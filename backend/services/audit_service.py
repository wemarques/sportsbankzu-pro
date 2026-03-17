from .typing import DictAny  # optional internal typing stub
import json
from datetime import datetime
from backend.audit import (
    init_db,
    ensure_thresholds,
    calculate_brier,
    get_current_threshold,
)

def log_pick_service(
    match_id: str,
    league: str,
    market: str,
    predicted_probs: dict,
    pick_type: str,
    ev: float | None,
    context: dict | None = None,
    actual_result: str | None = None,
) -> None:
    conn = init_db()
    cursor = conn.cursor()
    record_id = f"{match_id}:{market}"
    brier_score = None
    if actual_result and actual_result in predicted_probs:
        brier_score = calculate_brier(float(predicted_probs.get(actual_result, 0.0)), True)
    cursor.execute(
        """
        INSERT OR REPLACE INTO audit_results
        (match_id, league, market, predicted_probs, actual_result, pick_type, brier_score, ev, context, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record_id,
            league,
            market,
            json.dumps(predicted_probs),
            actual_result,
            pick_type,
            brier_score,
            ev,
            json.dumps(context or {}),
            datetime.now(),
        ),
    )
    conn.commit()
    conn.close()
