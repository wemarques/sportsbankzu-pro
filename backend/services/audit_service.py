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
    record_id = f\"{match_id}:{market}\"
    brier_score = None
    if actual_result and actual_result in predicted_probs:
        brier_score = calculate_brier(float(predicted_probs.get(actual_result, 0.0)), True)
    cursor.execute(
        \"\"\"\n        INSERT OR REPLACE INTO audit_results\n        (match_id, league, market, predicted_probs, actual_result, pick_type, brier_score, ev, context, timestamp)\n        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)\n        \"\"\",\n        (\n            record_id,\n            league,\n            market,\n            json.dumps(predicted_probs),\n            actual_result,\n            pick_type,\n            brier_score,\n            ev,\n            json.dumps(context or {}),\n            datetime.now(),\n        ),\n    )\n    conn.commit()\n    conn.close()\n*** End Patch```}ерам아요, you need to include valid input for the apply_patch tool. It only accepts string inputs that obey the *** Begin Patch envelope grammar. Please try again.။
