from typing import Dict, Any, List, Optional
import logging
from backend.services.util_service import team_name
from backend.modeling.market_validator import (
    validar_prognostico,
    filtrar_mercados_permitidos,
)

logger = logging.getLogger("sportsbankzu")


def selecionar_mercados_v2(
    jogo: Dict[str, Any],
    regime: str,
    volatilidade: str,
    league_id: str = "",
) -> List[Dict[str, Any]]:
    """Enhanced market selection using the new 5-layer pipeline.

    Integrates:
    - Layer 1: Data governance (quality score)
    - Layer 2: Poisson matrix + corners engine
    - Layer 3: EV + classification (SAFE/NEUTRO_QUALIFICADO/NO_BET)
    - Layer 4: Bankroll info (stake hints)
    - Layer 5: Correlation info for multiples

    Returns legacy-compatible mercados list enriched with new fields.
    """
    try:
        from backend.services.ev_classification import evaluate_match_markets

        bundle = evaluate_match_markets(jogo, league_id=league_id, regime=regime)

        # Convert to legacy format with enrichments
        mercados = []
        for market in bundle.markets:
            legacy = market.to_legacy_mercado()
            mercados.append(legacy)

        # Apply regime validation (existing logic)
        if mercados:
            def normalizar_mercado(nome: str) -> str:
                base = nome.replace(" gols", "").strip()
                if base.startswith("DC 1X"):
                    return "Double Chance 1X"
                if base.startswith("DC X2"):
                    return "Double Chance X2"
                if base.startswith("DC 12"):
                    return "Double Chance 12"
                if base.startswith("BTTS"):
                    return "BTTS"
                if base.startswith("Escanteios Over"):
                    return base
                return base

            mercados_normalizados = [normalizar_mercado(m.get("mercado", "")) for m in mercados]
            is_valid, invalidos = validar_prognostico({"markets": mercados_normalizados}, regime)
            if not is_valid:
                permitidos = filtrar_mercados_permitidos(mercados_normalizados, regime)
                mercados = [
                    m for m, nome_norm in zip(mercados, mercados_normalizados)
                    if nome_norm in permitidos
                ]

        # Set principal market in stats
        stats = jogo.get("stats", {})
        if mercados:
            principal = mercados[0]
            stats["status"] = principal.get("status", "NEUTRO")
            stats["mercado_principal"] = principal.get("mercado")
            stats["odd_minima"] = principal.get("odd_minima")
            stats["data_quality_score"] = bundle.data_quality_score

        return mercados

    except Exception as e:
        logger.warning(f"[V2] Fallback to legacy market selection: {e}")
        return selecionar_mercados_jogo(jogo, regime, volatilidade)


def _get_dynamic_thresholds(market: str) -> dict:
    """Return SAFE/NEUTRO thresholds for a market, preferring values from the audit DB.

    Falls back to hardcoded defaults when the DB is unavailable or has no entry
    for this market. This enables the cron audit to gradually tighten or relax
    thresholds based on observed Brier scores (Gap 4 — dynamic thresholds).
    """
    try:
        from backend.audit import init_db
        conn = init_db()
        row = conn.execute(
            "SELECT safe_threshold, neutro_threshold FROM thresholds WHERE market=?",
            (market,),
        ).fetchone()
        conn.close()
        if row and row[0] is not None:
            return {"SAFE": float(row[0]), "NEUTRO": float(row[1]) if row[1] is not None else float(row[0]) * 0.9}
    except Exception as _e:
        logger.debug(f"[Gap4] Could not read dynamic threshold for {market}: {_e}")

    _defaults: dict = {
        "BTTS":                  {"SAFE": 0.78, "NEUTRO": 0.72},
        "Over/Under":            {"SAFE": 0.72, "NEUTRO": 0.65},
        "Double Chance":         {"SAFE": 0.82, "NEUTRO": 0.75},
        "1X2":                   {"SAFE": 0.60, "NEUTRO": 0.50},
        "Escanteios Over 8.5":   {"SAFE": 0.88, "NEUTRO": 0.80},
        "Escanteios Over 9.5":   {"SAFE": 0.85, "NEUTRO": 0.78},
        "Escanteios Over 10.5":  {"SAFE": 0.80, "NEUTRO": 0.72},
    }
    return _defaults.get(market, {"SAFE": 0.60, "NEUTRO": 0.50})


def normalize_prob(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    try:
        v = float(value)
    except Exception:
        return None
    if v > 1.0:
        v = v / 100.0
    if v < 0:
        return None
    return min(max(v, 0.0), 1.0)

def calcular_odd_under(odd_over: float) -> Optional[float]:
    if not odd_over or odd_over <= 1.0:
        return None
    prob_over = 1.0 / odd_over
    prob_under = 1.0 - prob_over
    if prob_under <= 0:
        return None
    return round(1.0 / prob_under, 2)

def selecionar_mercados_jogo(jogo: Dict[str, Any], regime: str, volatilidade: str) -> List[Dict[str, Any]]:
    mercados: List[Dict[str, Any]] = []
    stats = jogo.get("stats", {})
    odds = jogo.get("odds", {})

    # Load thresholds from audit DB (Gap 4 — dynamic thresholds with hardcoded fallback)
    _th_btts = _get_dynamic_thresholds("BTTS")
    _th_dc = _get_dynamic_thresholds("Double Chance")
    _th_ou = _get_dynamic_thresholds("Over/Under")
    prob_over25 = normalize_prob(stats.get("over25Prob"))
    prob_btts = normalize_prob(stats.get("bttsProb"))
    prob_under35 = normalize_prob(stats.get("under35Prob"))
    prob_under45 = normalize_prob(stats.get("under45Prob"))
    home = team_name(jogo.get("homeTeam", "?"))
    away = team_name(jogo.get("awayTeam", "?"))
    logger.info(f"[DEBUG] {home} vs {away}:")
    logger.info(f"  under35Prob raw={stats.get('under35Prob')}, normalized={prob_under35}")
    logger.info(f"  under45Prob raw={stats.get('under45Prob')}, normalized={prob_under45}")
    logger.info(f"  regime={regime}, volatilidade={volatilidade}")
    logger.info(f"  leagueAvgGoals={stats.get('leagueAvgGoals')}")
    logger.info(f"  odds: over35={odds.get('over35')}, over45={odds.get('over45')}")
    prob_dc = None
    if stats.get("homeWinProb") is not None and stats.get("drawProb") is not None:
        prob_dc = normalize_prob(float(stats.get("homeWinProb", 0)) + float(stats.get("drawProb", 0)))
    odd_over35 = odds.get("over35")
    odd_over45 = odds.get("over45")
    odd_btts_yes = odds.get("bttsYes")
    odd_under35 = calcular_odd_under(odd_over35) if odd_over35 else None
    odd_under45 = calcular_odd_under(odd_over45) if odd_over45 else None
    def add_mercado(nome: str, status: str, prob: float, odd_real: Optional[float] = None, alerta: Optional[str] = None) -> None:
        prob_min = max(0, int(prob * 100) - 2)
        prob_max = max(0, int(prob * 100))
        odd_minima = round(1.0 / prob, 2) if prob > 0 else None
        odd_display = odd_real if odd_real else odd_minima
        item: Dict[str, Any] = {
            "mercado": nome,
            "status": status,
            "prob_min": prob_min,
            "prob_max": prob_max,
            "odd_minima": odd_display,
        }
        if alerta:
            item["alerta"] = alerta
        mercados.append(item)
    league_avg_goals = stats.get("leagueAvgGoals") or 2.7
    if league_avg_goals < 2.5:
        threshold_u35 = 0.72
        threshold_u45 = 0.82
    elif league_avg_goals < 3.0:
        threshold_u35 = 0.68
        threshold_u45 = 0.78
    else:
        threshold_u35 = 0.75
        threshold_u45 = 0.85
    logger.info(f"  thresholds: u35={threshold_u35}, u45={threshold_u45}")
    _u35_check = (prob_under35 >= threshold_u35) if prob_under35 is not None else False
    _u45_check = (prob_under45 >= threshold_u45) if prob_under45 is not None else False
    logger.info(f"  checks: u35({prob_under35} >= {threshold_u35})={_u35_check}")
    logger.info(f"  checks: u45({prob_under45} >= {threshold_u45})={_u45_check}")
    if regime in ["NORMAL", "DEFENSIVA"]:
        if prob_under35 is not None and prob_under35 >= threshold_u35:
            if odd_under35 and odd_under35 >= 1.25:
                add_mercado("Under 3.5 gols", "SAFE", prob_under35, odd_under35)
            elif odd_under35 and odd_under35 >= 1.20:
                add_mercado("Under 3.5 gols", "SAFE*", prob_under35, odd_under35, alerta="Odd baixa")
            else:
                add_mercado("Under 3.5 gols", "SAFE*", prob_under35, odd_under35, alerta="Odd muito baixa")
        elif prob_under45 is not None and prob_under45 >= threshold_u45:
            if odd_under45 and odd_under45 >= 1.15:
                add_mercado("Under 4.5 gols", "SAFE", prob_under45, odd_under45)
            elif odd_under45 and odd_under45 >= 1.10:
                add_mercado("Under 4.5 gols", "SAFE*", prob_under45, odd_under45, alerta="Odd baixa")
            else:
                add_mercado("Under 4.5 gols", "SAFE*", prob_under45, odd_under45, alerta="Odd muito baixa")
    else:
        if prob_over25 is not None and prob_over25 >= _th_ou["SAFE"]:
            add_mercado("Over 2.5 gols", "SAFE", prob_over25, odds.get("over25"))
    if prob_btts is not None and prob_btts >= _th_btts["NEUTRO"]:
        status = "SAFE" if prob_btts >= _th_btts["SAFE"] else "NEUTRO"
        add_mercado("BTTS — SIM", status, prob_btts, odd_btts_yes)
    if prob_dc is not None and prob_dc >= _th_dc["NEUTRO"]:
        home = team_name(jogo.get("homeTeam", ""))[:3].upper()
        status_dc = "SAFE" if prob_dc >= _th_dc["SAFE"] else "NEUTRO"
        add_mercado(f"DC 1X ({home}/EMP)", status_dc, prob_dc)
    # Corner market predictions (from FootyStats pre-match potentials)
    # Use dynamic thresholds from audit DB (Gap 4 extension for corners)
    _th_c85 = _get_dynamic_thresholds("Escanteios Over 8.5")
    _th_c95 = _get_dynamic_thresholds("Escanteios Over 9.5")
    _th_c105 = _get_dynamic_thresholds("Escanteios Over 10.5")
    corner_o85 = normalize_prob(stats.get("cornerOver85Prob"))
    corner_o95 = normalize_prob(stats.get("cornerOver95Prob"))
    corner_o105 = normalize_prob(stats.get("cornerOver105Prob"))
    odd_corners_o85 = odds.get("cornersOver85")
    odd_corners_o95 = odds.get("cornersOver95")
    odd_corners_o105 = odds.get("cornersOver105")
    # Add corner markets when probability exceeds dynamic threshold
    if corner_o85 is not None and corner_o85 >= _th_c85["NEUTRO"]:
        status_c = "SAFE" if corner_o85 >= _th_c85["SAFE"] else "NEUTRO"
        add_mercado("Escanteios Over 8.5", status_c, corner_o85, odd_corners_o85)
    if corner_o95 is not None and corner_o95 >= _th_c95["NEUTRO"]:
        status_c = "SAFE" if corner_o95 >= _th_c95["SAFE"] else "NEUTRO"
        add_mercado("Escanteios Over 9.5", status_c, corner_o95, odd_corners_o95)
    if corner_o105 is not None and corner_o105 >= _th_c105["NEUTRO"]:
        status_c = "SAFE" if corner_o105 >= _th_c105["SAFE"] else "NEUTRO"
        add_mercado("Escanteios Over 10.5", status_c, corner_o105, odd_corners_o105)
    if not mercados:
        # Fallback: only the single best candidate with stricter thresholds
        candidatos = []
        if prob_under35 and prob_under35 >= 0.65:
            candidatos.append(("Under 3.5 gols", "NEUTRO", prob_under35, odd_under35))
        if prob_under45 and prob_under45 >= 0.75:
            candidatos.append(("Under 4.5 gols", "NEUTRO", prob_under45, odd_under45))
        if prob_over25 and prob_over25 >= 0.62:
            candidatos.append(("Over 2.5 gols", "NEUTRO", prob_over25, odds.get("over25")))
        if prob_btts and prob_btts >= 0.63:
            candidatos.append(("BTTS — SIM", "NEUTRO", prob_btts, odd_btts_yes))
        if prob_dc and prob_dc >= 0.72:
            home = team_name(jogo.get("homeTeam", ""))[:3].upper()
            candidatos.append((f"DC 1X ({home}/EMP)", "NEUTRO", prob_dc, None))
        candidatos.sort(key=lambda x: x[2], reverse=True)
        if candidatos:
            nome, status, prob, odd = candidatos[0]
            add_mercado(nome, status, prob, odd)
    def normalizar_mercado(nome: str) -> str:
        base = nome.replace(" gols", "").strip()
        if base.startswith("DC 1X"):
            return "Double Chance 1X"
        if base.startswith("DC X2"):
            return "Double Chance X2"
        if base.startswith("DC 12"):
            return "Double Chance 12"
        if base.startswith("BTTS"):
            return "BTTS"
        if base.startswith("Escanteios Over"):
            return base  # Already in valid format
        return base
    if mercados:
        mercados_normalizados = [normalizar_mercado(m.get("mercado", "")) for m in mercados]
        is_valid, invalidos = validar_prognostico({"markets": mercados_normalizados}, regime)
        if not is_valid:
            permitidos = filtrar_mercados_permitidos(mercados_normalizados, regime)
            mercados = [
                m for m, nome_norm in zip(mercados, mercados_normalizados)
                if nome_norm in permitidos
            ]
            logger.warning(
                f"Prognóstico removido por mercados inválidos: {invalidos} | Regime: {regime}"
            )
        logger.info(
            f"Validação de mercados | Total: {len(mercados_normalizados)} | Válidos: {len(mercados)} | Removidos: {len(mercados_normalizados) - len(mercados)}"
        )
    if mercados:
        principal = mercados[0]
        stats["status"] = "SAFE" if principal.get("status") == "SAFE" else principal.get("status", "NEUTRO")
        stats["mercado_principal"] = principal.get("mercado")
        stats["odd_minima"] = principal.get("odd_minima")
    return mercados
