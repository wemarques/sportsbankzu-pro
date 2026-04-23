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

router = APIRouter(prefix="/api/debug", tags=["debug"])

# Lazy singletons — avoid eager instantiation at module import time.
# Clients read env vars + open SQLite caches on __init__, so lazy keeps
# module import cheap and matches the pattern used elsewhere in the code.
_afc_singleton = None
_fsc_singleton = None


def _get_afc():
    global _afc_singleton
    if _afc_singleton is None:
        from backend.services.api_football_client import APIFootballClient
        _afc_singleton = APIFootballClient()
    return _afc_singleton


def _get_fsc():
    global _fsc_singleton
    if _fsc_singleton is None:
        from backend.services.footstats_client import FootyStatsClient
        _fsc_singleton = FootyStatsClient()
    return _fsc_singleton


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
    afc = _get_afc()
    if not afc.is_configured:
        raise HTTPException(503, "API-Football not configured")
    t0 = time.time()
    odds_response = afc.get_odds(int(fixture_id), ttl_minutes=5)
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

    extracted = afc.extract_best_odds(odds_response, league_id=league_id)
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

    Uses FootyStatsClient PUBLIC methods (get_league_list, get_league_teams,
    get_league_matches). Each method is cache-backed internally (24h/6h/2h
    TTL). A fresh call happens only on expiry, which is acceptable for a
    permanent endpoint.

    Metrics:
    1A  coverage of home_advantage_attack across teams in the league
    1B  Pearson(homeAttackAdvantage, {shots, possession, xg, corners});
        redundant=true if any |r|>0.7 (multicollinearity)
    1C  Pearson(team_a_corners, team_b_corners) across finished matches;
        bivariate_potential=true if r<-0.15
    1D  empirical variance vs NB2 variance predicted using PRODUCTION
        alpha (predictor._get_alpha), not alpha fitted from the same data.
        Ratio > 1.1 → NB2 under-dispersed, < 0.9 → over-dispersed.

    Query: ?league=mls  (internal slug or alias)
    Header: X-Debug-Key: <ODDS_DEBUG_KEY>
    """
    _require_debug_key(x_debug_key)
    t0 = time.time()
    notes: List[str] = []

    from backend.config.leagues_config import LEAGUE_ID_ALIASES, get_league_config

    resolved = LEAGUE_ID_ALIASES.get(league, league)
    cfg = get_league_config(resolved)
    if not cfg:
        raise HTTPException(404, f"unknown league: {league}")

    client = _get_fsc()

    # ── Season resolution via public resolve_season_ids (cached 24h) ──
    # Reuses the same matcher the rest of the codebase uses:
    # substring match on FootyStats league name (which embeds the country),
    # chosen_only=False, cup-filter, most-recent-first. Avoids our diagnostic
    # diverging from production matching logic.
    season_id: Optional[int] = None
    try:
        season_pairs = client.resolve_season_ids(
            cfg["country"], cfg["name"],
            alt_names=cfg.get("alt_names"), n_seasons=1,
        )
    except Exception as e:
        season_pairs = []
        notes.append(f"resolve_season_ids failed: {e}")
    if season_pairs:
        season_id = int(season_pairs[0][0])

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
        notes.append("No matching season found for this league in get_league_list")
        result["elapsed_ms"] = int((time.time() - t0) * 1000)
        return result

    # ── 1A + 1B: public get_league_teams (cached 6h) ──────────────────
    try:
        teams_resp = client.get_league_teams(season_id, include_stats=True)
    except Exception as e:
        teams_resp = None
        notes.append(f"get_league_teams failed: {e}")
    if not teams_resp or not teams_resp.get("data"):
        notes.append("league-teams returned no data — 1A+1B skipped")
    else:
        teams = teams_resp.get("data", []) or []
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

    # ── 1C + 1D: public get_league_matches per page (cached 2h) ───────
    pairs: List[Tuple[int, int]] = []
    pages_walked = 0
    for page in range(1, 11):
        try:
            page_resp = client.get_league_matches(season_id, page=page)
        except Exception as e:
            notes.append(f"get_league_matches page={page} failed: {e}")
            break
        if not page_resp or not page_resp.get("success"):
            break
        pages_walked += 1
        data = page_resp.get("data", []) or []
        for m in data:
            a = m.get("team_a_corners")
            b = m.get("team_b_corners")
            try:
                ai, bi = int(a), int(b)
            except (TypeError, ValueError):
                continue
            if ai < 0 or bi < 0:
                continue
            pairs.append((ai, bi))
        pager = page_resp.get("pager", {}) or {}
        if page >= pager.get("max_page", 1) or len(data) == 0:
            break

    if pages_walked == 0:
        notes.append("get_league_matches returned no pages — 1C+1D skipped")
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

        # 1D — empirical variance vs PRODUCTION NB2 variance.
        # Uses predictor._get_alpha (same alpha that evaluates live picks)
        # so ratio isn't tautological. alpha_empirical is also reported
        # for informational comparison.
        from backend.modeling.corners.predictor import _get_alpha
        mean_total = sum(totals) / n
        var_total = sum((v - mean_total) ** 2 for v in totals) / (n - 1) if n > 1 else 0.0
        alpha_prod = _get_alpha(resolved, mean_total)
        if var_total > mean_total and mean_total > 0:
            alpha_empirical = (var_total - mean_total) / (mean_total ** 2)
        else:
            alpha_empirical = 0.0
        nb2_var_prod = mean_total + alpha_prod * (mean_total ** 2)
        ratio = round(var_total / nb2_var_prod, 3) if nb2_var_prod > 0 else None
        result["nb2_dispersion"] = {
            "n_matches": n,
            "empirical_mean": round(mean_total, 3),
            "empirical_variance": round(var_total, 3),
            "alpha_production": round(alpha_prod, 4),
            "alpha_empirical": round(alpha_empirical, 4),
            "nb2_variance_production": round(nb2_var_prod, 3),
            "ratio_empirical_to_production": ratio,
            "note": "ratio > 1.1 → production NB2 under-dispersed; < 0.9 → over-dispersed",
        }

    result["elapsed_ms"] = int((time.time() - t0) * 1000)
    return result
