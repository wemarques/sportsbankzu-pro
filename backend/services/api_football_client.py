# backend/services/api_football_client.py
"""
Client for API-Football (v3) — https://v3.football.api-sports.io/
Provides fixtures, live scores, standings, statistics, odds, H2H, and injuries.

Supports both async (httpx) and sync (requests) modes with SQLite TTL caching.
"""
import os
import json
import hashlib
import logging
import sqlite3
import time
from typing import Dict, List, Optional, Any
from datetime import date, datetime, timedelta

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore

try:
    import requests as _requests
except ImportError:
    _requests = None  # type: ignore

logger = logging.getLogger("sportsbankzu.services.api_football")

BASE_URL = "https://v3.football.api-sports.io"

# HTTP status codes that warrant a retry
_RETRYABLE_STATUS_CODES = {502, 503, 504, 429}


class APIFootballClient:
    """Client for API-Football v3.

    Authentication via header ``x-apisports-key``.
    All endpoints use GET requests only.
    Includes SQLite TTL cache (same pattern as FootyStatsClient).
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("API_FOOTBALL_KEY", "")
        if not self.api_key:
            logger.warning("API_FOOTBALL_KEY not configured — API-Football calls will be skipped")
        self.base_url = BASE_URL
        self.timeout = 15.0

        # SQLite cache setup (shared DB with FootyStats, separate table)
        if os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
            self.db_path = "/tmp/api_cache.db"
        else:
            self.db_path = "api_cache.db"
        self._init_db()

    def _init_db(self):
        """Initialize the cache table for API-Football responses."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS api_football_cache (
                    cache_key TEXT PRIMARY KEY,
                    endpoint TEXT,
                    params TEXT,
                    response TEXT,
                    created_at DATETIME,
                    expires_at DATETIME
                )
            """)
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error initializing API-Football cache: {e}")

    def _cache_key(self, endpoint: str, params: Dict) -> str:
        """Generate a unique cache key from endpoint + params."""
        clean = {k: v for k, v in sorted(params.items())}
        raw = f"apifootball:{endpoint}:{json.dumps(clean, sort_keys=True)}"
        return hashlib.md5(raw.encode()).hexdigest()

    def _get_from_cache(self, key: str, max_age_minutes: Optional[int] = None) -> Optional[Dict]:
        """Fetch a cached response if still valid."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            now = datetime.now()
            if max_age_minutes is not None:
                min_created = now - timedelta(minutes=max_age_minutes)
                cursor.execute(
                    "SELECT response FROM api_football_cache WHERE cache_key = ? AND expires_at > ? AND created_at > ?",
                    (key, now, min_created),
                )
            else:
                cursor.execute(
                    "SELECT response FROM api_football_cache WHERE cache_key = ? AND expires_at > ?",
                    (key, now),
                )
            row = cursor.fetchone()
            conn.close()
            if row:
                return json.loads(row[0])
        except Exception as e:
            logger.error(f"Cache read error: {e}")
        return None

    def _save_to_cache(self, key: str, endpoint: str, params: Dict, response: Dict, ttl_minutes: int = 60):
        """Persist a response to the cache."""
        try:
            now = datetime.now()
            expires = now + timedelta(minutes=ttl_minutes)
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                """INSERT OR REPLACE INTO api_football_cache
                   (cache_key, endpoint, params, response, created_at, expires_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (key, endpoint, json.dumps(params), json.dumps(response), now, expires),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Cache write error: {e}")

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> Dict[str, str]:
        return {"x-apisports-key": self.api_key}

    # ------------------------------------------------------------------
    # HTTP: async (httpx)
    # ------------------------------------------------------------------
    async def _get(self, endpoint: str, params: Dict) -> Dict:
        """Execute an async GET request to API-Football v3."""
        if not httpx:
            raise RuntimeError("httpx is not installed")
        if not self.api_key:
            raise RuntimeError("API_FOOTBALL_KEY not configured")

        url = f"{self.base_url}/{endpoint}"
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers=self._headers(),
                params=params,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()

            errors = data.get("errors")
            if errors and (isinstance(errors, dict) and errors) or (isinstance(errors, list) and errors):
                logger.error(f"API-Football error on {endpoint}: {errors}")

            return data

    # ------------------------------------------------------------------
    # HTTP: sync (requests) — used from ThreadPoolExecutor in fixtures
    # ------------------------------------------------------------------
    def _get_sync(self, endpoint: str, params: Dict, ttl_minutes: int = 60) -> Dict:
        """Execute a sync GET with cache + retry (same pattern as FootyStatsClient)."""
        if not self.api_key:
            return {"response": [], "errors": {"message": "API_FOOTBALL_KEY not configured"}}

        cache_key = self._cache_key(endpoint, params)
        cached = self._get_from_cache(cache_key, max_age_minutes=ttl_minutes)
        if cached is not None:
            logger.info(f"[api-football] Cache hit for {endpoint}")
            return cached

        if not _requests:
            raise RuntimeError("requests library is not installed")

        url = f"{self.base_url}/{endpoint}"
        max_attempts = 2
        last_error = None

        for attempt in range(1, max_attempts + 1):
            try:
                t0 = time.monotonic()
                resp = _requests.get(url, headers=self._headers(), params=params, timeout=self.timeout)
                elapsed_ms = int((time.monotonic() - t0) * 1000)

                if resp.status_code in _RETRYABLE_STATUS_CODES and attempt < max_attempts:
                    logger.warning(f"[api-football/{endpoint}] HTTP {resp.status_code} (attempt {attempt}) — retrying in 2s")
                    time.sleep(2)
                    continue

                resp.raise_for_status()
                data = resp.json()

                errors = data.get("errors")
                if errors and ((isinstance(errors, dict) and errors) or (isinstance(errors, list) and errors)):
                    logger.error(f"[api-football/{endpoint}] API error: {errors}")
                    return data

                self._save_to_cache(cache_key, endpoint, params, data, ttl_minutes)
                logger.info(f"[api-football/{endpoint}] OK ({elapsed_ms}ms, attempt {attempt})")
                return data

            except Exception as e:
                last_error = e
                logger.warning(f"[api-football/{endpoint}] Error (attempt {attempt}): {e}")
                if attempt < max_attempts:
                    time.sleep(2)

        logger.error(f"[api-football/{endpoint}] Failed after {max_attempts} attempts: {last_error}")
        return {"response": [], "errors": {"message": str(last_error)}}

    # ==================================================================
    # FIXTURES
    # ==================================================================
    def get_fixtures_by_date(
        self,
        league_id: int,
        season: int,
        match_date: Optional[str] = None,
        ttl_minutes: int = 5,
    ) -> List[Dict]:
        """Fetch fixtures for a league on a specific date (sync, cached).

        Args:
            league_id: API-Football numeric league ID
            season: Season year (e.g. 2025)
            match_date: Date string YYYY-MM-DD (defaults to today)
            ttl_minutes: Cache TTL (short for live, longer for past)

        Returns:
            List of raw fixture objects from API-Football response.
        """
        params: Dict[str, str] = {
            "league": str(league_id),
            "season": str(season),
            "date": match_date or date.today().isoformat(),
        }
        data = self._get_sync("fixtures", params, ttl_minutes=ttl_minutes)
        return data.get("response", [])

    def get_live_fixtures(self, league_id: Optional[int] = None) -> List[Dict]:
        """Fetch all currently live fixtures (sync, 1min cache).

        Optionally filter by league_id.
        """
        params: Dict[str, str] = {"live": "all"}
        if league_id:
            params["league"] = str(league_id)
        data = self._get_sync("fixtures", params, ttl_minutes=1)
        return data.get("response", [])

    @staticmethod
    def _normalize_team_name(name: str) -> str:
        """Normalize team name for cross-API matching.

        Handles common variations between FootyStats and API-Football:
        - "Atlético Madrid" vs "Atletico Madrid"
        - "FC Barcelona" vs "Barcelona"
        - "Man United" vs "Manchester United"
        - "Wolverhampton Wanderers" vs "Wolves"
        """
        import re
        import unicodedata

        if not name:
            return ""

        # Remove accents (é -> e, ã -> a, ü -> u)
        nfkd = unicodedata.normalize("NFKD", name)
        ascii_name = "".join(c for c in nfkd if not unicodedata.combining(c))

        # Lowercase
        result = ascii_name.lower().strip()

        # Remove common prefixes/suffixes that vary between APIs
        # Includes Brazilian (cr, se, ec, aa, ce, gr) and South American (csd, cn, cu) clubs
        result = re.sub(r"\b(fc|cf|sc|ac|as|us|rc|cd|ca|ss|afc|ssc|cr|se|ec|aa|ce|gr|csd|cn|cu|rcd|ud|sd)\b", "", result)
        # Remove punctuation
        result = re.sub(r"[.\-'\"()]", " ", result)
        # Collapse whitespace
        result = re.sub(r"\s+", " ", result).strip()

        return result

    @staticmethod
    def _team_names_match(name_a: str, name_b: str) -> bool:
        """Check if two team names refer to the same team.

        Uses normalized substring matching + token overlap for robustness.
        """
        norm_a = APIFootballClient._normalize_team_name(name_a)
        norm_b = APIFootballClient._normalize_team_name(name_b)

        if not norm_a or not norm_b:
            return False

        # Exact match after normalization
        if norm_a == norm_b:
            return True

        # Substring containment (handles "Barcelona" in "Barcelona" or vice-versa)
        if norm_a in norm_b or norm_b in norm_a:
            return True

        # Token overlap: if one name's significant tokens are a subset of the other
        tokens_a = set(norm_a.split())
        tokens_b = set(norm_b.split())
        # Remove very short tokens (1 char) that might be noise
        tokens_a = {t for t in tokens_a if len(t) > 1}
        tokens_b = {t for t in tokens_b if len(t) > 1}

        if tokens_a and tokens_b:
            overlap = tokens_a & tokens_b
            smaller = min(len(tokens_a), len(tokens_b))
            # If at least half of the smaller set's tokens overlap, consider it a match
            if smaller > 0 and len(overlap) >= max(1, smaller * 0.5):
                return True

        return False

    async def find_fixture(
        self,
        home_team: str,
        away_team: str,
        match_date: Optional[str] = None,
        league_id: Optional[int] = None,
        season: Optional[int] = None,
    ) -> Optional[Dict]:
        """Search for a fixture by team names and date (async).

        Uses normalized team name matching to bridge FootyStats → API-Football
        name differences (accents, prefixes like FC/SC, abbreviations).
        """
        params: Dict = {}
        if match_date:
            params["date"] = match_date
        else:
            params["date"] = date.today().isoformat()

        if league_id:
            params["league"] = str(league_id)
        if season:
            params["season"] = str(season)

        try:
            data = await self._get("fixtures", params)
        except Exception as e:
            logger.error(f"API-Football /fixtures error: {e}")
            return None

        fixtures = data.get("response", [])
        if not fixtures:
            logger.info(f"No fixtures found for date={params.get('date')}")
            return None

        # Pass 1: strict normalized matching (home=home, away=away)
        for fx in fixtures:
            teams = fx.get("teams", {})
            fx_home = teams.get("home", {}).get("name", "")
            fx_away = teams.get("away", {}).get("name", "")

            if self._team_names_match(home_team, fx_home) and \
               self._team_names_match(away_team, fx_away):
                logger.info(f"[find_fixture] Matched: '{home_team}'→'{fx_home}', '{away_team}'→'{fx_away}'")
                return fx

        # Pass 2: swapped order (rare but possible with different conventions)
        for fx in fixtures:
            teams = fx.get("teams", {})
            fx_home = teams.get("home", {}).get("name", "")
            fx_away = teams.get("away", {}).get("name", "")

            if self._team_names_match(home_team, fx_away) and \
               self._team_names_match(away_team, fx_home):
                logger.info(f"[find_fixture] Matched (swapped): '{home_team}'→'{fx_away}', '{away_team}'→'{fx_home}'")
                return fx

        logger.info(f"[find_fixture] No match for '{home_team}' vs '{away_team}' among {len(fixtures)} fixtures")
        return None

    # ==================================================================
    # LIVE DATA EXTRACTION
    # ==================================================================
    @staticmethod
    def extract_live_data(fixture: Dict) -> Dict:
        """Extract structured live match data from an API-Football fixture object."""
        fx = fixture.get("fixture", {})
        status_obj = fx.get("status", {})
        goals = fixture.get("goals", {})
        score_obj = fixture.get("score", {})

        status_short = status_obj.get("short", "NS")
        elapsed = status_obj.get("elapsed")
        extra = status_obj.get("extra")
        goals_home = goals.get("home")
        goals_away = goals.get("away")

        live_statuses = {"1H", "HT", "2H", "ET", "BT", "P", "SUSP", "INT", "LIVE"}
        finished_statuses = {"FT", "AET", "PEN"}

        score_str = "N/A"
        if goals_home is not None and goals_away is not None:
            score_str = f"{goals_home} - {goals_away}"

        # Halftime score
        ht = score_obj.get("halftime", {}) if score_obj else {}
        ht_home = ht.get("home")
        ht_away = ht.get("away")

        return {
            "fixture_id": fx.get("id"),
            "status": status_short,
            "status_long": status_obj.get("long", ""),
            "minute": elapsed,
            "extra_time": extra,
            "score": score_str,
            "goals_home": goals_home,
            "goals_away": goals_away,
            "halftime_home": ht_home,
            "halftime_away": ht_away,
            "is_live": status_short in live_statuses,
            "is_finished": status_short in finished_statuses,
        }

    # ==================================================================
    # STANDINGS
    # ==================================================================
    def get_standings(self, league_id: int, season: int, ttl_minutes: int = 360) -> List[Dict]:
        """Fetch league standings (sync, cached 6h).

        Returns a list of standing entries with:
            rank, team.id, team.name, points, goalsDiff, form, all/home/away stats
        """
        params = {"league": str(league_id), "season": str(season)}
        data = self._get_sync("standings", params, ttl_minutes=ttl_minutes)
        response = data.get("response", [])
        if not response:
            return []
        # API returns [{league: {standings: [[...]]}}]
        league_data = response[0].get("league", {})
        standings = league_data.get("standings", [])
        if standings and isinstance(standings[0], list):
            return standings[0]
        return standings

    # ==================================================================
    # TEAM STATISTICS
    # ==================================================================
    def get_team_statistics(self, team_id: int, league_id: int, season: int, ttl_minutes: int = 360) -> Dict:
        """Fetch aggregated team statistics for a season (sync, cached 6h).

        Returns goals, fixtures, cards, lineups, etc.
        """
        params = {
            "team": str(team_id),
            "league": str(league_id),
            "season": str(season),
        }
        data = self._get_sync("teams/statistics", params, ttl_minutes=ttl_minutes)
        return data.get("response", {})

    # ==================================================================
    # FIXTURE STATISTICS (match-level)
    # ==================================================================
    def get_fixture_statistics(self, fixture_id: int, ttl_minutes: int = 60) -> List[Dict]:
        """Fetch in-match statistics (possession, shots, corners, etc.) for a fixture."""
        params = {"fixture": str(fixture_id)}
        data = self._get_sync("fixtures/statistics", params, ttl_minutes=ttl_minutes)
        return data.get("response", [])

    # ==================================================================
    # FIXTURE EVENTS (goals, cards, subs)
    # ==================================================================
    def get_fixture_events(self, fixture_id: int, ttl_minutes: int = 5) -> List[Dict]:
        """Fetch match events (goals, cards, substitutions) for a fixture."""
        params = {"fixture": str(fixture_id)}
        data = self._get_sync("fixtures/events", params, ttl_minutes=ttl_minutes)
        return data.get("response", [])

    # ==================================================================
    # FIXTURE LINEUPS
    # ==================================================================
    def get_fixture_lineups(self, fixture_id: int, ttl_minutes: int = 60) -> List[Dict]:
        """Fetch lineups for a fixture (available ~1h before kickoff)."""
        params = {"fixture": str(fixture_id)}
        data = self._get_sync("fixtures/lineups", params, ttl_minutes=ttl_minutes)
        return data.get("response", [])

    # ==================================================================
    # ODDS (pre-match)
    # ==================================================================
    def get_odds(self, fixture_id: int, ttl_minutes: int = 30) -> List[Dict]:
        """Fetch pre-match odds for a fixture.

        Returns bookmaker odds for multiple markets (1X2, O/U, BTTS, etc.).
        """
        params = {"fixture": str(fixture_id)}
        data = self._get_sync("odds", params, ttl_minutes=ttl_minutes)
        return data.get("response", [])

    def extract_best_odds(self, odds_response: List[Dict]) -> Dict[str, Any]:
        """Extract best odds from the odds response into a flat dict.

        Prioritizes well-known bookmakers (Bet365, Pinnacle, 1xBet).
        Returns:
            {
                "home": float, "draw": float, "away": float,
                "over_25": float, "under_25": float,
                "btts_yes": float, "btts_no": float,
                "bookmaker": str,
            }
        """
        result: Dict[str, Any] = {}
        if not odds_response:
            return result

        # Priority bookmakers
        priority = ["bet365", "pinnacle", "1xbet", "betfair", "unibet"]

        for entry in odds_response:
            bookmakers = entry.get("bookmakers", [])
            # Sort: prioritized bookmakers first
            sorted_bk = sorted(
                bookmakers,
                key=lambda b: next(
                    (i for i, p in enumerate(priority) if p in (b.get("name", "")).lower()),
                    len(priority),
                ),
            )

            for bk in sorted_bk:
                bk_name = bk.get("name", "")
                for bet in bk.get("bets", []):
                    bet_name = (bet.get("name") or "").lower()
                    values = bet.get("values", [])

                    if "match winner" in bet_name or bet_name == "1x2":
                        for v in values:
                            val = v.get("value", "")
                            odd = _safe_float(v.get("odd"))
                            if val == "Home" and "home" not in result:
                                result["home"] = odd
                            elif val == "Draw" and "draw" not in result:
                                result["draw"] = odd
                            elif val == "Away" and "away" not in result:
                                result["away"] = odd
                        if "home" in result:
                            result.setdefault("bookmaker", bk_name)

                    elif "over/under" in bet_name or "goals" in bet_name:
                        for v in values:
                            val = str(v.get("value", ""))
                            odd = _safe_float(v.get("odd"))
                            if "over 2.5" in val.lower() and "over_25" not in result:
                                result["over_25"] = odd
                            elif "under 2.5" in val.lower() and "under_25" not in result:
                                result["under_25"] = odd

                    elif "both teams" in bet_name or "btts" in bet_name:
                        for v in values:
                            val = str(v.get("value", "")).lower()
                            odd = _safe_float(v.get("odd"))
                            if val == "yes" and "btts_yes" not in result:
                                result["btts_yes"] = odd
                            elif val == "no" and "btts_no" not in result:
                                result["btts_no"] = odd

                # If we have at least 1X2 from a priority bookmaker, stop
                if "home" in result:
                    break

        return result

    # ==================================================================
    # PREDICTIONS (API-Football built-in predictions)
    # ==================================================================
    def get_predictions(self, fixture_id: int, ttl_minutes: int = 60) -> Dict:
        """Fetch API-Football's own match predictions.

        Returns winner prediction, under/over, goals, advice, etc.
        """
        params = {"fixture": str(fixture_id)}
        data = self._get_sync("predictions", params, ttl_minutes=ttl_minutes)
        response = data.get("response", [])
        return response[0] if response else {}

    # ==================================================================
    # HEAD-TO-HEAD
    # ==================================================================
    def get_h2h(self, team1_id: int, team2_id: int, last: int = 10, ttl_minutes: int = 360) -> List[Dict]:
        """Fetch head-to-head history between two teams.

        Args:
            team1_id, team2_id: API-Football team IDs
            last: Number of recent encounters (default 10)

        Returns list of fixture objects.
        """
        params = {"h2h": f"{team1_id}-{team2_id}", "last": str(last)}
        data = self._get_sync("fixtures/headtohead", params, ttl_minutes=ttl_minutes)
        return data.get("response", [])

    # ==================================================================
    # INJURIES / SUSPENSIONS
    # ==================================================================
    @staticmethod
    def _parse_injuries(raw_injuries: List[Dict]) -> List[Dict]:
        """Parse raw injury objects into structured dicts with status classification.

        API-Football injury types:
        - "Missing Fixture" -> confirmed out (FORA)
        - "Questionable"    -> doubtful (DUVIDA)
        - Other (e.g. "Suspension") -> confirmed out (FORA)
        """
        result = []
        for inj in raw_injuries:
            player_info = inj.get("player", {})
            team_info = inj.get("team", {})
            raw_type = player_info.get("type", "Unknown")

            # Classify: Questionable = doubt, everything else = confirmed out
            if raw_type == "Questionable":
                availability = "DUVIDA"
            else:
                availability = "FORA"

            result.append({
                "player": player_info.get("name", "Unknown"),
                "team": team_info.get("name", "Unknown"),
                "type": raw_type,
                "reason": player_info.get("reason", "Unknown"),
                "availability": availability,
            })
        return result

    async def get_injuries(self, fixture_id: int) -> List[Dict]:
        """Fetch injuries/suspensions for a fixture (async, with sync cache fallback).

        Uses the sync cache (TTL 240min / 4h) to respect API-Football's
        recommendation of max 1 call per day per fixture for injury data.
        """
        # Check sync cache first (injuries update every ~4h per API docs)
        params = {"fixture": str(fixture_id)}
        cache_key = self._cache_key("injuries", params)
        cached = self._get_from_cache(cache_key, max_age_minutes=240)
        if cached is not None:
            logger.info(f"[api-football/injuries] Cache hit for fixture {fixture_id}")
            return self._parse_injuries(cached.get("response", []))

        try:
            data = await self._get("injuries", params)
        except Exception as e:
            logger.error(f"API-Football /injuries error: {e}")
            return []

        # Save to cache with 4h TTL (API updates injuries every ~4h)
        self._save_to_cache(cache_key, "injuries", params, data, ttl_minutes=240)
        return self._parse_injuries(data.get("response", []))

    def get_injuries_sync(self, fixture_id: int, ttl_minutes: int = 240) -> List[Dict]:
        """Fetch injuries/suspensions for a fixture (sync, cached 4h).

        Default TTL raised to 240min (4h) per API-Football recommendation.
        """
        params = {"fixture": str(fixture_id)}
        data = self._get_sync("injuries", params, ttl_minutes=ttl_minutes)
        return self._parse_injuries(data.get("response", []))

    # ==================================================================
    # LEAGUE COVERAGE CHECK
    # ==================================================================
    def get_league_coverage(self, league_id: int, season: int, ttl_minutes: int = 1440) -> Dict:
        """Fetch league info including coverage flags (sync, cached 24h).

        Returns coverage dict, e.g.:
            {"injuries": True, "predictions": True, "odds": True, ...}
        """
        params = {"id": str(league_id), "season": str(season)}
        data = self._get_sync("leagues", params, ttl_minutes=ttl_minutes)
        response = data.get("response", [])
        if not response:
            return {}
        league_data = response[0]
        seasons = league_data.get("seasons", [])
        # Find matching season
        for s in seasons:
            if s.get("year") == season:
                return s.get("coverage", {})
        # Fallback: return last season's coverage
        if seasons:
            return seasons[-1].get("coverage", {})
        return {}

    def has_injury_coverage(self, league_id: int, season: int) -> bool:
        """Check if a league supports injury data for the given season."""
        coverage = self.get_league_coverage(league_id, season)
        injuries_coverage = coverage.get("injuries", False)
        if isinstance(injuries_coverage, dict):
            # Some responses have injuries as a bool, others as a nested object
            return bool(injuries_coverage)
        return bool(injuries_coverage)

    # ==================================================================
    # HIGH-LEVEL: Enrich a fixture record with live data
    # ==================================================================
    def enrich_fixture_record(self, record: Dict, fixture: Dict) -> Dict:
        """Overlay API-Football live data onto an existing fixture record.

        Mutates and returns the record with updated status, score, and minute.
        Used by the fixtures route to enrich FootyStats records.
        """
        live = self.extract_live_data(fixture)

        # Map API-Football status to internal status
        af_status = live["status"]
        status_mapping = {
            "NS": "scheduled",
            "TBD": "scheduled",
            "1H": "live",
            "HT": "live",
            "2H": "live",
            "ET": "live",
            "BT": "live",
            "P": "live",
            "LIVE": "live",
            "FT": "finished",
            "AET": "finished",
            "PEN": "finished",
            "PST": "postponed",
            "CANC": "cancelled",
            "ABD": "cancelled",
            "SUSP": "suspended",
            "INT": "suspended",
        }

        mapped_status = status_mapping.get(af_status, record.get("status", "scheduled"))

        # Only override if API-Football has a more "advanced" status
        status_priority = {"scheduled": 0, "live": 2, "finished": 3, "postponed": 1, "cancelled": 1, "suspended": 1}
        current_priority = status_priority.get(record.get("status", "scheduled"), 0)
        new_priority = status_priority.get(mapped_status, 0)

        if new_priority >= current_priority:
            record["status"] = mapped_status

        # Update score if live or finished
        if live["is_live"] or live["is_finished"]:
            if live["goals_home"] is not None:
                record.setdefault("score", {})
                record["score"]["home"] = live["goals_home"]
                record["score"]["away"] = live["goals_away"]
                if live["halftime_home"] is not None:
                    record["score"].setdefault("halftime", {})
                    record["score"]["halftime"]["home"] = live["halftime_home"]
                    record["score"]["halftime"]["away"] = live["halftime_away"]

        # Update minute/period for live matches
        # Map API-Football period codes to internal format (1H→1T, 2H→2T)
        _period_map = {"1H": "1T", "HT": "HT", "2H": "2T", "ET": "ET", "BT": "HT", "P": "PEN"}
        if live["is_live"]:
            record["minute"] = live["minute"]
            record["period"] = _period_map.get(af_status, af_status)

        # Store the API-Football fixture ID for further enrichment calls
        if live["fixture_id"]:
            record["apiFootballFixtureId"] = live["fixture_id"]

        record["apiFootballStatus"] = af_status

        return record

    # ==================================================================
    # HIGH-LEVEL: fetch match + injuries in one call (async)
    # ==================================================================
    @staticmethod
    def extract_league_info(fixture: Dict) -> Dict:
        """Extract league metadata from a fixture object."""
        league = fixture.get("league", {})
        return {
            "league_name": league.get("name", ""),
            "league_country": league.get("country", ""),
            "league_season": league.get("season"),
            "league_id": league.get("id"),
            "league_logo": league.get("logo", ""),
            "league_round": league.get("round", ""),
        }

    async def get_match_live_data(
        self,
        home_team: str,
        away_team: str,
        match_date: Optional[str] = None,
        league_id: Optional[int] = None,
        season: Optional[int] = None,
    ) -> Dict:
        """Unified method: finds the fixture, extracts live data, league info, and fetches injuries.

        Includes coverage check: only calls /injuries if the league supports it.
        """
        empty_result = {
            "live_data": {
                "fixture_id": None,
                "status": "NS",
                "status_long": "Not Started",
                "minute": None,
                "extra_time": None,
                "score": "N/A",
                "goals_home": None,
                "goals_away": None,
                "halftime_home": None,
                "halftime_away": None,
                "is_live": False,
                "is_finished": False,
            },
            "league_info": {
                "league_name": "",
                "league_country": "",
                "league_season": None,
                "league_id": None,
                "league_logo": "",
                "league_round": "",
            },
            "injuries": [],
            "absences": "Nenhuma informacao disponivel",
            "live_status": "Sem dados ao vivo disponiveis",
        }

        if not self.is_configured:
            logger.info("API-Football not configured, returning empty result")
            return empty_result

        fixture = await self.find_fixture(
            home_team, away_team, match_date,
            league_id=league_id, season=season,
        )
        if not fixture:
            return empty_result

        live_data = self.extract_live_data(fixture)
        league_info = self.extract_league_info(fixture)

        # Fetch injuries only if the league has coverage for it
        injuries = []
        fixture_id = live_data.get("fixture_id")
        fx_league_id = league_info.get("league_id")
        fx_season = league_info.get("league_season") or season or date.today().year

        if fixture_id:
            should_fetch_injuries = True

            if fx_league_id:
                try:
                    has_coverage = self.has_injury_coverage(fx_league_id, fx_season)
                    if not has_coverage:
                        logger.info(
                            f"[api-football] League {fx_league_id} ({league_info.get('league_name')}) "
                            f"has no injury coverage for season {fx_season} — skipping /injuries"
                        )
                        should_fetch_injuries = False
                except Exception as e:
                    logger.warning(f"[api-football] Coverage check failed for league {fx_league_id}: {e}")
                    # Proceed anyway — fail-open to not lose data

            if should_fetch_injuries:
                try:
                    injuries = await self.get_injuries(fixture_id)
                except Exception as e:
                    logger.warning(f"[api-football] Injuries fetch failed for fixture {fixture_id}: {e}")

        absences = self._format_absences(injuries, home_team, away_team)
        live_status = self._format_live_status(live_data)

        return {
            "live_data": live_data,
            "league_info": league_info,
            "injuries": injuries,
            "absences": absences,
            "live_status": live_status,
        }

    # ==================================================================
    # HIGH-LEVEL: Convert API-Football fixtures to internal record format
    # ==================================================================
    def fixtures_to_records(self, fixtures: List[Dict], league_id: str) -> List[Dict[str, Any]]:
        """Convert raw API-Football fixture objects into internal record dicts.

        Used as a fallback data source when FootyStats is unavailable.
        Produces records compatible with the frontend schema.
        """
        from backend.services.math_service import implied_probs

        records = []
        for fx in fixtures:
            fx_data = fx.get("fixture", {})
            teams = fx.get("teams", {})
            goals = fx.get("goals", {})
            score_obj = fx.get("score", {})
            league_data = fx.get("league", {})

            home_name = teams.get("home", {}).get("name", "Unknown")
            away_name = teams.get("away", {}).get("name", "Unknown")
            home_id = teams.get("home", {}).get("id")
            away_id = teams.get("away", {}).get("id")

            # Status mapping
            status_short = fx_data.get("status", {}).get("short", "NS")
            status_mapping = {
                "NS": "scheduled", "TBD": "scheduled",
                "1H": "live", "HT": "live", "2H": "live",
                "ET": "live", "BT": "live", "P": "live", "LIVE": "live",
                "FT": "finished", "AET": "finished", "PEN": "finished",
                "PST": "postponed", "CANC": "cancelled",
                "ABD": "cancelled", "SUSP": "suspended", "INT": "suspended",
            }
            status = status_mapping.get(status_short, "scheduled")

            # Score
            goals_home = goals.get("home")
            goals_away = goals.get("away")
            ht = score_obj.get("halftime", {})

            # Datetime
            dt_str = fx_data.get("date", "")
            timestamp = fx_data.get("timestamp")

            # Venue
            venue = fx_data.get("venue", {})
            venue_name = venue.get("name", "") if venue else ""

            record: Dict[str, Any] = {
                "id": f"af-{fx_data.get('id', 0)}",
                "homeTeam": home_name,
                "awayTeam": away_name,
                "homeTeamId": home_id,
                "awayTeamId": away_id,
                "league": league_id,
                "leagueName": league_data.get("name", ""),
                "country": league_data.get("country", ""),
                "status": status,
                "datetime": dt_str,
                "timestamp": timestamp,
                "venue": venue_name,
                "score": {
                    "home": goals_home,
                    "away": goals_away,
                    "halftime": {
                        "home": ht.get("home"),
                        "away": ht.get("away"),
                    },
                },
                "minute": fx_data.get("status", {}).get("elapsed"),
                "period": status_short if status == "live" else None,
                "apiFootballFixtureId": fx_data.get("id"),
                "apiFootballStatus": status_short,
                "dataSource": "API-Football v3",
            }

            # Try to fetch odds for this fixture (sync, from cache or API)
            af_fixture_id = fx_data.get("id")
            if af_fixture_id and status == "scheduled":
                try:
                    odds_data = self.get_odds(af_fixture_id, ttl_minutes=30)
                    best_odds = self.extract_best_odds(odds_data)
                    if best_odds.get("home"):
                        record["odds"] = {
                            "home": best_odds.get("home"),
                            "draw": best_odds.get("draw"),
                            "away": best_odds.get("away"),
                            "over25": best_odds.get("over_25"),
                            "under25": best_odds.get("under_25"),
                            "bttsYes": best_odds.get("btts_yes"),
                            "bttsNo": best_odds.get("btts_no"),
                            "bookmaker": best_odds.get("bookmaker", ""),
                        }
                        # Implied probabilities
                        probs = implied_probs(
                            best_odds.get("home", 0),
                            best_odds.get("draw", 0),
                            best_odds.get("away", 0),
                        )
                        record["stats"] = {
                            "homeWinProb": round(probs[0] * 100, 1) if probs[0] else 0,
                            "drawProb": round(probs[1] * 100, 1) if probs[1] else 0,
                            "awayWinProb": round(probs[2] * 100, 1) if probs[2] else 0,
                        }
                except Exception as e:
                    logger.warning(f"[api-football] Failed to fetch odds for fixture {af_fixture_id}: {e}")

            records.append(record)

        return records

    # ==================================================================
    # FORMATTING HELPERS
    # ==================================================================
    @staticmethod
    def _format_absences(injuries: List[Dict], home_team: str, away_team: str) -> str:
        """Format injuries into a readable string for AI context.

        Differentiates between confirmed absences [FORA] and doubtful [DUVIDA]
        so the AI can weigh the impact accordingly.
        """
        if not injuries:
            return "Nenhuma ausencia reportada pela API-Football."

        home_absences = []
        away_absences = []

        home_lower = home_team.lower()
        away_lower = away_team.lower()

        for inj in injuries:
            team = inj.get("team", "")
            player = inj.get("player", "Unknown")
            reason = inj.get("reason", "Unknown")
            availability = inj.get("availability", "FORA")

            entry = f"{player} ({reason}) [{availability}]"

            team_lower = team.lower()
            if home_lower in team_lower or team_lower in home_lower:
                home_absences.append(entry)
            elif away_lower in team_lower or team_lower in away_lower:
                away_absences.append(entry)

        parts = []
        if home_absences:
            parts.append(f"{home_team}: {', '.join(home_absences)}")
        else:
            parts.append(f"{home_team}: Sem ausencias reportadas")
        if away_absences:
            parts.append(f"{away_team}: {', '.join(away_absences)}")
        else:
            parts.append(f"{away_team}: Sem ausencias reportadas")

        return " | ".join(parts)

    @staticmethod
    def _format_live_status(live_data: Dict) -> str:
        """Format live data into a readable string for AI context."""
        status = live_data.get("status", "NS")
        minute = live_data.get("minute")
        score = live_data.get("score", "N/A")

        status_map = {
            "NS": "Jogo nao iniciado",
            "TBD": "Horario a definir",
            "1H": "Primeiro tempo em andamento",
            "HT": "Intervalo",
            "2H": "Segundo tempo em andamento",
            "ET": "Prorrogacao",
            "BT": "Intervalo da prorrogacao",
            "P": "Penaltis em andamento",
            "FT": "Jogo encerrado",
            "AET": "Encerrado apos prorrogacao",
            "PEN": "Encerrado nos penaltis",
            "PST": "Jogo adiado",
            "CANC": "Jogo cancelado",
            "ABD": "Jogo abandonado",
            "SUSP": "Jogo suspenso",
            "INT": "Jogo interrompido",
            "LIVE": "Jogo em andamento",
        }

        status_desc = status_map.get(status, f"Status: {status}")

        if live_data.get("is_live") and minute is not None:
            extra = live_data.get("extra_time")
            minute_str = f"{minute}"
            if extra:
                minute_str += f"+{extra}"
            return f"{status_desc}: {minute_str} min, Placar: {score}"
        elif live_data.get("is_finished"):
            return f"{status_desc}. Placar final: {score}"
        else:
            return status_desc


def _safe_float(val: Any) -> float:
    """Safely convert a value to float, returning 0.0 on failure."""
    if val is None:
        return 0.0
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0
