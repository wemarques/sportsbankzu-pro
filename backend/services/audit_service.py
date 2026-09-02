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
    # ATENCAO (#218): `INSERT OR REPLACE` e a origem mecanica do vazamento
    # temporal que o #200 teve de conter com um gate. Cada reprocessamento
    # pos-jogo sobrescreve a linha, entao `audit_results` guarda o prognostico
    # RECOMPUTADO com o placar ja conhecido — nao o que foi publicado antes.
    # Treinar calibrador nisso e aprender com dados do futuro.
    #
    # A semantica NAO muda aqui de proposito: varios leitores (backtesting,
    # brier_service, audit_status) esperam uma linha por (jogo, mercado) e
    # troca-la agora quebraria as telas sem que ninguem tivesse medido nada.
    # A fonte limpa e `prediction_ledger` (#218), append-only, escrita no
    # momento da publicacao. Quando o ledger tiver rodadas suficientes, esta
    # tabela vira historico e este INSERT OR REPLACE sai.
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
