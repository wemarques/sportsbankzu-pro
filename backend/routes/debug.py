"""#166 — Odds ingestion diagnostic endpoint.
#170 — Corners model structural gap diagnostic (Fase 1).

Registered only when ODDS_INGESTION_V2=true (see main.py). Requires
X-Debug-Key header matching ODDS_DEBUG_KEY env var — blocks anonymous
access even when the flag is on.
"""
from __future__ import annotations

import os
import time
from fastapi import APIRouter, Header, HTTPException
from typing import Optional, List, Tuple

from backend.services.api_football_client import APIFootballClient

router = APIRouter(prefix="/api/debug", tags=["debug"])
_afc = APIFootballClient()


def _pearson(xs: list, ys: list) -> Optional[float]:
    """Simple Pearson correlation; returns None if insufficient / constant data."""
    pairs = [(float(x), float(y)) for x, y in zip(xs, ys)
             if x is not None and y is not None]
    n = len(pairs)
    if n < 3:
        return None
    xs2, ys2 = zip(*pairs)
    mx = sum(xs2) / n
    my = sum(ys2) / n
    num = sum((xs2[i] - mx) * (ys2[i] - my) for i in range(n))
    dx = sum((xs2[i] - mx) ** 2 for i in range(n))
    dy = sum((ys2[i] - my) ** 2 for i in range(n))
    if dx == 0 or dy == 0:
        return None
    return round(num / (dx ** 0.5 * dy ** 0.5), 4)


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


@router.get("/corners-diagnostic")
def corners_diagnostic(
    league: str,
    x_debug_key: Optional[str] = Header(default=None, alias="X-Debug-Key"),
) -> dict:
    """#170 Fase 1 — empirical diagnostic for corners model gaps.

    Computes 4 metrics from CACHE ONLY (no live FootyStats calls):
    1A  coverage of home_advantage_attack
    1B  correlations of homeAttackAdvantage vs existing team-level features
    1C  home vs away corners correlation per match
    1D  empirical variance vs NB2-predicted variance ratio

    Query: ?league=mls  (internal slug or alias)
    Header: X-Debug-Key: <ODDS_DEBUG_KEY>
    """
    _require_debug_key(x_debug_key)
    t0 = time.time()
    notes: List[str] = []

    from backend.config.leagues_config import LEAGUE_ID_ALIASES, get_league_config
    from backend.services.footstats_client import FootyStatsClient

    resolved = LEAGUE_ID_ALIASES.get(league, league)
    cfg = get_league_config(resolved)
    if not cfg:
        raise HTTPException(404, f"unknown league: {league}")

    client = FootyStatsClient()

    # ── Season resolution from cache (league-list, ttl 24h) ───────────
    # _request adds params["key"] = api_key before hashing, so mirror it.
    # If league-list not cached, we cannot resolve season_id → skip everything.
    list_params = {"key": client.api_key}
    list_key = client._generate_cache_key("league-list", list_params)
    list_data = client._get_from_cache(list_key, max_age_minutes=999999)
    season_id: Optional[int] = None
    if list_data and list_data.get("data"):
        # Match league-list entry by country + name (case-insensitive)
        target_country = (cfg["country"] or "").lower()
        target_names = {(cfg["name"] or "").lower(), *[
            a.lower() for a in (cfg.get("alt_names") or [])
        ]}
        latest_year = -1
        for entry in list_data["data"]:
            country = (entry.get("country") or "").lower()
            name = (entry.get("name") or entry.get("league_name") or "").lower()
            if country != target_country or name not in target_names:
                continue
            # pick newest season from this league's seasons array
            for s in entry.get("season", []) or []:
                year = int(s.get("year", 0) or 0)
                sid = s.get("id")
                if sid and year > latest_year:
                    latest_year = year
                    season_id = int(sid)
    else:
        notes.append("league-list not in cache — season resolution skipped")

    result: dict = {
        "league_id": resolved,
        "league_name": cfg["name"],
        "season_id": season_id,
        "coverage": None,           # 1A
        "correlations": None,       # 1B
        "home_away_corr": None,     # 1C
        "nb2_dispersion": None,     # 1D
        "notes": notes,
    }

    if season_id is None:
        if not any("league-list" in n for n in notes):
            notes.append("No matching season in league-list for this league")
        result["elapsed_ms"] = int((time.time() - t0) * 1000)
        return result

    # ── 1A + 1B: league-teams cache ───────────────────────────────────
    teams_params = {"season_id": season_id, "include": "stats", "key": client.api_key}
    teams_key = client._generate_cache_key("league-teams", teams_params)
    teams_data = client._get_from_cache(teams_key, max_age_minutes=999999)
    if teams_data is None:
        notes.append("league-teams not in cache — 1A+1B skipped")
    else:
        teams = teams_data.get("data", []) or []
        haa_col: list = []
        shots_col: list = []
        poss_col: list = []
        xg_col: list = []
        corners_col: list = []
        total_teams = 0
        for t in teams:
            if not isinstance(t, dict):
                continue
            total_teams += 1
            # FootyStats primary keys first, with fallbacks matching data_mapper.py
            stats = t.get("stats") if isinstance(t.get("stats"), dict) else t
            haa = stats.get("homeAttackAdvantage")
            if haa is None:
                haa = stats.get("homeAttackAdvantagePercentage")
            haa_col.append(haa)
            shots_col.append(
                stats.get("shotsAVG_overall")
                or stats.get("shots_per_match_overall")
                or stats.get("shotsAVG")
                or stats.get("shots_per_match")
            )
            poss_col.append(
                stats.get("possessionAVG_overall")
                or stats.get("average_possession_overall")
                or stats.get("possessionAVG")
            )
            xg_col.append(
                stats.get("xg_for_avg_overall")
                or stats.get("xgForAVG_overall")
                or stats.get("xg_for_avg")
            )
            corners_col.append(
                stats.get("cornersAVG_overall")
                or stats.get("corners_per_match_overall")
                or stats.get("cornersAVG")
            )
        with_data = sum(1 for v in haa_col if v is not None)
        coverage_pct = round(100.0 * with_data / total_teams, 1) if total_teams else 0.0
        result["coverage"] = {
            "total_teams": total_teams,
            "teams_with_data": with_data,
            "coverage_pct": coverage_pct,
        }
        corrs = {
            "shots": _pearson(haa_col, shots_col),
            "possession": _pearson(haa_col, poss_col),
            "xg": _pearson(haa_col, xg_col),
            "corners": _pearson(haa_col, corners_col),
        }
        redundant = any(c is not None and abs(c) > 0.7 for c in corrs.values())
        result["correlations"] = {"pairs": corrs, "redundant": redundant}

    # ── 1C + 1D: league-matches cache (walk pages until miss) ─────────
    pairs: List[Tuple[int, int]] = []
    pages_hit = 0
    for page in range(1, 11):
        m_params = {
            "season_id": season_id,
            "page": page,
            "max_per_page": 1000,
            "key": client.api_key,
        }
        m_key = client._generate_cache_key("league-matches", m_params)
        cached = client._get_from_cache(m_key, max_age_minutes=999999)
        if cached is None:
            break
        pages_hit += 1
        for m in cached.get("data", []) or []:
            a = m.get("team_a_corners")
            b = m.get("team_b_corners")
            try:
                ai, bi = int(a), int(b)
            except (TypeError, ValueError):
                continue
            if ai < 0 or bi < 0:
                continue
            pairs.append((ai, bi))

    if pages_hit == 0:
        notes.append("league-matches not in cache — 1C+1D skipped")
    elif len(pairs) < 10:
        notes.append(f"only {len(pairs)} finished matches with corner data — 1C+1D skipped")
    else:
        homes = [p[0] for p in pairs]
        aways = [p[1] for p in pairs]
        totals = [p[0] + p[1] for p in pairs]
        n = len(pairs)

        # 1C — home × away correlation
        r_ha = _pearson(homes, aways)
        result["home_away_corr"] = {
            "n_matches": n,
            "correlation": r_ha,
            "bivariate_potential": r_ha is not None and r_ha < -0.15,
        }

        # 1D — empirical variance vs NB2 method-of-moments alpha fit
        mean_total = sum(totals) / n
        var_total = sum((v - mean_total) ** 2 for v in totals) / (n - 1) if n > 1 else 0.0
        if var_total > mean_total and mean_total > 0:
            alpha_fit = (var_total - mean_total) / (mean_total ** 2)
        else:
            alpha_fit = 0.0  # degenerate → Poisson
        nb2_var_predicted = mean_total + alpha_fit * (mean_total ** 2)
        ratio = round(var_total / nb2_var_predicted, 3) if nb2_var_predicted > 0 else None
        result["nb2_dispersion"] = {
            "n_matches": n,
            "empirical_mean": round(mean_total, 3),
            "empirical_variance": round(var_total, 3),
            "nb2_variance_predicted": round(nb2_var_predicted, 3),
            "alpha_fit": round(alpha_fit, 4),
            "ratio_empirical_to_predicted": ratio,
            "note": "ratio > 1.1 → NB2 underestimates; < 0.9 → overestimates",
        }

    result["elapsed_ms"] = int((time.time() - t0) * 1000)
    return result
