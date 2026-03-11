# backend/services/api_football_client.py
"""
Client for API-Football (v3) — https://v3.football.api-sports.io/
Provides live match status, scores, and injury/suspension data.
"""
import os
import logging
from typing import Dict, List, Optional
from datetime import date

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore

logger = logging.getLogger("sportsbankzu.services.api_football")

BASE_URL = "https://v3.football.api-sports.io"


class APIFootballClient:
    """Client for API-Football v3.

    Authentication via header ``x-apisports-key``.
    All endpoints use GET requests only.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("API_FOOTBALL_KEY", "")
        if not self.api_key:
            logger.warning("API_FOOTBALL_KEY not configured — API-Football calls will be skipped")
        self.base_url = BASE_URL
        self.timeout = 15.0

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> Dict[str, str]:
        return {"x-apisports-key": self.api_key}

    async def _get(self, endpoint: str, params: Dict) -> Dict:
        """Execute a GET request to the API-Football v3."""
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

            # API-Football wraps errors in an "errors" field
            errors = data.get("errors")
            if errors and (isinstance(errors, dict) and errors) or (isinstance(errors, list) and errors):
                logger.error(f"API-Football error on {endpoint}: {errors}")

            return data

    # ------------------------------------------------------------------
    # Fixture lookup — finds a match by team names + date
    # ------------------------------------------------------------------
    async def find_fixture(
        self,
        home_team: str,
        away_team: str,
        match_date: Optional[str] = None,
        league_id: Optional[int] = None,
        season: Optional[int] = None,
    ) -> Optional[Dict]:
        """Search for a fixture by team names and date.

        Returns the raw fixture object from the API response, or None.
        The fixture object contains:
            - fixture.id
            - fixture.status.short / .long / .elapsed
            - goals.home / goals.away
            - teams.home.name / teams.away.name
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

        # If we have a league, prefer that filter; otherwise search by date alone
        try:
            data = await self._get("fixtures", params)
        except Exception as e:
            logger.error(f"API-Football /fixtures error: {e}")
            return None

        fixtures = data.get("response", [])
        if not fixtures:
            logger.info(f"No fixtures found for date={params.get('date')}")
            return None

        # Match by team name similarity (case-insensitive substring)
        home_lower = home_team.lower()
        away_lower = away_team.lower()

        for fx in fixtures:
            teams = fx.get("teams", {})
            fx_home = (teams.get("home", {}).get("name") or "").lower()
            fx_away = (teams.get("away", {}).get("name") or "").lower()

            if (home_lower in fx_home or fx_home in home_lower) and \
               (away_lower in fx_away or fx_away in away_lower):
                return fx

        # Fallback: looser matching (check both orderings)
        for fx in fixtures:
            teams = fx.get("teams", {})
            fx_home = (teams.get("home", {}).get("name") or "").lower()
            fx_away = (teams.get("away", {}).get("name") or "").lower()

            # Sometimes team name ordering differs
            if (home_lower in fx_away or fx_away in home_lower) and \
               (away_lower in fx_home or fx_home in away_lower):
                logger.info("Found fixture with swapped team order")
                return fx

        logger.info(f"No fixture matched for {home_team} vs {away_team}")
        return None

    # ------------------------------------------------------------------
    # Extract structured live data from a fixture object
    # ------------------------------------------------------------------
    @staticmethod
    def extract_live_data(fixture: Dict) -> Dict:
        """Extract live match data from an API-Football fixture object.

        Returns:
            {
                "fixture_id": int,
                "status": "1H" | "HT" | "2H" | "FT" | "NS" | ...,
                "status_long": "First Half" | "Not Started" | ...,
                "minute": int | None,
                "extra_time": int | None,
                "score": "1 - 0" | "N/A",
                "goals_home": int | None,
                "goals_away": int | None,
                "is_live": bool,
                "is_finished": bool,
            }
        """
        fx = fixture.get("fixture", {})
        status_obj = fx.get("status", {})
        goals = fixture.get("goals", {})

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

        return {
            "fixture_id": fx.get("id"),
            "status": status_short,
            "status_long": status_obj.get("long", ""),
            "minute": elapsed,
            "extra_time": extra,
            "score": score_str,
            "goals_home": goals_home,
            "goals_away": goals_away,
            "is_live": status_short in live_statuses,
            "is_finished": status_short in finished_statuses,
        }

    # ------------------------------------------------------------------
    # Injuries / Suspensions
    # ------------------------------------------------------------------
    async def get_injuries(self, fixture_id: int) -> List[Dict]:
        """Fetch injuries/suspensions for a fixture.

        Returns a list of:
            {
                "player": "Player Name",
                "team": "Team Name",
                "type": "Missing Fixture" | "Questionable",
                "reason": "Injury description or 'Suspended'"
            }
        """
        try:
            data = await self._get("injuries", {"fixture": str(fixture_id)})
        except Exception as e:
            logger.error(f"API-Football /injuries error: {e}")
            return []

        raw_injuries = data.get("response", [])
        result = []
        for inj in raw_injuries:
            player_info = inj.get("player", {})
            team_info = inj.get("team", {})
            result.append({
                "player": player_info.get("name", "Unknown"),
                "team": team_info.get("name", "Unknown"),
                "type": player_info.get("type", "Unknown"),
                "reason": player_info.get("reason", "Unknown"),
            })

        return result

    # ------------------------------------------------------------------
    # High-level: fetch match + injuries in one call
    # ------------------------------------------------------------------
    async def get_match_live_data(
        self,
        home_team: str,
        away_team: str,
        match_date: Optional[str] = None,
        league_id: Optional[int] = None,
        season: Optional[int] = None,
    ) -> Dict:
        """Unified method: finds the fixture, extracts live data, and fetches injuries.

        Returns:
            {
                "live_data": { ... live match status ... },
                "injuries": [ ... ],
                "absences": "Formatted string of absences for AI context",
                "live_status": "Formatted string of live status for AI context",
            }
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
                "is_live": False,
                "is_finished": False,
            },
            "injuries": [],
            "absences": "Nenhuma informacao disponivel",
            "live_status": "Sem dados ao vivo disponiveis",
        }

        if not self.is_configured:
            logger.info("API-Football not configured, returning empty result")
            return empty_result

        # 1. Find the fixture
        fixture = await self.find_fixture(
            home_team, away_team, match_date,
            league_id=league_id, season=season,
        )
        if not fixture:
            return empty_result

        # 2. Extract live data
        live_data = self.extract_live_data(fixture)

        # 3. Fetch injuries using the fixture ID
        injuries = []
        fixture_id = live_data.get("fixture_id")
        if fixture_id:
            injuries = await self.get_injuries(fixture_id)

        # 4. Format absences string for AI context
        absences = self._format_absences(injuries, home_team, away_team)

        # 5. Format live status string for AI context
        live_status = self._format_live_status(live_data)

        return {
            "live_data": live_data,
            "injuries": injuries,
            "absences": absences,
            "live_status": live_status,
        }

    @staticmethod
    def _format_absences(injuries: List[Dict], home_team: str, away_team: str) -> str:
        """Format injuries into a readable string for AI context."""
        if not injuries:
            return "Nenhuma ausencia reportada pela API-Football."

        home_absences = []
        away_absences = []
        other_absences = []

        home_lower = home_team.lower()
        away_lower = away_team.lower()

        for inj in injuries:
            team = inj.get("team", "")
            player = inj.get("player", "Unknown")
            reason = inj.get("reason", "Unknown")
            inj_type = inj.get("type", "")

            entry = f"{player} ({reason})"
            if inj_type == "Questionable":
                entry += " [DUVIDA]"

            team_lower = team.lower()
            if home_lower in team_lower or team_lower in home_lower:
                home_absences.append(entry)
            elif away_lower in team_lower or team_lower in away_lower:
                away_absences.append(entry)
            else:
                other_absences.append(f"{entry} [{team}]")

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
