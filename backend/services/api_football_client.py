# backend/services/api_football_client.py
"""
Client for API-Football (v3) — https://v3.football.api-sports.io/
Provides fixtures, live scores, standings, statistics, odds, H2H, and injuries.

Supports both async (httpx) and sync (requests) modes with SQLite TTL caching.
"""
import asyncio
import os
import json
import hashlib
import logging
import sqlite3
import time
from typing import Any, Dict, List, Optional, Tuple
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

# Canonical alias map: nickname/abbreviation → full canonical name (lowercase).
# Used by _team_names_match to resolve common short names that fuzzy/token
# matching cannot handle (e.g. "Wolves" vs "Wolverhampton Wanderers").
_TEAM_ALIASES: Dict[str, str] = {
    "wolves": "wolverhampton wanderers",
    "man united": "manchester united",
    "man utd": "manchester united",
    "man city": "manchester city",
    "spurs": "tottenham hotspur",
    "brighton": "brighton and hove albion",
    "west ham": "west ham united",
    "newcastle": "newcastle united",
    "leicester": "leicester city",
    "nottm forest": "nottingham forest",
    "nott'm forest": "nottingham forest",
    "sheffield utd": "sheffield united",
    "luton": "luton town",
    "atletico madrid": "atletico de madrid",
    "atletico": "atletico de madrid",
    "real sociedad": "real sociedad de futbol",
    "betis": "real betis balompie",
    "real betis": "real betis balompie",
    "inter": "inter milan",
    "internazionale": "inter milan",
    "ac milan": "milan",
    "napoli": "ssc napoli",
    "psg": "paris saint germain",
    "paris sg": "paris saint germain",
    "st etienne": "saint etienne",
    "lyon": "olympique lyonnais",
    "marseille": "olympique de marseille",
    "bayern": "bayern munich",
    "bayern munchen": "bayern munich",
    "dortmund": "borussia dortmund",
    "monchengladbach": "borussia monchengladbach",
    "gladbach": "borussia monchengladbach",
    "leverkusen": "bayer leverkusen",
    "rb leipzig": "rasenballsport leipzig",
    "corinthians": "sport club corinthians paulista",
    "palmeiras": "sociedade esportiva palmeiras",
    "flamengo": "clube de regatas do flamengo",
    "santos": "santos futebol clube",
    "sao paulo": "sao paulo futebol clube",
    "gremio": "gremio foot-ball porto alegrense",
    "internacional": "sport club internacional",
    "botafogo": "botafogo de futebol e regatas",
}

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

                # --- Rate limit monitoring (API-Football docs) ---
                rl_remaining_day = resp.headers.get("x-ratelimit-requests-remaining")
                rl_remaining_min = resp.headers.get("X-Ratelimit-Remaining",
                                                    resp.headers.get("x-ratelimit-remaining"))
                if rl_remaining_day is not None:
                    try:
                        remaining = int(rl_remaining_day)
                        if remaining <= 10:
                            logger.warning(
                                f"[api-football] Daily quota almost exhausted: {remaining} requests remaining"
                            )
                        elif remaining <= 50:
                            logger.info(f"[api-football] Daily quota: {remaining} requests remaining")
                    except (ValueError, TypeError):
                        pass

                errors = data.get("errors")
                if errors and ((isinstance(errors, dict) and errors) or (isinstance(errors, list) and errors)):
                    logger.error(f"[api-football/{endpoint}] API error: {errors}")
                    return data

                # Warn if response is paginated and caller isn't handling it
                paging = data.get("paging", {})
                total_pages = paging.get("total", 1)
                current_page = paging.get("current", 1)
                if total_pages > 1 and current_page == 1 and "page" not in params:
                    logger.warning(
                        f"[api-football/{endpoint}] Response has {total_pages} pages but only page 1 fetched "
                        f"({data.get('results', 0)} results on this page)"
                    )

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
            "timezone": "America/Sao_Paulo",
        }
        data = self._get_sync("fixtures", params, ttl_minutes=ttl_minutes)
        return data.get("response", [])

    def get_season_fixtures(
        self,
        league_id: int,
        season: int,
        ttl_minutes: int = 1440,
    ) -> List[Dict]:
        """Fetch ALL finished fixtures for a league+season (sync, cached 24h).

        Returns only finished matches. Used for historical calibration.
        """
        params: Dict[str, str] = {
            "league": str(league_id),
            "season": str(season),
            "timezone": "America/Sao_Paulo",
        }
        data = self._get_sync("fixtures", params, ttl_minutes=ttl_minutes)
        fixtures = data.get("response", [])

        finished = [
            f for f in fixtures
            if f.get("fixture", {}).get("status", {}).get("short") in ("FT", "AET", "PEN")
        ]

        logger.info(f"[api-football] season {season} league {league_id}: {len(finished)} finished / {len(fixtures)} total")
        return finished

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
        - "Al-Hazem" vs "Al Hazm" (Arabic transliteration)
        - "Al Taawoun" vs "Al Taawon"
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
        # Includes Brazilian (cr, se, ec, aa, ce, gr), South American (csd, cn, cu),
        # and Arabic article "al" (equivalent of "The" — varies between APIs)
        result = re.sub(r"\b(fc|cf|sc|ac|as|us|rc|cd|ca|ss|afc|ssc|cr|se|ec|aa|ce|gr|csd|cn|cu|rcd|ud|sd|al)\b", "", result)
        # Remove punctuation
        result = re.sub(r"[.\-'\"()]", " ", result)
        # Collapse whitespace
        result = re.sub(r"\s+", " ", result).strip()

        return result

    @staticmethod
    def _fuzzy_match(s1: str, s2: str) -> float:
        """Return similarity ratio (0.0–1.0) between two strings using SequenceMatcher."""
        from difflib import SequenceMatcher
        if not s1 or not s2:
            return 0.0
        return SequenceMatcher(None, s1, s2).ratio()

    @staticmethod
    def _resolve_alias(name: str) -> str:
        """Resolve a team name to its canonical form using the alias map."""
        low = name.lower().strip()
        if low in _TEAM_ALIASES:
            return _TEAM_ALIASES[low]
        # Also try the already-normalized form
        norm = APIFootballClient._normalize_team_name(name)
        if norm in _TEAM_ALIASES:
            return _TEAM_ALIASES[norm]
        return norm

    @staticmethod
    def _team_names_match(name_a: str, name_b: str) -> bool:
        """Check if two team names refer to the same team.

        Uses alias resolution + normalized substring matching + token overlap + fuzzy matching.
        Handles Arabic transliterations (Al-Hazem/Al Hazm, Taawoun/Taawon)
        and common nicknames (Wolves/Wolverhampton Wanderers).
        """
        norm_a = APIFootballClient._normalize_team_name(name_a)
        norm_b = APIFootballClient._normalize_team_name(name_b)

        if not norm_a or not norm_b:
            return False

        # Resolve aliases before comparing (Wolves → wolverhampton wanderers)
        canon_a = APIFootballClient._resolve_alias(name_a)
        canon_b = APIFootballClient._resolve_alias(name_b)
        if canon_a == canon_b:
            return True

        # Exact match after normalization
        if norm_a == norm_b:
            return True

        # Substring containment (handles "Barcelona" in "Barcelona" or vice-versa)
        if norm_a in norm_b or norm_b in norm_a:
            return True
        # Also check canonical forms for substring
        if canon_a in canon_b or canon_b in canon_a:
            return True

        # Fuzzy match: handles transliteration variants (Hazm/Hazem, Taawon/Taawoun)
        # Threshold 0.8 = allows ~1 char difference per 5 chars
        if APIFootballClient._fuzzy_match(norm_a, norm_b) >= 0.8:
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
            # Require >50% overlap AND at least 1 non-trivial token match
            if smaller > 0 and len(overlap) >= max(1, smaller * 0.5):
                return True

            # Token-level fuzzy: check if non-overlapping tokens are close matches
            # Handles "hazm"/"hazem", "taawon"/"taawoun" after "al" prefix removal
            non_overlap_a = tokens_a - overlap
            non_overlap_b = tokens_b - overlap
            if non_overlap_a and non_overlap_b and len(non_overlap_a) <= 2:
                fuzzy_matches = 0
                for ta in non_overlap_a:
                    for tb in non_overlap_b:
                        if APIFootballClient._fuzzy_match(ta, tb) >= 0.75:
                            fuzzy_matches += 1
                            break
                if fuzzy_matches == len(non_overlap_a):
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

        # Corner kicks from inline statistics (present in /fixtures?live=all)
        home_corners: int | None = None
        away_corners: int | None = None
        raw_stats = fixture.get("statistics")
        if raw_stats and isinstance(raw_stats, list):
            for team_block in raw_stats:
                stats_list = team_block.get("statistics", [])
                for s in stats_list:
                    if "corner" in str(s.get("type", "")).lower():
                        val = s.get("value")
                        if val is not None:
                            try:
                                val = int(val)
                            except (ValueError, TypeError):
                                val = None
                        if home_corners is None:
                            home_corners = val
                        else:
                            away_corners = val
                        break

        # Possession from inline statistics (if present)
        home_possession: int | None = None
        away_possession: int | None = None
        if raw_stats and isinstance(raw_stats, list):
            for team_block in raw_stats:
                stats_list = team_block.get("statistics", [])
                for s in stats_list:
                    if s.get("type") == "Ball Possession":
                        val = s.get("value")
                        if isinstance(val, str) and val.endswith("%"):
                            try:
                                val = int(val.replace("%", ""))
                            except (ValueError, TypeError):
                                val = None
                        if home_possession is None:
                            home_possession = val
                        else:
                            away_possession = val
                        break

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
            "home_corners": home_corners,
            "away_corners": away_corners,
            "home_possession": home_possession,
            "away_possession": away_possession,
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

    # ------------------------------------------------------------------
    # ASYNC versions of statistics & events (for asyncio.gather in live)
    # ------------------------------------------------------------------
    async def get_fixture_statistics_async(self, fixture_id: int) -> List[Dict]:
        """Fetch in-match statistics asynchronously (with sync cache fallback, TTL 2min)."""
        params = {"fixture": str(fixture_id)}
        cache_key = self._cache_key("fixtures/statistics", params)
        cached = self._get_from_cache(cache_key, max_age_minutes=2)
        if cached is not None:
            logger.info(f"[api-football/statistics] Cache hit for fixture {fixture_id}")
            return cached.get("response", [])
        try:
            data = await self._get("fixtures/statistics", params)
        except Exception as e:
            logger.error(f"[api-football] /fixtures/statistics error for {fixture_id}: {e}")
            return []
        self._save_to_cache(cache_key, "fixtures/statistics", params, data, ttl_minutes=2)
        return data.get("response", [])

    async def get_fixture_events_async(self, fixture_id: int) -> List[Dict]:
        """Fetch match events asynchronously (with sync cache fallback, TTL 2min)."""
        params = {"fixture": str(fixture_id)}
        cache_key = self._cache_key("fixtures/events", params)
        cached = self._get_from_cache(cache_key, max_age_minutes=2)
        if cached is not None:
            logger.info(f"[api-football/events] Cache hit for fixture {fixture_id}")
            return cached.get("response", [])
        try:
            data = await self._get("fixtures/events", params)
        except Exception as e:
            logger.error(f"[api-football] /fixtures/events error for {fixture_id}: {e}")
            return []
        self._save_to_cache(cache_key, "fixtures/events", params, data, ttl_minutes=2)
        return data.get("response", [])

    # ------------------------------------------------------------------
    # PARSERS: extract structured stats from API-Football responses
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_corners_from_stats(raw_stats: List[Dict]) -> Tuple[Optional[int], Optional[int]]:
        """Extract home/away corner counts from /fixtures/statistics response.

        Handles multiple API response formats and case-insensitive stat type matching.
        Returns (home_corners, away_corners) or (None, None) if not found.
        """
        if not raw_stats or not isinstance(raw_stats, list):
            return (None, None)
        home_corners: Optional[int] = None
        away_corners: Optional[int] = None

        def _parse_corner_val(val: Any) -> Optional[int]:
            if val is None:
                return None
            try:
                v = int(val)
                return v if v >= 0 else None
            except (ValueError, TypeError):
                return None

        def _is_corner_stat(stype: str) -> bool:
            if not stype:
                return False
            return "corner" in str(stype).lower()

        for idx in range(min(2, len(raw_stats))):
            team_block = raw_stats[idx]
            stats_list: List[Dict] = []

            if isinstance(team_block, dict):
                stats_list = team_block.get("statistics", [])
                if not stats_list and isinstance(team_block.get("statistics"), list):
                    stats_list = team_block["statistics"]
            elif isinstance(team_block, list):
                stats_list = team_block

            for s in stats_list:
                if not isinstance(s, dict):
                    continue
                stype = s.get("type", "")
                if _is_corner_stat(stype):
                    val = _parse_corner_val(s.get("value"))
                    if val is not None:
                        if idx == 0:
                            home_corners = val
                        else:
                            away_corners = val
                    break

        return (home_corners, away_corners)

    @staticmethod
    def parse_fixture_statistics(raw_stats: List[Dict]) -> Dict:
        """Parse /fixtures/statistics response into a structured dict.

        Returns dict with keys per team (home/away index 0/1):
          possession, shots_on_goal, shots_off_goal, shots_inside_box,
          goalkeeper_saves, corner_kicks, fouls, yellow_cards, red_cards,
          total_shots, shots_blocked, offsides, passes_total, passes_accurate,
          passes_pct, expected_goals.
        """
        result: Dict[str, Any] = {"home": {}, "away": {}}

        stat_key_map = {
            "Ball Possession": "possession",
            "Shots on Goal": "shots_on_goal",
            "Shots off Goal": "shots_off_goal",
            "Shots insidebox": "shots_inside_box",
            "Shots outsidebox": "shots_outside_box",
            "Goalkeeper Saves": "goalkeeper_saves",
            "Corner Kicks": "corner_kicks",
            "Corner kicks": "corner_kicks",
            "Fouls": "fouls",
            "Yellow Cards": "yellow_cards",
            "Red Cards": "red_cards",
            "Total Shots": "total_shots",
            "Blocked Shots": "shots_blocked",
            "Offsides": "offsides",
            "Total passes": "passes_total",
            "Passes accurate": "passes_accurate",
            "Passes %": "passes_pct",
            "expected_goals": "expected_goals",
        }

        for idx, label in enumerate(["home", "away"]):
            if idx >= len(raw_stats):
                break
            team_block = raw_stats[idx]
            team_name = (team_block.get("team") or {}).get("name", label) if isinstance(team_block, dict) else label
            result[label]["team_name"] = team_name
            stats_list = team_block.get("statistics", []) if isinstance(team_block, dict) else (team_block if isinstance(team_block, list) else [])
            for s in stats_list:
                stype = s.get("type", "")
                mapped = stat_key_map.get(stype)
                if mapped:
                    val = s.get("value")
                    # Handle percentage strings like "65%"
                    if isinstance(val, str) and val.endswith("%"):
                        try:
                            val = int(val.replace("%", ""))
                        except ValueError:
                            val = None
                    elif val is not None:
                        try:
                            val = int(val) if isinstance(val, (int, float)) and float(val) == int(float(val)) else float(val)
                        except (ValueError, TypeError):
                            pass
                    result[label][mapped] = val

        return result

    @staticmethod
    def parse_fixture_events(raw_events: List[Dict]) -> Dict:
        """Parse /fixtures/events response into structured event lists.

        Returns dict with:
          goals: [{time, team, player, assist, detail}]
          cards: [{time, team, player, card_type, detail}]
          substitutions: [{time, team, player_in, player_out}]
          red_card_events: [{time, team, player}]  -- for easy access
        """
        goals = []
        cards = []
        substitutions = []
        red_card_events = []

        for ev in raw_events:
            ev_time = (ev.get("time") or {}).get("elapsed")
            ev_extra = (ev.get("time") or {}).get("extra")
            team_name = (ev.get("team") or {}).get("name", "")
            player_name = (ev.get("player") or {}).get("name", "")
            assist_name = (ev.get("assist") or {}).get("name")
            ev_type = ev.get("type", "")
            ev_detail = ev.get("detail", "")

            time_str = str(ev_time) if ev_time else "?"
            if ev_extra:
                time_str += f"+{ev_extra}"

            if ev_type == "Goal":
                goals.append({
                    "time": time_str, "team": team_name,
                    "player": player_name, "assist": assist_name,
                    "detail": ev_detail,
                })
            elif ev_type == "Card":
                card_type = "Amarelo" if "Yellow" in ev_detail else "Vermelho"
                cards.append({
                    "time": time_str, "team": team_name,
                    "player": player_name, "card_type": card_type,
                    "detail": ev_detail,
                })
                if "Red" in ev_detail:
                    red_card_events.append({
                        "time": time_str, "team": team_name,
                        "player": player_name,
                    })
            elif ev_type == "subst":
                substitutions.append({
                    "time": time_str, "team": team_name,
                    "player_in": assist_name or "",
                    "player_out": player_name,
                })

        return {
            "goals": goals,
            "cards": cards,
            "substitutions": substitutions,
            "red_card_events": red_card_events,
        }

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
        """Fetch pre-match odds for a fixture (handles pagination).

        Returns bookmaker odds for multiple markets (1X2, O/U, BTTS, etc.).
        API-Football paginates odds at 10 results per page.
        """
        params: Dict[str, str] = {"fixture": str(fixture_id)}
        data = self._get_sync("odds", params, ttl_minutes=ttl_minutes)
        results = data.get("response", [])

        # Handle pagination (odds endpoint paginates at 10/page)
        paging = data.get("paging", {})
        total_pages = paging.get("total", 1)
        if total_pages > 1:
            for page in range(2, min(total_pages + 1, 6)):  # Cap at 5 pages
                params["page"] = str(page)
                page_data = self._get_sync("odds", params, ttl_minutes=ttl_minutes)
                results.extend(page_data.get("response", []))

        return results

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

                    # Cards / Bookings Over/Under (#095)
                    elif "booking" in bet_name or "card" in bet_name:
                        for v in values:
                            val = str(v.get("value", "")).lower()
                            odd = _safe_float(v.get("odd"))
                            if not odd:
                                continue
                            for line in ("2.5", "3.5", "4.5", "5.5"):
                                key_sfx = line.replace(".", "")  # "25", "35", ...
                                if f"over {line}" in val and f"cards_over_{key_sfx}" not in result:
                                    result[f"cards_over_{key_sfx}"] = odd
                                elif f"under {line}" in val and f"cards_under_{key_sfx}" not in result:
                                    result[f"cards_under_{key_sfx}"] = odd

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
                # Guard: if score key exists but is None (e.g. FootyStats had no goal data),
                # replace it with a fresh dict instead of crashing on None["home"].
                if not isinstance(record.get("score"), dict):
                    record["score"] = {}
                record["score"]["home"] = live["goals_home"]
                record["score"]["away"] = live["goals_away"]
                if live["halftime_home"] is not None:
                    if not isinstance(record["score"].get("halftime"), dict):
                        record["score"]["halftime"] = {}
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

        # Overlay corners from API-Football live data (#068)
        if live.get("home_corners") is not None and live.get("away_corners") is not None:
            record["currentCorners"] = live["home_corners"] + live["away_corners"]
        elif live.get("home_corners") is not None:
            record["currentCorners"] = live["home_corners"]

        # Overlay venue/stadium when FootyStats didn't provide it
        if not record.get("stadium"):
            venue = fixture.get("fixture", {}).get("venue", {}) or {}
            venue_name = venue.get("name", "")
            if venue_name:
                record["stadium"] = venue_name

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
        """Unified method: finds the fixture, extracts live data, league info,
        and fetches injuries + statistics + events via asyncio.gather.

        Includes coverage check: only calls /injuries if the league supports it.
        Statistics and events are fetched in parallel (timeout 8s) for live/finished matches.
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
                "home_corners": None,
                "away_corners": None,
                "home_possession": None,
                "away_possession": None,
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
            "match_statistics": {},
            "match_events": {},
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

        injuries: List[Dict] = []
        match_statistics: Dict = {}
        match_events: Dict = {}
        fixture_id = live_data.get("fixture_id")
        fx_league_id = league_info.get("league_id")
        fx_season = league_info.get("league_season") or season or date.today().year

        if fixture_id and (live_data.get("is_live") or live_data.get("is_finished")):
            # ----------------------------------------------------------
            # Parallel fetch: statistics + events + injuries via asyncio.gather
            # Graceful degradation: each task is wrapped in try/except
            # ----------------------------------------------------------
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

            async def _fetch_statistics() -> List[Dict]:
                try:
                    return await asyncio.wait_for(
                        self.get_fixture_statistics_async(fixture_id),
                        timeout=8.0,
                    )
                except Exception as e:
                    logger.error(f"[api-football] Statistics fetch failed for fixture {fixture_id}: {e}")
                    return []

            async def _fetch_events() -> List[Dict]:
                try:
                    return await asyncio.wait_for(
                        self.get_fixture_events_async(fixture_id),
                        timeout=8.0,
                    )
                except Exception as e:
                    logger.error(f"[api-football] Events fetch failed for fixture {fixture_id}: {e}")
                    return []

            async def _fetch_injuries() -> List[Dict]:
                if not should_fetch_injuries:
                    return []
                try:
                    return await asyncio.wait_for(
                        self.get_injuries(fixture_id),
                        timeout=8.0,
                    )
                except Exception as e:
                    logger.warning(f"[api-football] Injuries fetch failed for fixture {fixture_id}: {e}")
                    return []

            raw_stats, raw_events, injuries = await asyncio.gather(
                _fetch_statistics(),
                _fetch_events(),
                _fetch_injuries(),
            )

            # Parse the raw responses
            if raw_stats:
                match_statistics = self.parse_fixture_statistics(raw_stats)
            if raw_events:
                match_events = self.parse_fixture_events(raw_events)

            # Enrich live_data with possession from detailed statistics
            home_stats = match_statistics.get("home", {})
            away_stats = match_statistics.get("away", {})
            if home_stats.get("possession") is not None:
                live_data["home_possession"] = home_stats["possession"]
            if away_stats.get("possession") is not None:
                live_data["away_possession"] = away_stats["possession"]
            # Update corners from detailed stats if inline stats were missing
            if live_data.get("home_corners") is None and home_stats.get("corner_kicks") is not None:
                live_data["home_corners"] = home_stats["corner_kicks"]
            if live_data.get("away_corners") is None and away_stats.get("corner_kicks") is not None:
                live_data["away_corners"] = away_stats["corner_kicks"]

        elif fixture_id:
            # Pre-match: only fetch injuries (no stats/events yet)
            should_fetch_injuries = True
            if fx_league_id:
                try:
                    has_coverage = self.has_injury_coverage(fx_league_id, fx_season)
                    if not has_coverage:
                        should_fetch_injuries = False
                except Exception:
                    pass
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
            "match_statistics": match_statistics,
            "match_events": match_events,
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
                "leagueId": league_id,
                "leagueName": league_data.get("name", ""),
                "country": league_data.get("country", ""),
                "status": status,
                "datetime": dt_str,
                "timestamp": timestamp,
                "venue": venue_name,
                "stadium": venue_name,
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

        # Corner info (available for live and finished matches)
        home_corners = live_data.get("home_corners")
        away_corners = live_data.get("away_corners")
        corner_str = ""
        if home_corners is not None and away_corners is not None:
            total = home_corners + away_corners
            corner_str = f", Escanteios: {home_corners}+{away_corners}={total}"

        # Possession info
        home_poss = live_data.get("home_possession")
        away_poss = live_data.get("away_possession")
        poss_str = ""
        if home_poss is not None and away_poss is not None:
            poss_str = f", Posse: {home_poss}%x{away_poss}%"

        if live_data.get("is_live") and minute is not None:
            extra = live_data.get("extra_time")
            minute_str = f"{minute}"
            if extra:
                minute_str += f"+{extra}"
            return f"{status_desc}: {minute_str} min, Placar: {score}{poss_str}{corner_str}"
        elif live_data.get("is_finished"):
            return f"{status_desc}. Placar final: {score}{poss_str}{corner_str}"
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
