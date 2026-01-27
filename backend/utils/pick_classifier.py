def is_safe_tec(match: dict, thresholds: dict) -> bool:
    return match["prob"] >= thresholds[match["market"]]["SAFE"]

def is_safe_op(match: dict, thresholds: dict) -> bool:
    return (
        is_safe_tec(match, thresholds)
        and match.get("correlation", 0) < 0.3
        and match.get("liquidity", 0) > 0.7
        and not match.get("has_contextual_risk", False)
    )
