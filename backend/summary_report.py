from typing import List, Dict
from datetime import datetime


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
        pick_type = match.get("pick_type", "NO_BET")
        ev = match.get("ev", 0)
        context = match.get("context", {})

        suggested_markets = []
        if predicted_probs.get("over25", 0) > 0.6:
            suggested_markets.append(f"Over 2.5 ({predicted_probs['over25'] * 100:.1f}%)")
        if predicted_probs.get("btts", 0) > 0.55:
            suggested_markets.append(f"BTTS Sim ({predicted_probs['btts'] * 100:.1f}%)")
        if predicted_probs.get("home", 0) > 0.6:
            suggested_markets.append(f"Vitória {match.get('homeTeam', match.get('home_team', ''))} ({predicted_probs['home'] * 100:.1f}%)")

        summary.append(
            {
                "Jogo": game,
                "Liga": league,
                "Data/Hora": timestamp,
                "Mercados Sugeridos": suggested_markets if suggested_markets else ["Nenhum"],
                "Status": pick_type,
                "EV": f"{ev:.2f}",
                "Contexto": f"Volatilidade: {context.get('volatility', 'Desconhecida')}, Regime: {context.get('regime', 'Desconhecido')}",
                "λ (Home)": match.get("lambda_home", match.get("lambdaHome", "N/A")),
                "λ (Away)": match.get("lambda_away", match.get("lambdaAway", "N/A")),
            }
        )

    return summary
