# scripts/fill_ai_audit_results.py
"""
#188 Fase 1 — preenche actual_result nos registros do ai_audit_log.

Uso (com .venv ativa, a partir da raiz do repo):
    python scripts/fill_ai_audit_results.py [--date yesterday|today|week] [--dry-run]

Fluxo:
1. Lista match_ids do ai_audit_log ainda sem actual_result.
2. Busca os jogos finalizados no pipeline (reusa _get_all_finished_matches).
3. Para cada match logado que finalizou, grava o resultado real
   (total_goals, btts, result_1x2, total_corners, total_cards, placar).

Rodável manualmente ou via cron. Não altera comportamento de produção —
só escreve na tabela de medição. A extração de resultado espelha a lógica
do cron_handler (linhas ~116-190); unificar num helper compartilhado é
candidato de refactor na Fase 4.
"""
import argparse
import logging
import sys
from pathlib import Path
from typing import Any, Dict, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("fill_ai_audit_results")


def _int_or_zero(*candidates) -> int:
    """Primeiro valor não-None convertível para int >= 0; senão 0.

    Usa checagens `is None` — não `or` — porque 0 é valor válido (#078v).
    """
    for c in candidates:
        if c is None:
            continue
        try:
            v = int(c)
            return v if v >= 0 else 0
        except (ValueError, TypeError):
            continue
    return 0


def extract_actual_result(record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extrai o resultado real de um record finalizado do pipeline.

    Espelha a extração do cron_handler (#085b/#078v). Retorna None quando não
    há placar verificado (jogo não deve ser marcado como resolvido).
    """
    score = record.get("score") or {}
    stats = record.get("stats", {}) or {}

    home_goals = score.get("home") if isinstance(score, dict) else None
    away_goals = score.get("away") if isinstance(score, dict) else None
    if home_goals is None or away_goals is None:
        home_goals = record.get("home_team_goal_count") or record.get("homeGoals")
        away_goals = record.get("away_team_goal_count") or record.get("awayGoals")
    try:
        home_goals = int(home_goals) if home_goals is not None else None
        away_goals = int(away_goals) if away_goals is not None else None
    except (ValueError, TypeError):
        home_goals, away_goals = None, None

    if home_goals is None or away_goals is None:
        return None  # sem placar verificado — não preencher

    total_goals = home_goals + away_goals
    if home_goals > away_goals:
        result_1x2 = "1"
    elif home_goals == away_goals:
        result_1x2 = "X"
    else:
        result_1x2 = "2"

    total_corners = _int_or_zero(stats.get("homeCornersCount"), record.get("home_team_corner_count")) + \
        _int_or_zero(stats.get("awayCornersCount"), record.get("away_team_corner_count"))

    total_cards = (
        _int_or_zero(stats.get("homeYellowCards"), record.get("home_team_yellow_cards"))
        + _int_or_zero(stats.get("awayYellowCards"), record.get("away_team_yellow_cards"))
        + _int_or_zero(stats.get("homeRedCards"), record.get("home_team_red_cards"))
        + _int_or_zero(stats.get("awayRedCards"), record.get("away_team_red_cards"))
    )

    return {
        "home_goals": home_goals,
        "away_goals": away_goals,
        "total_goals": total_goals,
        "btts": home_goals > 0 and away_goals > 0,
        "result_1x2": result_1x2,
        "total_corners": total_corners,
        "total_cards": total_cards,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", default="yesterday",
                        choices=["today", "yesterday", "week"],
                        help="Janela de jogos finalizados a buscar (default: yesterday)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Mostra o que seria preenchido sem gravar")
    args = parser.parse_args()

    from backend.ai.audit_log import fill_actual_result, get_pending_result_match_ids
    from backend.routes.ai_analysis import _get_all_finished_matches

    pending = set(get_pending_result_match_ids())
    if not pending:
        logger.info("Nenhum registro pendente de actual_result. Nada a fazer.")
        return 0
    logger.info(f"{len(pending)} match_id(s) pendentes no ai_audit_log")

    finished = _get_all_finished_matches(date_filter=args.date)
    logger.info(f"{len(finished)} jogos finalizados no pipeline ({args.date})")

    filled = 0
    for record in finished:
        mid = record.get("id")
        if mid not in pending:
            continue
        result = extract_actual_result(record)
        if result is None:
            logger.warning(f"  {mid}: finalizado mas sem placar verificado — pulado")
            continue
        if args.dry_run:
            logger.info(f"  [dry-run] {mid}: {result}")
            filled += 1
            continue
        n = fill_actual_result(mid, result)
        if n:
            logger.info(f"  {mid}: {n} registro(s) preenchido(s) — {result['home_goals']}x{result['away_goals']}")
            filled += n

    logger.info(f"Concluído: {filled} registro(s) {'(dry-run) ' if args.dry_run else ''}preenchidos")
    return 0


if __name__ == "__main__":
    sys.exit(main())
