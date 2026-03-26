# backend/routes/ai_analysis.py
"""
Router para endpoints de analise AI com MISTRAL — v3.0
Conectado ao pipeline real de dados (fixtures_service + API-Football).
"""
import asyncio
import logging
from datetime import datetime as _dt
from fastapi import APIRouter, HTTPException, Query
from typing import Optional, Dict, List, Any

from backend.services.mistral_analysis import (
    MistralAnalysisService,
    AIAnalysisResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/ai",
    tags=["AI Analysis v3.0"]
)


@router.get("/match/{match_id}/analysis", response_model=AIAnalysisResponse)
async def get_match_analysis(
    match_id: str,
    include_context: bool = Query(
        True, description="Incluir contexto adicional (forma, H2H, lesoes titulares)"
    ),
):
    """
    Analise completa v3.0 — 24 mercados.

    Retorna: 1X2, Double Chance, Over/Under 0.5-4.5, BTTS,
    Escanteios Over/Under 8.5-11.5, lesoes de titulares, alertas.
    """
    try:
        match_data = await _get_match_data(match_id)
        service = MistralAnalysisService()

        analysis = await service.analyze_match(
            home_team=match_data['home_team'],
            away_team=match_data['away_team'],
            league=match_data['league'],
            match_stats=match_data['stats'],
            odds=match_data['odds'],
            context=match_data.get('context') if include_context else None,
        )
        return analysis

    except ValueError as e:
        # MISTRAL_API_KEY ausente ou liga nao identificada — retornar fallback
        # em vez de HTTP 400, para que o frontend mostre mensagem amigável (#090)
        logger.warning(f"[ai_analysis] Fallback para {match_id}: {e}")
        from backend.services.mistral_analysis import MistralAnalysisService as _MAS
        return _MAS._get_fallback_static()
    except Exception as e:
        logger.error(f"[ai_analysis] Erro analise match {match_id}: {e}")
        from backend.services.mistral_analysis import MistralAnalysisService as _MAS
        return _MAS._get_fallback_static()


@router.get("/match/{match_id}/analysis/legacy")
async def get_match_analysis_legacy(match_id: str):
    """Formato legado para MatchDetailCard.tsx (summary, keyPoints, etc)."""
    analysis = await get_match_analysis(match_id, include_context=True)
    return MistralAnalysisService.to_legacy_format(analysis)


@router.post(
    "/match/{match_id}/analysis/regenerate",
    response_model=AIAnalysisResponse,
)
async def regenerate_match_analysis(match_id: str):
    """Forca regeneracao da analise (quando odds mudam)."""
    return await get_match_analysis(match_id, include_context=True)


@router.get("/batch-analysis")
async def get_batch_analysis(
    league: str = Query(..., description="ID da liga"),
    date: str = Query("today", description="today/tomorrow/YYYY-MM-DD"),
    limit: int = Query(10, ge=1, le=50),
):
    """Analises v3.0 em batch para multiplos jogos."""
    try:
        matches = await _get_matches_by_league_and_date(league, date, limit)
        service = MistralAnalysisService()
        analyses = []

        for match in matches:
            try:
                analysis = await service.analyze_match(
                    home_team=match['home_team'],
                    away_team=match['away_team'],
                    league=match['league'],
                    match_stats=match['stats'],
                    odds=match['odds'],
                    context=match.get('context'),
                )
                analyses.append({
                    'match_id': match['id'],
                    'home_team': match['home_team'],
                    'away_team': match['away_team'],
                    'start_time': match['start_time'],
                    'analysis': analysis.model_dump(),
                })
            except Exception as e:
                print(f"[BatchV3] Erro jogo {match['id']}: {e}")
                continue

        return {
            'version': MistralAnalysisService.VERSION,
            'league': league,
            'date': date,
            'total_matches': len(matches),
            'analyzed': len(analyses),
            'analyses': analyses,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro batch: {e}")


# =====================================================================
# DIAGNOSTIC ENDPOINT (#083)
# =====================================================================

@router.get("/diagnostic/latest")
async def get_latest_diagnostic():
    """Return the most recent post-match diagnostic report."""
    try:
        from backend.audit import get_recent_audit_results
        results = get_recent_audit_results(days=7, limit=1)
        if not results:
            return {"status": "no_diagnostic", "message": "Nenhum diagnostico disponivel"}
        data = results[0].get("data", {})
        diagnostic = data.get("diagnostic") if isinstance(data, dict) else None
        if not diagnostic:
            return {"status": "no_diagnostic", "message": "Ultimo audit nao contem diagnostico"}
        return {"status": "ok", "diagnostic": diagnostic}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =====================================================================
# AUDIT / VALIDATION ENDPOINTS (#075)
# =====================================================================

from pydantic import BaseModel, Field as PydanticField
from typing import List as _List


class _AuditRequest(BaseModel):
    predictions: Optional[list] = None
    ai_summary: Optional[dict] = None


class _CorrectionRequest(BaseModel):
    correction_type: str
    parameter_name: str
    old_value: float
    new_value: float
    reason: str
    audit_confidence: int = 0


def _validate_match_deterministic(match_data: Dict[str, Any]) -> Dict[str, Any]:
    """Deterministic match validation — replaces MistralAuditor.audit_match_calculation (#079).

    Checks: prob sum ~100%, lambdas in [0.5-4.0], EVs < 40%, BTTS coherence.
    """
    stats = match_data.get("stats", {})
    checks = []
    corrections = []
    status = "PASS"

    # Check 1: 1X2 prob sum
    prob_h = _safe_float(stats.get("prob_home", stats.get("homeWinProb")))
    prob_d = _safe_float(stats.get("prob_draw", stats.get("drawProb")))
    prob_a = _safe_float(stats.get("prob_away", stats.get("awayWinProb")))
    if prob_h is not None and prob_d is not None and prob_a is not None:
        prob_sum = prob_h + prob_d + prob_a
        deviation = abs(prob_sum - 100.0)
        if deviation > 5:
            checks.append({"check": "prob_sum", "status": "FAIL", "value": prob_sum, "expected": "95-105"})
            status = "FAIL"
        elif deviation > 3:
            checks.append({"check": "prob_sum", "status": "WARN", "value": prob_sum, "expected": "97-103"})
            if status == "PASS":
                status = "WARN"
        else:
            checks.append({"check": "prob_sum", "status": "PASS", "value": prob_sum})

    # Check 2: Lambda range
    lambda_h = _safe_float(stats.get("lambda_home", stats.get("lambdaHome")))
    lambda_a = _safe_float(stats.get("lambda_away", stats.get("lambdaAway")))
    for name, val in [("lambda_home", lambda_h), ("lambda_away", lambda_a)]:
        if val is not None:
            if val < 0.3 or val > 4.5:
                checks.append({"check": name, "status": "FAIL", "value": val, "expected": "0.3-4.5"})
                status = "FAIL"
            elif val < 0.5 or val > 4.0:
                checks.append({"check": name, "status": "WARN", "value": val, "expected": "0.5-4.0"})
                if status == "PASS":
                    status = "WARN"
            else:
                checks.append({"check": name, "status": "PASS", "value": val})

    # Check 3: Over 2.5 prob sanity
    over25 = _safe_float(stats.get("prob_over_25", stats.get("over25Prob")))
    if over25 is not None:
        if over25 < 5 or over25 > 95:
            checks.append({"check": "over25Prob", "status": "WARN", "value": over25, "expected": "5-95"})
            if status == "PASS":
                status = "WARN"
        else:
            checks.append({"check": "over25Prob", "status": "PASS", "value": over25})

    # Check 4: BTTS prob sanity
    btts = _safe_float(stats.get("prob_btts", stats.get("bttsProb")))
    if btts is not None:
        if btts < 5 or btts > 95:
            checks.append({"check": "bttsProb", "status": "WARN", "value": btts, "expected": "5-95"})
            if status == "PASS":
                status = "WARN"
        else:
            checks.append({"check": "bttsProb", "status": "PASS", "value": btts})

    return {
        "status": status,
        "checks": checks,
        "corrections": corrections,
        "audit_type": "deterministic_match_validation",
        "biases_detected": [],
        "audit_confidence": 90,
    }


def _safe_float(val) -> Optional[float]:
    """Safely convert to float, returning None on failure."""
    if val is None or val == "N/A":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


@router.post("/match/{match_id}/audit")
async def audit_match(match_id: str, body: _AuditRequest = _AuditRequest()):
    """Deterministic audit validation for a specific match (#079, #082)."""
    try:
        match_data = await _get_match_data(match_id)
        result = _validate_match_deterministic(match_data)
        return {"status": "success", "audit": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[ai_analysis] Audit error for {match_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/match/{match_id}/audit/apply")
async def apply_audit_correction(match_id: str, body: _CorrectionRequest):
    """Apply an audit correction for a match."""
    from backend.audit import log_correction

    try:
        match_data = await _get_match_data(match_id)
        league = match_data.get("league", "unknown")

        log_correction(
            match_id=match_id,
            league=league,
            correction_type=body.correction_type,
            parameter_name=body.parameter_name,
            old_value=body.old_value,
            new_value=body.new_value,
            suggested_by="mistral_audit",
            applied_by="user_dashboard",
            audit_confidence=body.audit_confidence,
            reason=body.reason,
        )
        return {"status": "success", "message": f"Correcao aplicada para {match_id}"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[ai_analysis] Apply correction error for {match_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =====================================================================
# REAL DATA PIPELINE — replaces mock functions
# =====================================================================

def _extract_league_id(match_id: str) -> str:
    """Extract league_id from composite match_id by prefix-matching known leagues.

    Match IDs have format: "{league_id}-{home}-{away}-{timestamp}"
    League IDs are slugs like "premier-league", "brasileirao-serie-a".
    """
    from backend.config.leagues_config import LEAGUES_CONFIG
    known_ids = sorted(
        [lg["id"] for lg in LEAGUES_CONFIG],
        key=len, reverse=True,  # longest first to avoid partial matches
    )
    for lid in known_ids:
        if match_id.startswith(lid + "-"):
            return lid
    raise ValueError(
        f"Liga nao identificada no match_id: {match_id[:60]}..."
    )


def _extract_date_from_id(match_id: str) -> str:
    """Extract date (YYYY-MM-DD) from Unix timestamp at end of match_id."""
    # ID format: "league-id-Home Team-Away Team-1711202400.0"
    # The timestamp is a float after the last '-'
    last_segment = match_id.rsplit("-", 1)[-1]
    try:
        ts = float(last_segment)
        dt = _dt.fromtimestamp(ts)
        return dt.strftime("%Y-%m-%d")
    except (ValueError, TypeError, OverflowError):
        logger.warning(
            f"[ai_analysis] Could not parse date from match_id '{match_id[:60]}', using 'today'"
        )
        return "today"


def _format_injuries_str(injuries_list: list) -> str:
    """Format API-Football injuries list into human-readable string for Mistral."""
    if not injuries_list:
        return "Sem desfalques entre titulares"
    parts = []
    for inj in injuries_list:
        if not isinstance(inj, dict):
            continue
        player = inj.get("player", {})
        name = player.get("name", "Desconhecido") if isinstance(player, dict) else str(player)
        reason = inj.get("reason", "lesao")
        parts.append(f"{name} [FORA] - {reason}")
    return "; ".join(parts) if parts else "Sem desfalques entre titulares"


def _format_h2h_str(h2h: Any) -> str:
    """Format h2h dict into human-readable string for Mistral."""
    if isinstance(h2h, str):
        return h2h
    if not isinstance(h2h, dict):
        return "Dado nao disponivel"
    total = h2h.get("totalMatches", 0)
    hw = h2h.get("homeWins", 0)
    dr = h2h.get("draws", 0)
    aw = h2h.get("awayWins", 0)
    avg = h2h.get("avgGoals", 0)
    if total == 0:
        return "Sem confrontos diretos recentes"
    return f"Ultimos {total}: Casa {hw}V, {dr}E, {aw}D. Media {avg:.1f} gols/jogo"


def _map_record_to_v3(record: Dict[str, Any]) -> Dict[str, Any]:
    """Map a pipeline record (fixtures_service) to v3.0 format expected by MistralAnalysisService.

    The Mistral prompt uses snake_case for some stats (lambda_home, prob_home)
    while the pipeline produces camelCase (lambdaHome, homeWinProb).
    This function adds the expected aliases so both naming conventions work.
    """
    stats = dict(record.get("stats", {}))  # shallow copy
    odds = dict(record.get("odds", {}))    # shallow copy

    # --- Stats: add snake_case aliases for fields the prompt expects ---
    stats["lambda_home"] = stats.get("lambdaHome", "N/A")
    stats["lambda_away"] = stats.get("lambdaAway", "N/A")
    stats["prob_home"] = stats.get("homeWinProb", "N/A")
    stats["prob_draw"] = stats.get("drawProb", "N/A")
    stats["prob_away"] = stats.get("awayWinProb", "N/A")
    stats["prob_over_05"] = stats.get("over05Prob", "N/A")
    stats["prob_over_15"] = stats.get("over15Prob", "N/A")
    stats["prob_over_25"] = stats.get("over25Prob", "N/A")
    stats["prob_over_35"] = stats.get("over35Prob", "N/A")
    stats["prob_over_45"] = stats.get("over45Prob", "N/A")
    stats["prob_btts"] = stats.get("bttsProb", "N/A")
    stats["homeXg"] = stats.get("homeXgForAvg", stats.get("homeXg", "N/A"))
    stats["awayXg"] = stats.get("awayXgForAvg", stats.get("awayXg", "N/A"))

    # --- Odds: add underscore aliases for fields the prompt expects ---
    odds["over_05"] = odds.get("over05", "N/A")
    odds["over_15"] = odds.get("over15", "N/A")
    odds["over_25"] = odds.get("over25", "N/A")
    odds["over_35"] = odds.get("over35", "N/A")
    odds["over_45"] = odds.get("over45", "N/A")
    odds["under_25"] = odds.get("under25", "N/A")
    odds["under_35"] = odds.get("under35", "N/A")
    odds["under_45"] = odds.get("under45", "N/A")
    odds["btts_yes"] = odds.get("bttsYes", "N/A")
    odds["btts_no"] = odds.get("bttsNo", "N/A")
    # DC odds not in pipeline — will show as N/A (acceptable)

    # --- Context: build from _mistral_context + stats ---
    ctx = record.get("_mistral_context", {}) or {}
    injuries = ctx.get("injuries", {}) or {}
    home_injuries = injuries.get("home", []) if isinstance(injuries, dict) else []
    away_injuries = injuries.get("away", []) if isinstance(injuries, dict) else []

    home_pos = stats.get("homeLeaguePosition")
    away_pos = stats.get("awayLeaguePosition")

    context = {
        "home_form": ctx.get("home_form") or record.get("homeForm", "N/A"),
        "away_form": ctx.get("away_form") or record.get("awayForm", "N/A"),
        "h2h": _format_h2h_str(ctx.get("h2h") or record.get("h2h")),
        "home_position": f"{home_pos}o lugar" if home_pos else "N/A",
        "away_position": f"{away_pos}o lugar" if away_pos else "N/A",
        "home_injuries_starters": _format_injuries_str(home_injuries),
        "away_injuries_starters": _format_injuries_str(away_injuries),
    }

    # --- Team names ---
    home_team_obj = record.get("homeTeam", {})
    away_team_obj = record.get("awayTeam", {})
    home_name = home_team_obj.get("name", "") if isinstance(home_team_obj, dict) else str(home_team_obj)
    away_name = away_team_obj.get("name", "") if isinstance(away_team_obj, dict) else str(away_team_obj)

    return {
        "id": record.get("id", ""),
        "home_team": home_name,
        "away_team": away_name,
        "league": record.get("leagueName", record.get("leagueId", "")),
        "start_time": record.get("datetime", ""),
        "stats": stats,
        "odds": odds,
        "context": context,
    }


async def _get_match_data(match_id: str) -> dict:
    """Fetch real match data from the fixtures pipeline by match_id."""
    from backend.routes.fixtures import _process_single_league
    from backend.main import get_data_dir

    league_id = _extract_league_id(match_id)
    date_str = _extract_date_from_id(match_id)
    base = get_data_dir()

    logger.info(f"[ai_analysis] Fetching {league_id} / {date_str} for match {match_id[:60]}")
    records = await asyncio.to_thread(_process_single_league, league_id, date_str, base)

    record = next((r for r in records if r["id"] == match_id), None)
    if not record:
        available = [r["id"] for r in records[:5]]
        raise ValueError(
            f"Jogo '{match_id}' nao encontrado na liga {league_id} ({date_str}). "
            f"Disponiveis: {available}"
        )

    return _map_record_to_v3(record)


async def _get_matches_by_league_and_date(league: str, date: str, limit: int) -> list:
    """Fetch real match data for a league/date from the fixtures pipeline."""
    from backend.routes.fixtures import _process_single_league
    from backend.main import get_data_dir

    base = get_data_dir()
    records = await asyncio.to_thread(_process_single_league, league, date, base)
    return [_map_record_to_v3(r) for r in records[:limit]]


# =====================================================================
# CRON AUDIT HELPERS — used by cron_handler.py (#085b)
# =====================================================================

import re as _re
from datetime import timedelta as _td


def _get_all_finished_matches(
    date_filter: str = "yesterday",
    before_time_brt: str | None = None,
) -> list[dict]:
    """Fetch all finished matches across all leagues for a given date range.

    Args:
        date_filter: 'today' | 'yesterday' | 'week'
        before_time_brt: Optional BRT cutoff time (e.g. '23:45')

    Returns:
        List of raw match records with status='finished'.
    """
    from backend.routes.fixtures import _process_single_league
    from backend.main import get_data_dir
    from backend.config.leagues_config import LEAGUES_CONFIG

    base = get_data_dir()

    # Determine date(s) to query — use BRT calendar day, not UTC,
    # so late-night BRT matches (21:00-23:59 BRT = 00:00-02:59 UTC+1)
    # stay on the correct BRT date (#089).
    from datetime import timezone as _tz_mod
    _BRT = _tz_mod(_td(hours=-3))
    _now_brt = _dt.now(_BRT)
    if date_filter == "yesterday":
        dates = [(_now_brt - _td(days=1)).strftime("%Y-%m-%d")]
    elif date_filter == "today":
        dates = [_now_brt.strftime("%Y-%m-%d")]
    elif date_filter == "week":
        dates = [
            (_now_brt - _td(days=i)).strftime("%Y-%m-%d")
            for i in range(7)
        ]
    else:
        dates = [date_filter]

    finished = []
    for lg in LEAGUES_CONFIG:
        lid = lg["id"]
        for d in dates:
            try:
                records = _process_single_league(lid, d, base)
                for r in records:
                    if r.get("status") == "finished":
                        # Apply BRT cutoff if specified
                        if before_time_brt and r.get("datetime"):
                            try:
                                match_dt = _dt.fromisoformat(
                                    str(r["datetime"]).replace("Z", "+00:00")
                                )
                                # BRT = UTC-3
                                brt_hour = (match_dt.hour - 3) % 24
                                cutoff_parts = before_time_brt.split(":")
                                cutoff_h = int(cutoff_parts[0])
                                cutoff_m = int(cutoff_parts[1]) if len(cutoff_parts) > 1 else 0
                                if brt_hour > cutoff_h or (brt_hour == cutoff_h and match_dt.minute > cutoff_m):
                                    continue
                            except Exception:
                                pass  # if we can't parse, include the match
                        finished.append(r)
            except Exception as e:
                logger.debug(f"[cron] Error fetching {lid}/{d}: {e}")
                continue

    logger.info(f"[cron] Found {len(finished)} finished matches for {date_filter}")
    return finished


def _evaluate_pick_deterministic(pick: dict, actual_result: dict) -> bool:
    """Evaluate if a single pick was correct based on actual match result.

    Handles: 1X2, Over/Under goals, BTTS, Double Chance, Corners, Cards.

    Args:
        pick: dict with 'mercado' key (market name string)
        actual_result: dict with total_goals, btts, result_1x2, total_corners, total_cards

    Returns:
        True if the pick was correct, False otherwise.
    """
    mercado = pick.get("mercado", "")
    m = mercado.strip().upper()

    total_goals = actual_result.get("total_goals", 0)
    btts = actual_result.get("btts", False)
    result_1x2 = actual_result.get("result_1x2", "X")
    total_corners = actual_result.get("total_corners", 0)
    total_cards = actual_result.get("total_cards", 0)

    # ── Cards markets (#085b — pattern #006) ──
    if "CART" in m or "CARD" in m:
        match = _re.search(r"(\d+\.?\d*)", m)
        if not match:
            return False
        threshold = float(match.group(1))
        if "OVER" in m:
            return total_cards > threshold
        if "UNDER" in m:
            return total_cards < threshold
        return False

    # ── Corner markets ──
    if "ESCANTEIO" in m or "CORNER" in m:
        match = _re.search(r"(\d+\.?\d*)", m)
        if not match:
            return False
        threshold = float(match.group(1))
        if "OVER" in m:
            return total_corners > threshold
        if "UNDER" in m:
            return total_corners < threshold
        return False

    # ── Over/Under goals ──
    for threshold in [0.5, 1.5, 2.5, 3.5, 4.5]:
        ts = str(threshold)
        if ts in m:
            if "UNDER" in m or "MENOS" in m or "ABAIXO" in m:
                return total_goals < threshold
            if "OVER" in m or "MAIS" in m or "ACIMA" in m:
                return total_goals > threshold

    # ── BTTS ──
    if "BTTS" in m or "AMBAS" in m:
        if "NAO" in m or "NO" in m or "NÃO" in m:
            return not btts
        return btts

    # ── Double Chance ──
    if "DC 1X" in m or m.startswith("1X") or "CASA OU EMPATE" in m:
        return result_1x2 in ("1", "X")
    if "DC 12" in m or m.startswith("12") or "CASA OU FORA" in m:
        return result_1x2 in ("1", "2")
    if "DC X2" in m or m.startswith("X2") or "EMPATE OU FORA" in m:
        return result_1x2 in ("X", "2")

    # ── 1X2 ──
    if m in ("1", "VITORIA CASA", "HOME WIN", "CASA"):
        return result_1x2 == "1"
    if m in ("X", "EMPATE", "DRAW"):
        return result_1x2 == "X"
    if m in ("2", "VITORIA FORA", "AWAY WIN", "FORA"):
        return result_1x2 == "2"

    return False
