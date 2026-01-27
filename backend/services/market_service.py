from typing import Dict, Any, List, Optional
import logging
from backend.modeling.market_validator import (
    validar_prognostico,
    filtrar_mercados_permitidos,
)

logger = logging.getLogger("sportsbank")

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
    prob_over25 = normalize_prob(stats.get("over25Prob"))
    prob_btts = normalize_prob(stats.get("bttsProb"))
    prob_under35 = normalize_prob(stats.get("under35Prob"))
    prob_under45 = normalize_prob(stats.get("under45Prob"))
    home = jogo.get("homeTeam", "?")
    away = jogo.get("awayTeam", "?")
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
    league_avg_goals = stats.get("leagueAvgGoals", 2.7)
    if league_avg_goals < 2.5:
        threshold_u35 = 0.55
        threshold_u45 = 0.65
    elif league_avg_goals < 3.0:
        threshold_u35 = 0.60
        threshold_u45 = 0.70
    else:
        threshold_u35 = 0.65
        threshold_u45 = 0.75
    logger.info(f"  thresholds: u35={threshold_u35}, u45={threshold_u45}")
    logger.info(f"  checks: u35({prob_under35} >= {threshold_u35})={prob_under35 >= threshold_u35 if prob_under35 else False}")
    logger.info(f"  checks: u45({prob_under45} >= {threshold_u45})={prob_under45 >= threshold_u45 if prob_under45 else False}")
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
        if prob_over25 is not None and prob_over25 >= 0.72:
            add_mercado("Over 2.5 gols", "SAFE", prob_over25, odds.get("over25"))
    if prob_btts is not None and prob_btts >= 0.60:
        status = "SAFE" if prob_btts >= 0.68 else "NEUTRO"
        add_mercado("BTTS — SIM", status, prob_btts, odd_btts_yes)
    if prob_dc is not None and prob_dc >= 0.65:
        home = str(jogo.get("homeTeam", ""))[:3].upper()
        add_mercado(f"DC 1X ({home}/EMP)", "NEUTRO", prob_dc)
    if not mercados:
        candidatos = []
        if prob_under35:
            candidatos.append(("Under 3.5 gols", "NEUTRO", prob_under35, odd_under35))
        if prob_under45:
            candidatos.append(("Under 4.5 gols", "NEUTRO", prob_under45, odd_under45))
        if prob_over25:
            candidatos.append(("Over 2.5 gols", "NEUTRO", prob_over25, odds.get("over25")))
        if prob_btts and prob_btts >= 0.50:
            candidatos.append(("BTTS — SIM", "NEUTRO", prob_btts, odd_btts_yes))
        if prob_dc and prob_dc >= 0.60:
            home = str(jogo.get("homeTeam", ""))[:3].upper()
            candidatos.append((f"DC 1X ({home}/EMP)", "NEUTRO", prob_dc, None))
        candidatos.sort(key=lambda x: x[2], reverse=True)
        for nome, status, prob, odd in candidatos[:3]:
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
