# backend/routes/ai_analysis.py
"""
Router para endpoints de analise AI com MISTRAL
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import logging
import os

from backend.services.mistral_analysis import MistralAnalysisService, AIAnalysisResponse

logger = logging.getLogger("sportsbank.routes.ai_analysis")

router = APIRouter(
    prefix="/api/ai",
    tags=["AI Analysis"],
)


@router.get("/match/{match_id}/analysis", response_model=AIAnalysisResponse)
async def get_match_analysis(
    match_id: str,
    home_team: str = Query(None, description="Nome do time da casa (para busca precisa)"),
    away_team: str = Query(None, description="Nome do time visitante (para busca precisa)"),
    include_context: bool = Query(True, description="Incluir contexto adicional (forma, H2H)"),
):
    """
    Retorna analise completa de um jogo usando MISTRAL AI.

    - **match_id**: ID do jogo
    - **home_team**: Nome do time da casa (opcional, para busca precisa)
    - **away_team**: Nome do time visitante (opcional, para busca precisa)
    - **include_context**: Se deve incluir contexto adicional na analise
    """
    try:
        match_data = _get_match_data(match_id, home_team=home_team, away_team=away_team)
        service = MistralAnalysisService()

        analysis = await service.analyze_match(
            home_team=match_data["home_team"],
            away_team=match_data["away_team"],
            league=match_data["league"],
            match_stats=match_data["stats"],
            odds=match_data["odds"],
            context=match_data.get("context") if include_context else None,
        )

        return analysis
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Dados invalidos: {str(e)}")
    except Exception as e:
        logger.error(f"Error generating analysis for match {match_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao gerar analise: {str(e)}")


@router.post("/match/{match_id}/analysis/regenerate", response_model=AIAnalysisResponse)
async def regenerate_match_analysis(match_id: str):
    """Forca regeneracao da analise AI para um jogo."""
    return await get_match_analysis(match_id, include_context=True)


class AuditRequest(BaseModel):
    predictions: Optional[List[dict]] = None  # System picks (SAFE/NEUTRO)
    ai_summary: Optional[dict] = None  # Mistral AI analysis summary


class CorrectionApplication(BaseModel):
    correction_type: str  # 'lambda_multiplier', 'threshold_adjustment', 'weight_adjustment'
    parameter_name: str
    old_value: float
    new_value: float
    reason: str
    audit_confidence: int = 0


@router.post("/match/{match_id}/audit")
async def audit_match(
    match_id: str,
    request: AuditRequest = None,
    home_team: str = Query(None),
    away_team: str = Query(None),
):
    """
    Audit a match's predictions vs actual results.
    - Scheduled matches: validates calculation consistency
    - Finished matches: compares system picks + Mistral analysis vs real result
    """
    from backend.ai.mistral_auditor import MistralAuditor
    from backend import audit as audit_db

    try:
        match_data = _get_match_data(match_id, home_team=home_team, away_team=away_team)
        # Ensure both camelCase and snake_case team name keys exist for auditor compatibility
        if "homeTeam" not in match_data and "home_team" in match_data:
            match_data["homeTeam"] = match_data["home_team"]
        if "awayTeam" not in match_data and "away_team" in match_data:
            match_data["awayTeam"] = match_data["away_team"]
        # Fallback to query params if neither key is populated
        if not match_data.get("homeTeam") and home_team:
            match_data["homeTeam"] = home_team
            match_data["home_team"] = home_team
        if not match_data.get("awayTeam") and away_team:
            match_data["awayTeam"] = away_team
            match_data["away_team"] = away_team
        auditor = MistralAuditor()

        # Get full match record to check status and extract actual result
        full_match = _get_full_match_record(match_id, home_team, away_team)
        match_status = full_match.get("status", "scheduled") if full_match else "scheduled"
        is_finished = match_status in ("finished", "complete", "ft")

        if is_finished and full_match:
            # Extract actual result from match data (FootyStats API fields)
            home_goals = full_match.get("home_team_goal_count") or full_match.get("homeGoals") or 0
            away_goals = full_match.get("away_team_goal_count") or full_match.get("awayGoals") or 0
            try:
                home_goals = int(home_goals)
                away_goals = int(away_goals)
            except (ValueError, TypeError):
                home_goals, away_goals = 0, 0
            total_goals = home_goals + away_goals
            btts = home_goals > 0 and away_goals > 0
            if home_goals > away_goals:
                result_1x2 = "1"
            elif home_goals == away_goals:
                result_1x2 = "X"
            else:
                result_1x2 = "2"

            actual_result = {
                "home_goals": home_goals,
                "away_goals": away_goals,
                "total_goals": total_goals,
                "btts": btts,
                "result_1x2": result_1x2,
                "score": f"{home_goals}x{away_goals}",
            }

            predictions = (request.predictions or []) if request else []
            ai_analysis = (request.ai_summary or {}) if request else {}

            # Include team names in stats dict for audit metadata
            audit_stats = dict(match_data.get("stats", {}))
            audit_stats["homeTeam"] = match_data.get("homeTeam", "")
            audit_stats["awayTeam"] = match_data.get("awayTeam", "")
            audit_result = auditor.audit_match_vs_result(
                match_data=audit_stats,
                predictions=predictions,
                ai_analysis=ai_analysis,
                actual_result=actual_result,
            )
        else:
            # Pre-match: validate calculation consistency
            audit_result = auditor.audit_match_calculation(match_data)

        # Store audit result
        audit_db.log_audit_result(
            match_id=match_id,
            league=match_data.get("league", ""),
            audit_data=audit_result,
            match_status="finished" if is_finished else "scheduled",
            user="user",
        )

        return {"status": "success", "audit": audit_result, "match_status": match_status}
    except Exception as e:
        logger.error(f"Audit error for match {match_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Erro na auditoria: {str(e)}")


@router.post("/match/{match_id}/audit/apply")
async def apply_audit_correction(match_id: str, correction: CorrectionApplication):
    """Apply a correction suggested by the audit."""
    from backend import audit as audit_db
    from datetime import datetime

    try:
        match_data = _get_match_data(match_id)

        audit_db.log_correction(
            match_id=match_id,
            league=match_data.get("league", ""),
            correction_type=correction.correction_type,
            parameter_name=correction.parameter_name,
            old_value=correction.old_value,
            new_value=correction.new_value,
            suggested_by="mistral_audit",
            applied_by="user",
            audit_confidence=correction.audit_confidence,
            reason=correction.reason,
        )

        # Apply threshold corrections immediately
        if correction.correction_type == "threshold_adjustment":
            _apply_threshold_correction(correction)

        return {
            "status": "success",
            "message": f"Correcao aplicada: {correction.parameter_name}",
            "old_value": correction.old_value,
            "new_value": correction.new_value,
        }
    except Exception as e:
        logger.error(f"Error applying correction for match {match_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao aplicar correcao: {str(e)}")


def _apply_threshold_correction(correction: CorrectionApplication):
    """Apply a threshold correction to the thresholds table."""
    from backend import audit as audit_db
    from datetime import datetime

    parts = correction.parameter_name.split(".")
    if len(parts) >= 2:
        market = parts[0] if len(parts) == 2 else parts[1]
        conn = audit_db.init_db()
        cursor = conn.cursor()
        if audit_db._use_postgres():
            cursor.execute(
                "UPDATE thresholds SET safe_threshold = %s, last_updated = %s WHERE market = %s",
                (correction.new_value, datetime.now(), market),
            )
        else:
            cursor.execute(
                "UPDATE thresholds SET safe_threshold = ?, last_updated = ? WHERE market = ?",
                (correction.new_value, datetime.now(), market),
            )
        conn.commit()
        conn.close()


def _get_full_match_record(match_id: str, home_team: str = None, away_team: str = None) -> dict | None:
    """Get the full raw match record including status and goals, without AI transformation."""
    try:
        from backend.routes.fixtures import fixtures as fixtures_endpoint
        league_id = _extract_league_id(match_id)
        for date_filter in ("today", "week"):
            if not league_id:
                break
            result = fixtures_endpoint(leagues=league_id, date=date_filter)
            for m in result.get("matches", []):
                if str(m.get("id")) == str(match_id):
                    return m
                if home_team and away_team:
                    h = str(m.get("homeTeam", ""))
                    a = str(m.get("awayTeam", ""))
                    if (home_team.lower() in h.lower() or h.lower() in home_team.lower()) and \
                       (away_team.lower() in a.lower() or a.lower() in away_team.lower()):
                        return m
    except Exception as e:
        logger.warning(f"Could not fetch full match record for {match_id}: {e}")
    return None


@router.get("/batch-analysis")
async def get_batch_analysis(
    league: str = Query("", description="ID da liga"),
    date: str = Query("today", description="Data dos jogos (today/tomorrow/YYYY-MM-DD)"),
    limit: int = Query(10, ge=1, le=50, description="Numero maximo de jogos"),
):
    """Retorna analises AI para multiplos jogos de uma liga."""
    try:
        matches = _get_matches_by_league_and_date(league, date, limit)
        service = MistralAnalysisService()
        analyses = []

        for match in matches:
            try:
                analysis = await service.analyze_match(
                    home_team=match["home_team"],
                    away_team=match["away_team"],
                    league=match["league"],
                    match_stats=match["stats"],
                    odds=match["odds"],
                    context=match.get("context"),
                )
                analyses.append(
                    {
                        "match_id": match["id"],
                        "home_team": match["home_team"],
                        "away_team": match["away_team"],
                        "start_time": match.get("start_time", ""),
                        "analysis": analysis.model_dump(),
                    }
                )
            except Exception as e:
                logger.error(f"Batch analysis failed for match {match['id']}: {e}")
                continue

        return {
            "league": league,
            "date": date,
            "total_matches": len(matches),
            "analyzed": len(analyses),
            "analyses": analyses,
        }
    except Exception as e:
        logger.error(f"Batch analysis error: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao gerar analises em batch: {str(e)}")


# ===== HELPER FUNCTIONS =====

def _extract_league_id(match_id: str) -> str:
    """Extract league ID from match_id format 'premier-league-mock-0'."""
    # Remove trailing '-mock-N' or '-m-N' suffix to get league id
    parts = match_id.rsplit("-mock-", 1)
    if len(parts) == 2:
        return parts[0]
    parts = match_id.rsplit("-m", 1)
    if len(parts) == 2 and parts[1].isdigit():
        return parts[0]
    # Fallback: try all known league prefixes
    from backend.config.leagues_config import LEAGUE_ID_ALIASES
    for alias in LEAGUE_ID_ALIASES:
        if match_id.startswith(alias):
            return alias
    return ""


def _match_to_ai_input(m: dict) -> dict:
    """Convert a fixtures match object to the dict expected by AI analysis."""
    stats = m.get("stats", {})
    home_form = stats.get("homeForm") or m.get("homeForm") or []
    away_form = stats.get("awayForm") or m.get("awayForm") or []
    h2h = m.get("h2h", {})

    # Enrich with FootyStats match details (gpt_en analysis, H2H, etc.)
    footystats_analysis = ""
    footystats_match_id = m.get("footystatsId")
    if footystats_match_id:
        try:
            from backend.services.footstats_client import FootyStatsClient
            client = FootyStatsClient()
            details = client.get_match_details(int(footystats_match_id))
            if details.get("success"):
                detail_data = details.get("data", {})
                footystats_analysis = detail_data.get("gpt_en", "") or ""
                # Extract real H2H data if available
                api_h2h = detail_data.get("h2h", {})
                if api_h2h and isinstance(api_h2h, dict):
                    prev = api_h2h.get("previous_matches_results", {})
                    betting = api_h2h.get("betting_stats", {})
                    h2h = {
                        "totalMatches": prev.get("totalMatches", 0),
                        "homeWins": prev.get("team_a_wins", 0),
                        "draws": prev.get("draw", 0),
                        "awayWins": prev.get("team_b_wins", 0),
                        "avgGoals": betting.get("avg_goals", 0),
                        "bttsPercentage": betting.get("bttsPercentage", 0),
                        "over25Percentage": betting.get("over25Percentage", 0),
                    }
        except Exception as e:
            logger.warning(f"Could not fetch match details for {footystats_match_id}: {e}")

    h2h_text = f"Total: {h2h.get('totalMatches', 0)} jogos, Casa: {h2h.get('homeWins', 0)}, Empates: {h2h.get('draws', 0)}, Fora: {h2h.get('awayWins', 0)}, Media gols: {h2h.get('avgGoals', 0)}"
    if h2h.get("bttsPercentage"):
        h2h_text += f", BTTS: {h2h['bttsPercentage']}%, Over 2.5: {h2h.get('over25Percentage', 0)}%"

    context = {
        "home_form": ", ".join(home_form) if isinstance(home_form, list) else str(home_form),
        "away_form": ", ".join(away_form) if isinstance(away_form, list) else str(away_form),
        "h2h": h2h_text,
    }
    if footystats_analysis:
        context["footystats_analysis"] = footystats_analysis

    home_name = m.get("homeTeam", "")
    away_name = m.get("awayTeam", "")
    return {
        "id": m.get("id"),
        "footystatsId": footystats_match_id,
        "home_team": home_name,
        "away_team": away_name,
        "homeTeam": home_name,
        "awayTeam": away_name,
        "league": m.get("leagueName", ""),
        "stats": stats,
        "odds": m.get("odds", {}),
        "context": context,
    }


def _get_match_data(match_id: str, home_team: str = None, away_team: str = None) -> dict:
    """Fetch match data from the fixtures system, falling back to mock."""
    try:
        from backend.routes.fixtures import fixtures as fixtures_endpoint

        # Extract league from match_id so the fixtures endpoint returns data
        league_id = _extract_league_id(match_id)

        # Try today first, then week as fallback
        for date_filter in ("today", "week"):
            if not league_id:
                break
            result = fixtures_endpoint(leagues=league_id, date=date_filter)
            # 1. Try exact ID match
            for m in result.get("matches", []):
                if str(m.get("id")) == str(match_id):
                    logger.info(f"Found match {match_id} via fixtures (date={date_filter})")
                    return _match_to_ai_input(m)

            # 2. Try matching by team names (handles ID format mismatches)
            if home_team and away_team:
                for m in result.get("matches", []):
                    h = str(m.get("homeTeam", ""))
                    a = str(m.get("awayTeam", ""))
                    if (home_team.lower() in h.lower() or h.lower() in home_team.lower()) and \
                       (away_team.lower() in a.lower() or a.lower() in away_team.lower()):
                        logger.info(f"Found match by team names: {h} vs {a} (date={date_filter})")
                        return _match_to_ai_input(m)

        # If no league could be extracted but we have team names, try all leagues
        if home_team and away_team and not league_id:
            from backend.config.leagues_config import LEAGUE_ID_ALIASES
            for alias in LEAGUE_ID_ALIASES:
                try:
                    result = fixtures_endpoint(leagues=alias, date="today")
                    for m in result.get("matches", []):
                        h = str(m.get("homeTeam", ""))
                        a = str(m.get("awayTeam", ""))
                        if (home_team.lower() in h.lower() or h.lower() in home_team.lower()) and \
                           (away_team.lower() in a.lower() or a.lower() in away_team.lower()):
                            logger.info(f"Found match by team names in {alias}: {h} vs {a}")
                            return _match_to_ai_input(m)
                except Exception:
                    continue

    except Exception as e:
        logger.warning(f"Could not fetch live fixtures for match {match_id}: {e}")

    # Fallback — use generic data with descriptive names instead of hardcoded mock
    logger.warning(f"Using fallback mock data for match {match_id}")
    fallback_home = home_team or "Home Team"
    fallback_away = away_team or "Away Team"
    return {
        "id": match_id,
        "home_team": fallback_home,
        "away_team": fallback_away,
        "homeTeam": fallback_home,
        "awayTeam": fallback_away,
        "league": "Unknown League",
        "stats": {
            "homeWinProb": 40.0,
            "drawProb": 30.0,
            "awayWinProb": 30.0,
            "avgGoals": 2.5,
            "bttsProb": 52.0,
            "lambdaHome": 1.3,
            "lambdaAway": 1.2,
        },
        "odds": {
            "home": 2.10,
            "draw": 3.30,
            "away": 3.40,
            "over25": 1.85,
            "bttsYes": 1.80,
        },
        "context": {
            "home_form": "Dados indisponiveis",
            "away_form": "Dados indisponiveis",
            "h2h": "Dados indisponiveis",
        },
    }


def _get_matches_by_league_and_date(league: str, date: str, limit: int) -> list:
    """Fetch matches from fixtures, fallback to week then mock."""
    try:
        from backend.routes.fixtures import fixtures as fixtures_endpoint

        # Try requested date first, then week as fallback
        for date_filter in (date, "week"):
            if not league:
                break
            result = fixtures_endpoint(leagues=league, date=date_filter)
            matches = []
            for m in result.get("matches", [])[:limit]:
                data = _match_to_ai_input(m)
                data["start_time"] = m.get("datetime", "")
                matches.append(data)
            if matches:
                return matches
    except Exception as e:
        logger.warning(f"Could not fetch fixtures for batch: {e}")

    return [_get_match_data("fallback-0")][:limit]


# ===== BATCH AUDIT =====

class BatchAuditRequest(BaseModel):
    date: str = "today"  # today / tomorrow / week / YYYY-MM-DD


class BatchCorrectionRequest(BaseModel):
    corrections: List[dict]  # List of corrections to apply


def _evaluate_pick_deterministic(pick: dict, actual_result: dict) -> bool:
    """Deterministic evaluation of a single pick against actual result.
    Returns True if the pick was correct, False otherwise."""
    mercado = str(pick.get("mercado", "")).strip().upper()
    total_goals = actual_result.get("total_goals", 0)
    btts = actual_result.get("btts", False)
    result_1x2 = actual_result.get("result_1x2", "")

    # Over/Under markets
    if "UNDER" in mercado or "MENOS" in mercado:
        for threshold in (0.5, 1.5, 2.5, 3.5, 4.5):
            if str(threshold) in mercado:
                return total_goals < threshold
    if "OVER" in mercado or "MAIS" in mercado or "ACIMA" in mercado:
        for threshold in (0.5, 1.5, 2.5, 3.5, 4.5):
            if str(threshold) in mercado:
                return total_goals > threshold

    # BTTS — handle "BTTS — SIM", "BTTS - SIM", "BTTS SIM", etc.
    if "BTTS" in mercado or "AMBAS" in mercado:
        if "SIM" in mercado or "YES" in mercado:
            return btts
        if "NAO" in mercado or "NO" in mercado or "NÃO" in mercado:
            return not btts
        # Bare "BTTS" without qualifier defaults to YES
        return btts

    # Double Chance — handle "DC 1X (ARS/EMP)" format with parentheses
    if mercado.startswith("DC 1X") or mercado.startswith("1X") or "CASA OU EMPATE" in mercado:
        return result_1x2 in ("1", "X")
    if mercado.startswith("DC 12") or mercado.startswith("12") or "CASA OU FORA" in mercado:
        return result_1x2 in ("1", "2")
    if mercado.startswith("DC X2") or mercado.startswith("X2") or "EMPATE OU FORA" in mercado:
        return result_1x2 in ("X", "2")

    # 1X2
    if mercado in ("1", "VITORIA CASA", "HOME WIN", "CASA"):
        return result_1x2 == "1"
    if mercado in ("X", "EMPATE", "DRAW"):
        return result_1x2 == "X"
    if mercado in ("2", "VITORIA FORA", "AWAY WIN", "FORA"):
        return result_1x2 == "2"

    # Unknown market — cannot evaluate
    logger.warning(f"Cannot evaluate unknown market: {mercado}")
    return False


def _get_all_finished_matches(date_filter: str, before_time_brt: str | None = None) -> list:
    """Fetch all finished matches across all leagues for the given date range.

    Args:
        date_filter: 'today' | 'yesterday' | 'week'
        before_time_brt: Optional cutoff time in BRT (HH:MM). When set, only matches
            that finished strictly before this BRT time are included. Used by the
            today_audit cron action (23:45 BRT) to audit European matches same-day.
    """
    from backend.routes.fixtures import fixtures as fixtures_endpoint
    from backend.config.leagues_config import LEAGUE_ID_ALIASES
    from datetime import timezone, timedelta

    BRT = timezone(timedelta(hours=-3))
    cutoff_hour, cutoff_min = (int(p) for p in before_time_brt.split(":")) if before_time_brt else (None, None)

    all_finished = []
    tried_leagues = set()

    for alias, resolved in LEAGUE_ID_ALIASES.items():
        if resolved in tried_leagues:
            continue
        tried_leagues.add(resolved)
        try:
            result = fixtures_endpoint(leagues=alias, date=date_filter)
            for m in result.get("matches", []):
                status = str(m.get("status", "")).lower()
                if status not in ("finished", "complete", "ft"):
                    continue

                # Apply BRT time cutoff when requested (Gap 1 — today_audit)
                if before_time_brt is not None:
                    try:
                        dt_str = m.get("datetime", "")
                        dt_utc = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                        dt_brt = dt_utc.astimezone(BRT)
                        if dt_brt.hour > cutoff_hour or (dt_brt.hour == cutoff_hour and dt_brt.minute >= cutoff_min):
                            continue  # Match after cutoff — skip
                    except Exception:
                        pass  # Cannot parse datetime → include the match

                all_finished.append(m)
        except Exception as e:
            logger.debug(f"Skipping league {alias} for batch audit: {e}")
            continue

    if before_time_brt:
        logger.info(f"[TODAY_AUDIT] {len(all_finished)} jogos finalizados antes das {before_time_brt} BRT")

    return all_finished


@router.post("/batch-audit")
async def batch_audit(
    request: BatchAuditRequest = None,
    date: str = Query("today", description="Date filter: today/tomorrow/week/YYYY-MM-DD"),
):
    """
    Audit ALL finished matches for the given date range.
    - Evaluates each pick deterministically (no AI call per match)
    - ONE Mistral call at the end for aggregate model evaluation
    """
    from backend.ai.mistral_auditor import MistralAuditor
    from backend import audit as audit_db

    date_filter = request.date if request and request.date else date

    try:
        # 1. Get all finished matches
        finished_matches = _get_all_finished_matches(date_filter)

        if not finished_matches:
            return {
                "status": "success",
                "total_matches": 0,
                "finished_matches": 0,
                "audited_matches": 0,
                "message": "Nenhum jogo finalizado encontrado para o periodo.",
                "match_results": [],
                "model_evaluation": None,
            }

        # 2. Evaluate each match deterministically
        match_results = []
        overall_correct = 0
        overall_total = 0
        safe_correct = 0
        safe_total = 0
        neutro_correct = 0
        neutro_total = 0
        market_stats = {}  # {market: {correct: int, total: int}}
        lambda_errors = []
        brier_scores = []

        for m in finished_matches:
            home = m.get("homeTeam", "")
            away = m.get("awayTeam", "")
            league = m.get("leagueName", m.get("leagueId", ""))
            score = m.get("score") or {}
            stats = m.get("stats", {})
            mercados = m.get("mercados", [])

            # Extract actual result
            home_goals = score.get("home", 0) if score else 0
            away_goals = score.get("away", 0) if score else 0

            # If score not from new field, try legacy fields
            if not score:
                home_goals = m.get("home_team_goal_count") or m.get("homeGoals") or 0
                away_goals = m.get("away_team_goal_count") or m.get("awayGoals") or 0
                try:
                    home_goals = int(home_goals)
                    away_goals = int(away_goals)
                except (ValueError, TypeError):
                    home_goals, away_goals = 0, 0

            total_goals = home_goals + away_goals
            btts = home_goals > 0 and away_goals > 0
            if home_goals > away_goals:
                result_1x2 = "1"
            elif home_goals == away_goals:
                result_1x2 = "X"
            else:
                result_1x2 = "2"

            actual_result = {
                "home_goals": home_goals,
                "away_goals": away_goals,
                "total_goals": total_goals,
                "btts": btts,
                "result_1x2": result_1x2,
            }

            # Evaluate picks
            picks_eval = []
            match_correct = 0
            match_total = 0

            for merc in mercados:
                merc_name = merc.get("mercado", merc.get("market", ""))
                merc_status = merc.get("status", merc.get("pick_type", "NEUTRO"))

                pick_dict = {"mercado": merc_name}
                is_correct = _evaluate_pick_deterministic(pick_dict, actual_result)

                picks_eval.append({
                    "mercado": merc_name,
                    "status_pick": merc_status,
                    "resultado": "ACERTOU" if is_correct else "ERROU",
                })

                match_total += 1
                overall_total += 1
                if is_correct:
                    match_correct += 1
                    overall_correct += 1

                # Track by pick status
                if merc_status == "SAFE":
                    safe_total += 1
                    if is_correct:
                        safe_correct += 1
                elif merc_status == "NEUTRO":
                    neutro_total += 1
                    if is_correct:
                        neutro_correct += 1

                # Track by market
                market_key = merc_name.upper().strip()
                if market_key not in market_stats:
                    market_stats[market_key] = {"correct": 0, "total": 0}
                market_stats[market_key]["total"] += 1
                if is_correct:
                    market_stats[market_key]["correct"] += 1

            # Lambda error calculation
            lambda_total = stats.get("lambdaTotal") or (
                (stats.get("lambdaHome") or 0) + (stats.get("lambdaAway") or 0)
            )
            if lambda_total and lambda_total > 0:
                lambda_errors.append(abs(lambda_total - total_goals))

            # Brier score (simplified: use over25Prob)
            over25_prob = stats.get("over25Prob")
            if over25_prob is not None:
                actual_over25 = 1 if total_goals > 2.5 else 0
                brier = (over25_prob / 100.0 - actual_over25) ** 2
                brier_scores.append(brier)

            match_results.append({
                "match_id": m.get("id", ""),
                "home_team": home,
                "away_team": away,
                "league": league,
                "score": f"{home_goals}x{away_goals}",
                "picks": picks_eval,
                "picks_correct": match_correct,
                "picks_total": match_total,
            })

        # 3. Aggregate metrics
        overall_accuracy_pct = (overall_correct / overall_total * 100.0) if overall_total > 0 else 0.0
        safe_accuracy_pct = (safe_correct / safe_total * 100.0) if safe_total > 0 else 0.0
        neutro_accuracy_pct = (neutro_correct / neutro_total * 100.0) if neutro_total > 0 else 0.0
        avg_brier = sum(brier_scores) / len(brier_scores) if brier_scores else 0.0
        avg_lambda_error = sum(lambda_errors) / len(lambda_errors) if lambda_errors else 0.0

        # Build market accuracy text for prompt
        market_accuracy_list = []
        market_accuracy_output = []
        for mkt, data in sorted(market_stats.items()):
            acc = (data["correct"] / data["total"] * 100.0) if data["total"] > 0 else 0.0
            market_accuracy_list.append(f"- {mkt}: {data['correct']}/{data['total']} ({acc:.1f}%)")
            market_accuracy_output.append({
                "market": mkt,
                "correct": data["correct"],
                "total": data["total"],
                "accuracy_pct": round(acc, 1),
            })

        # Build match summary text for prompt (abbreviated)
        matches_summary_lines = []
        for mr in match_results[:20]:  # Limit to 20 for prompt size
            picks_str = ", ".join(
                f"{p['mercado']}:{p['resultado']}" for p in mr["picks"]
            )
            matches_summary_lines.append(
                f"- {mr['home_team']} {mr['score']} {mr['away_team']} ({mr['league']}) | {picks_str}"
            )

        # 4. ONE Mistral call for aggregate model evaluation
        batch_summary = {
            "total_audited": len(match_results),
            "overall_correct": overall_correct,
            "overall_total": overall_total,
            "overall_accuracy_pct": overall_accuracy_pct,
            "safe_correct": safe_correct,
            "safe_total": safe_total,
            "safe_accuracy_pct": safe_accuracy_pct,
            "neutro_correct": neutro_correct,
            "neutro_total": neutro_total,
            "neutro_accuracy_pct": neutro_accuracy_pct,
            "avg_brier_score": avg_brier,
            "avg_lambda_error": avg_lambda_error,
            "market_accuracy_text": "\n".join(market_accuracy_list) if market_accuracy_list else "Sem dados de mercado",
            "matches_summary_text": "\n".join(matches_summary_lines) if matches_summary_lines else "Sem detalhes",
        }

        model_evaluation = None
        try:
            auditor = MistralAuditor()
            model_evaluation = auditor.evaluate_model_from_batch(batch_summary)
        except Exception as e:
            logger.error(f"Mistral batch evaluation failed: {e}")

        # 5. Store aggregate audit result
        # Determine user source: "cron" for EventBridge, "user" for manual
        _audit_user = "cron" if os.getenv("EVENTBRIDGE_TRIGGERED") else "user"
        try:
            audit_db.log_audit_result(
                match_id=f"batch:{date_filter}:{datetime.now().strftime('%Y%m%d%H%M')}",
                league="ALL",
                audit_data={
                    "overall_accuracy": overall_accuracy_pct,
                    "safe_accuracy": safe_accuracy_pct,
                    "neutro_accuracy": neutro_accuracy_pct,
                    "total_matches": len(match_results),
                    "avg_brier_score": avg_brier,
                    "avg_lambda_error": avg_lambda_error,
                    "model_evaluation_summary": model_evaluation.get("overall_assessment", "") if model_evaluation else "",
                },
                match_status="batch_audit",
                user=_audit_user,
            )
        except Exception as e:
            logger.warning(f"Could not store batch audit result: {e}")

        return {
            "status": "success",
            "total_matches": len(finished_matches),
            "finished_matches": len(finished_matches),
            "audited_matches": len(match_results),
            "overall_accuracy": round(overall_accuracy_pct, 1),
            "safe_accuracy": round(safe_accuracy_pct, 1),
            "neutro_accuracy": round(neutro_accuracy_pct, 1),
            "safe_correct": safe_correct,
            "safe_total": safe_total,
            "neutro_correct": neutro_correct,
            "neutro_total": neutro_total,
            "avg_brier_score": round(avg_brier, 4),
            "avg_lambda_error": round(avg_lambda_error, 2),
            "market_accuracy": market_accuracy_output,
            "match_results": match_results,
            "model_evaluation": model_evaluation,
        }
    except Exception as e:
        logger.error(f"Batch audit error: {e}")
        raise HTTPException(status_code=500, detail=f"Erro na auditoria em lote: {str(e)}")


@router.post("/batch-audit/apply")
async def apply_batch_corrections(request: BatchCorrectionRequest):
    """Apply multiple corrections from a batch audit at once."""
    from backend import audit as audit_db

    applied = []
    errors = []

    for idx, corr in enumerate(request.corrections):
        try:
            corr_type = corr.get("type", corr.get("correction_type", ""))
            param = corr.get("parameter", corr.get("parameter_name", ""))
            old_val = float(corr.get("current_value", corr.get("old_value", 0)))
            new_val = float(corr.get("suggested_value", corr.get("new_value", 0)))
            reason = corr.get("reason", "")
            confidence = int(corr.get("confidence", corr.get("audit_confidence", 0)))

            audit_db.log_correction(
                match_id=f"batch_correction_{datetime.now().strftime('%Y%m%d%H%M')}_{idx}",
                league="ALL",
                correction_type=corr_type,
                parameter_name=param,
                old_value=old_val,
                new_value=new_val,
                suggested_by="mistral_batch_audit",
                applied_by="user",
                audit_confidence=confidence,
                reason=reason,
            )

            # Apply threshold corrections immediately
            if corr_type in ("THRESHOLD", "threshold_adjustment"):
                corr_model = CorrectionApplication(
                    correction_type="threshold_adjustment",
                    parameter_name=param,
                    old_value=old_val,
                    new_value=new_val,
                    reason=reason,
                    audit_confidence=confidence,
                )
                _apply_threshold_correction(corr_model)

            applied.append({"parameter": param, "old_value": old_val, "new_value": new_val})
        except Exception as e:
            errors.append({"index": idx, "error": str(e)})

    return {
        "status": "success" if not errors else "partial",
        "applied": len(applied),
        "errors": len(errors),
        "details": applied,
        "error_details": errors if errors else None,
    }
