from typing import List, Dict, Any
from backend.main import load_fixtures_from_csv

class MatchService:
    async def get_matches(self, league: str, date: str = "today") -> List[Dict[str, Any]]:
        return load_fixtures_from_csv(league, date)

    async def get_match_by_id(self, match_id: str) -> Dict[str, Any]:
        return {"id": match_id}

    async def create_match(self, match: dict) -> Dict[str, Any]:
        return {"ok": True, "match": match}
