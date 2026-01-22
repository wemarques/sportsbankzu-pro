from backend.audit import adjust_thresholds

DEFAULT_THRESHOLDS = {
    "home_win": {"SAFE": 0.60, "NEUTRO": 0.45},
    "over25": {"SAFE": 0.65, "NEUTRO": 0.50},
    "btts": {"SAFE": 0.55, "NEUTRO": 0.40},
    "under35": {"SAFE": 0.70, "NEUTRO": 0.60},
    "under45": {"SAFE": 0.75, "NEUTRO": 0.65},
}

if __name__ == "__main__":
    adjust_thresholds(DEFAULT_THRESHOLDS)
