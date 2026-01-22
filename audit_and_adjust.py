from datetime import datetime
from backend.audit import init_db, log_pick, adjust_thresholds

# Thresholds iniciais (exemplo)
initial_thresholds = {
    "home_win": {"SAFE": 0.60, "NEUTRO": 0.45},
    "over25": {"SAFE": 0.65, "NEUTRO": 0.50},
    "btts": {"SAFE": 0.55, "NEUTRO": 0.40},
    "under35": {"SAFE": 0.70, "NEUTRO": 0.60},
    "under45": {"SAFE": 0.75, "NEUTRO": 0.65},
}

def audit_round(matches: list):
    for match in matches:
        log_pick(**match)


# Exemplo de uso
if __name__ == "__main__":
    init_db()
    matches = [
        {
            "match_id": "ARSENAL_CHELSEA_20260121",
            "league": "Premier League",
            "market": "over25",
            "predicted_probs": {"home": 0.45, "draw": 0.25, "over25": 0.60},
            "actual_result": "over25",
            "pick_type": "SAFE",
            "ev": 0.15,
            "context": {"volatility": "BAIXA", "regime": "NORMAL"},
        },
        {
            "match_id": "LIVERPOOL_MANUTD_20260121",
            "league": "Premier League",
            "market": "home_win",
            "predicted_probs": {"home": 0.70, "draw": 0.20, "over25": 0.50},
            "actual_result": "home",
            "pick_type": "NEUTRO",
            "ev": 0.10,
            "context": {"volatility": "ALTA", "regime": "HIPER-OFENSIVA"},
        },
    ]

    audit_round(matches)
    adjust_thresholds(initial_thresholds)
