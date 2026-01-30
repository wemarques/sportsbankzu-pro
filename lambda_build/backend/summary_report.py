from typing import List, Dict
from datetime import datetime


def _normalize_prob(value):
    if value is None:
        return None
    try:
        v = float(value)
    except Exception:
        return None
    if v > 1:
        v = v / 100.0
    return max(0.0, min(1.0, v))


def generate_summary_report(matches: List[Dict]) -> List[Dict]:
    """
    Gera um quadro resumo dos jogos analisados, incluindo sugestões de mercados.
    """
    summary = []

    for match in matches:
        game = f"{match.get('homeTeam', match.get('home_team', ''))} x {match.get('awayTeam', match.get('away_team', ''))}"
        league = match.get("leagueName", match.get("league", "Desconhecida"))
        timestamp = match.get("datetime", match.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M")))

        predicted_probs = match.get("predicted_probs", {})
        stats = match.get("stats", {})
        pick_type = match.get("pick_type", "NO_BET")
        ev = match.get("ev", None)
        context = match.get("context", {})

        suggested_markets = []
        prob_over25 = _normalize_prob(predicted_probs.get("over25")) or _normalize_prob(stats.get("over25Prob"))
        prob_btts = _normalize_prob(predicted_probs.get("btts")) or _normalize_prob(stats.get("bttsProb"))
        prob_home = _normalize_prob(predicted_probs.get("home")) or _normalize_prob(stats.get("homeWinProb"))

        if prob_over25 and prob_over25 > 0.6:
            suggested_markets.append(f"Over 2.5 ({prob_over25 * 100:.1f}%)")
        if prob_btts and prob_btts > 0.55:
            suggested_markets.append(f"BTTS Sim ({prob_btts * 100:.1f}%)")
        if prob_home and prob_home > 0.6:
            suggested_markets.append(f"Vitória {match.get('homeTeam', match.get('home_team', ''))} ({prob_home * 100:.1f}%)")

        if ev is None and prob_over25:
            odd = match.get("odds", {}).get("over25")
            if odd:
                try:
                    ev = (prob_over25 * float(odd)) - 1
                except Exception:
                    ev = None

        summary.append(
            {
                "Jogo": game,
                "Liga": league,
                "Data/Hora": timestamp,
                "Mercados Sugeridos": suggested_markets if suggested_markets else ["Nenhum"],
                "Status": pick_type,
                "EV": f"{ev:.2f}" if ev is not None else "-",
                "Contexto": f"Volatilidade: {context.get('volatility', stats.get('leagueVolatility', 'Desconhecida'))}, Regime: {context.get('regime', stats.get('leagueRegime', 'Desconhecido'))}",
                "λ (Home)": match.get("lambda_home", match.get("lambdaHome", "N/A")),
                "λ (Away)": match.get("lambda_away", match.get("lambdaAway", "N/A")),
            }
        )

    return summary
