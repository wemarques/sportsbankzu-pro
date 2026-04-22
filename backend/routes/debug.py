"""#166 — Odds ingestion diagnostic endpoint.

Registered only when ODDS_INGESTION_V2=true (see main.py). Requires
X-Debug-Key header matching ODDS_DEBUG_KEY env var — blocks anonymous
access even when the flag is on.
"""
from __future__ import annotations

import os
import time
from fastapi import APIRouter, Header, HTTPException
from typing import Optional

from backend.services.api_football_client import api_football_client as _afc

router = APIRouter(prefix="/api/debug", tags=["debug"])


def _require_debug_key(header_key: Optional[str]) -> None:
    expected = os.getenv("ODDS_DEBUG_KEY", "")
    if not expected:
        raise HTTPException(503, "ODDS_DEBUG_KEY not configured")
    if not header_key or header_key != expected:
        raise HTTPException(401, "invalid X-Debug-Key")


@router.get("/odds-coverage")
def odds_coverage(
    fixture_id: int,
    league_id: str = "",
    x_debug_key: Optional[str] = Header(default=None, alias="X-Debug-Key"),
) -> dict:
    """Per-bookmaker odds coverage report for a single fixture.

    Query: ?fixture_id=12345&league_id=mls
    Header: X-Debug-Key: <ODDS_DEBUG_KEY>
    """
    _require_debug_key(x_debug_key)
    if not _afc.is_configured:
        raise HTTPException(503, "API-Football not configured")
    t0 = time.time()
    odds_response = _afc.get_odds(int(fixture_id), ttl_minutes=5)
    if not odds_response:
        return {
            "fixture_id": fixture_id,
            "league_id": league_id or None,
            "total_bookmakers": 0,
            "bookmakers": [],
            "extracted": {},
            "missing": ["home", "over_25", "btts_yes"],
            "source_bookmaker": None,
            "elapsed_ms": int((time.time() - t0) * 1000),
        }

    per_bk = []
    for entry in odds_response:
        for bk in entry.get("bookmakers", []):
            bets = bk.get("bets", [])
            names = [(b.get("name") or "").lower() for b in bets]
            per_bk.append({
                "name": bk.get("name"),
                "bets_count": len(bets),
                "has_1x2": any("match winner" in n or n == "1x2" for n in names),
                "has_ou": any(
                    ("over/under" in n or "goals" in n)
                    and "corner" not in n
                    and "card" not in n
                    and "booking" not in n
                    for n in names
                ),
                "has_btts": any("both teams" in n or "btts" in n for n in names),
            })

    extracted = _afc.extract_best_odds(odds_response, league_id=league_id)
    essentials = ["home", "over_25", "btts_yes"]
    missing = [k for k in essentials if k not in extracted]
    return {
        "fixture_id": fixture_id,
        "league_id": league_id or None,
        "total_bookmakers": sum(len(e.get("bookmakers", [])) for e in odds_response),
        "bookmakers": per_bk,
        "extracted": extracted,
        "missing": missing,
        "source_bookmaker": extracted.get("bookmaker"),
        "elapsed_ms": int((time.time() - t0) * 1000),
    }
