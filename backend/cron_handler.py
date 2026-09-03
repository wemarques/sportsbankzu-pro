"""
Handler para AWS EventBridge (CloudWatch Events).
Executa auditoria batch automatizada diariamente.

A Lambda principal (backend.main:handler) roda o FastAPI via Mangum.
Este handler eh invocado separadamente pelo EventBridge rule
e chama diretamente a logica de batch audit, sem precisar de HTTP.

Configuracao EventBridge:
  - Rule name: sportsbank-daily-audit
  - Schedule: cron(0 23 * * ? *)  -> 23:00 UTC = 20:00 BRT
  - Target: Lambda sportsbank-pro-backend
  - Input: {"source": "eventbridge", "action": "batch_audit", "date": "yesterday"}
"""

import json
import logging
import os
from datetime import datetime
from backend.services.util_service import team_name
from backend.utils.valores import primeiro_valido  # #226

logger = logging.getLogger("sportsbankzu.cron")
logger.setLevel(logging.INFO)


def cron_handler(event, context):
    """
    Entry point for EventBridge-triggered events.
    Delegates to the appropriate action based on event payload.
    """
    logger.info(f"EventBridge triggered: {json.dumps(event)}")

    # Set env flag so audit logs know this is a cron execution
    os.environ["EVENTBRIDGE_TRIGGERED"] = "1"

    action = event.get("action", "batch_audit")
    date_filter = event.get("date", "yesterday")

    try:
        if action == "batch_audit":
            return _run_batch_audit(date_filter)
        elif action == "today_audit":
            # New rule: cron(45 2 * * ? *) → 02:45 UTC = 23:45 BRT
            return _run_batch_audit("today", before_time_brt="23:45")
        elif action == "late_audit":
            # #160: cron(0 5 * * ? *) → 05:00 UTC = 02:00 BRT
            # Catches Liga MX, MLS, Copa Libertadores etc. that finish after 23:45 BRT
            return _run_late_audit()
        elif action == "retrain_calibrators":
            return _run_retrain_calibrators(force=bool(event.get("force")))
        elif action == "adjust_thresholds":
            return _run_threshold_adjustment()
        elif action == "retrain_corners":
            return _run_retrain_corners()
        elif action == "snapshot_standings":
            # #173: persistencia diaria de standings em S3 para backtest
            # futuro de features de contexto de temporada.
            return _run_snapshot_standings()
        else:
            return {"status": "error", "message": f"Unknown action: {action}"}
    except Exception as e:
        logger.error(f"Cron handler error: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        os.environ.pop("EVENTBRIDGE_TRIGGERED", None)


def _run_batch_audit(date_filter: str, before_time_brt: str | None = None) -> dict:
    """Execute batch audit for all finished matches.

    Args:
        date_filter: 'today' | 'yesterday' | 'week'
        before_time_brt: Optional cutoff time in BRT (e.g. '23:45') — only include
            matches that finished before this time. Used by the today_audit action so
            that late European matches already completed are audited same-day.
    """
    from backend.routes.ai_analysis import (
        _get_all_finished_matches,
        _evaluate_pick_deterministic,
    )
    from backend import audit as audit_db

    label = f"date={date_filter}" + (f" before_brt={before_time_brt}" if before_time_brt else "")
    logger.info(f"Starting automated batch audit for {label}")

    finished_matches = _get_all_finished_matches(date_filter, before_time_brt=before_time_brt)

    if not finished_matches:
        from backend.audit import audit_logger
        msg = f"[CRON] {date_filter} — Nenhum jogo finalizado encontrado. Auditoria pulada."
        logger.info(msg)
        audit_logger.info(msg)
        return {
            "status": "success",
            "message": "Nenhum jogo finalizado encontrado.",
            "audited_matches": 0,
        }

    # Evaluate each match deterministically (same logic as the API endpoint)
    overall_correct = 0
    overall_total = 0
    safe_correct = 0
    safe_total = 0
    neutro_correct = 0
    neutro_total = 0
    market_stats = {}
    lambda_errors = []
    brier_scores = []
    # #195: Brier sobre os picks auditados — mesmo conjunto que alimenta a
    # acuracia. brier_scores mede apenas Over 2.5 gols, um valor por jogo,
    # entao 81% de acerto convivia com "Brier 0.18" sem relacao entre si.
    pick_brier_scores = []
    ev_values = []
    match_results = []
    ou_predictions = []  # #079: for Log-Loss computation
    all_evaluated_picks = []  # #083: for diagnostic engine
    # Per-league tracking for BUG #069: Brier/SAFE/lambda were global-only
    league_metrics: dict[str, dict] = {}

    for m in finished_matches:
        home = team_name(m.get("homeTeam", ""))
        away = team_name(m.get("awayTeam", ""))
        league = m.get("leagueName", m.get("leagueId", ""))
        score = m.get("score") or {}
        stats = m.get("stats", {})
        mercados = m.get("mercados", [])

        home_goals = score.get("home") if score else None
        away_goals = score.get("away") if score else None

        if home_goals is None or away_goals is None:
            home_goals = m.get("home_team_goal_count") or m.get("homeGoals")
            away_goals = m.get("away_team_goal_count") or m.get("awayGoals")
            try:
                home_goals = int(home_goals) if home_goals is not None else None
                away_goals = int(away_goals) if away_goals is not None else None
            except (ValueError, TypeError):
                home_goals, away_goals = None, None

        # Skip matches with no verified score data
        if home_goals is None or away_goals is None:
            logger.warning(
                f"[cron_audit] Skipping {home} vs {away} — no verified score data"
            )
            continue

        total_goals = home_goals + away_goals
        btts = home_goals > 0 and away_goals > 0
        if home_goals > away_goals:
            result_1x2 = "1"
        elif home_goals == away_goals:
            result_1x2 = "X"
        else:
            result_1x2 = "2"

        # Extract total corners for corner market evaluation
        home_corners = stats.get("homeCornersCount") or m.get("home_team_corner_count") or 0
        away_corners = stats.get("awayCornersCount") or m.get("away_team_corner_count") or 0
        try:
            home_corners = int(home_corners) if home_corners and int(home_corners) >= 0 else 0
            away_corners = int(away_corners) if away_corners and int(away_corners) >= 0 else 0
            total_corners = home_corners + away_corners
        except (ValueError, TypeError):
            total_corners = 0
        if any("ESCANTEIO" in (mc.get("mercado", mc.get("market", "")).upper()) for mc in mercados):
            logger.info(f"[audit] {home} vs {away}: corners home={home_corners} away={away_corners} total={total_corners}")

        # Extract total cards for card market evaluation (#085b — pattern #006)
        # Use `is None` checks — NOT `or` — because 0 is a valid value (pattern #078v)
        home_yellow = stats.get("homeYellowCards")
        if home_yellow is None:
            home_yellow = m.get("home_team_yellow_cards")
        if home_yellow is None:
            home_yellow = 0
        away_yellow = stats.get("awayYellowCards")
        if away_yellow is None:
            away_yellow = m.get("away_team_yellow_cards")
        if away_yellow is None:
            away_yellow = 0
        home_red = stats.get("homeRedCards")
        if home_red is None:
            home_red = m.get("home_team_red_cards")
        if home_red is None:
            home_red = 0
        away_red = stats.get("awayRedCards")
        if away_red is None:
            away_red = m.get("away_team_red_cards")
        if away_red is None:
            away_red = 0
        try:
            total_cards = int(home_yellow) + int(away_yellow) + int(home_red) + int(away_red)
        except (ValueError, TypeError):
            total_cards = 0
        if any("CART" in (mc.get("mercado", mc.get("market", "")).upper()) or "CARD" in (mc.get("mercado", mc.get("market", "")).upper()) for mc in mercados):
            logger.info(f"[audit] {home} vs {away}: cards hy={home_yellow} ay={away_yellow} hr={home_red} ar={away_red} total={total_cards}")

        actual_result = {
            "home_goals": home_goals,
            "away_goals": away_goals,
            "total_goals": total_goals,
            "btts": btts,
            "result_1x2": result_1x2,
            "total_corners": total_corners,
            "total_cards": total_cards,
        }

        picks_eval = []
        match_correct = 0
        match_total = 0

        for merc in mercados:
            merc_name = merc.get("mercado", merc.get("market", ""))
            merc_status = merc.get("status", merc.get("pick_type", "NEUTRO"))

            pick_dict = {"mercado": merc_name}
            is_correct = _evaluate_pick_deterministic(pick_dict, actual_result)

            picks_eval.append({
                "mercado": merc_name,
                "status_pick": merc_status,
                "resultado": "ACERTOU" if is_correct else "ERROU",
            })

            match_total += 1
            overall_total += 1
            if is_correct:
                match_correct += 1
                overall_correct += 1

            if merc_status == "SAFE":
                safe_total += 1
                if is_correct:
                    safe_correct += 1
            elif merc_status == "NEUTRO":
                neutro_total += 1
                if is_correct:
                    neutro_correct += 1

            market_key = merc_name.upper().strip()
            if market_key not in market_stats:
                market_stats[market_key] = {"correct": 0, "total": 0}
            market_stats[market_key]["total"] += 1
            if is_correct:
                market_stats[market_key]["correct"] += 1

            # #196: EV e odd do PROPRIO pick.
            #
            # Antes isto recalculava EV a partir de prob_max x odd_minima, que
            # nao sao os insumos do EV exibido no card: o card usa a
            # probabilidade calibrada (pos-deflacao) contra a odd real da casa,
            # enquanto prob_max e o topo da faixa exibida e odd_minima cai para
            # a odd justa (1/prob) quando nao ha odd real — nesse caso o EV
            # recalculado dava exatamente zero. Resultado: a auditoria media um
            # EV que ninguem viu na tela.
            _odds_reais = merc.get("book_odd")
            odd_pick = merc.get("odd_minima", 0) or 0
            _cal_prob = merc.get("calibrated_probability")
            prob_pick = (
                float(_cal_prob)
                if _cal_prob is not None
                else (merc.get("prob_max", 0) / 100.0 if merc.get("prob_max") else 0)
            )

            # #195: Brier do proprio pick (probabilidade declarada vs desfecho)
            _cal = merc.get("calibrated_probability")
            _pmin, _pmax = merc.get("prob_min"), merc.get("prob_max")
            _p = None
            if _cal is not None:
                try:
                    _p = float(_cal)
                except (TypeError, ValueError):
                    _p = None
            elif _pmin is not None and _pmax is not None:
                try:
                    _p = (float(_pmin) + float(_pmax)) / 200.0
                except (TypeError, ValueError):
                    _p = None
            if _p is not None and 0 < _p <= 1:
                pick_brier_scores.append((_p - (1 if is_correct else 0)) ** 2)
            ev_pick = None
            _ev_field = merc.get("ev")  # fracao (0.213 = +21,3%), quando o pipeline v2 rodou
            if _ev_field is not None:
                try:
                    ev_pick = float(_ev_field)
                except (TypeError, ValueError):
                    ev_pick = None
            if ev_pick is None and odd_pick > 0 and prob_pick > 0:
                # Fallback para mercados do caminho legado, que nao carregam `ev`.
                ev_pick = (prob_pick * (odd_pick - 1)) - (1 - prob_pick)
            if ev_pick is not None:
                ev_values.append(ev_pick)

            # #083: collect for diagnostic engine
            all_evaluated_picks.append({
                "match_id": m.get("id", f"{home}-{away}"),
                "league": league,
                "mercado": merc_name,
                "acertou": is_correct,
                "prob": prob_pick * 100 if prob_pick else 50,
                "ev": (ev_pick or 0) * 100 if ev_pick else 0,
                # #196: ROI so faz sentido com a odd que existia de verdade;
                # odd_minima vira a odd justa quando nao ha mercado, e isso
                # inflava o retorno simulado.
                "odd": float(_odds_reais) if _odds_reais else None,
                "odd_display": odd_pick,
                "lambda_home": stats.get("lambdaHome"),
                "lambda_away": stats.get("lambdaAway"),
                "draw_prob": stats.get("drawProb", 0),
                "projected_corners": stats.get("projectedTotalCornersFT"),
            })

            # Log individual pick to audit_results for calibrator training (Gap 3)
            try:
                _norm_market = merc_name.strip()
                actual_outcome = "hit" if is_correct else "miss"
                # #179: shadow snapshot of band 50-60% recalibration. When the
                # SHADOW_BAND_50_60_V179 env flag is OFF (default), prob_deflated
                # and prob_shadow_v179 are identical — observability only, no
                # behavior change. The endpoint /metrics/shadow_v179 compares them.
                _shadow_current = prob_pick
                _shadow_v179 = prob_pick
                _raw_prob = None  # #179: init before try so dict ref is crash-safe if import fails
                try:
                    from backend.services.ev_classification import (
                        apply_probability_deflation_with_shadow,
                    )
                    _raw_prob = merc.get("raw_probability")
                    if _raw_prob is not None:
                        _shadow_current, _shadow_v179 = apply_probability_deflation_with_shadow(
                            float(_raw_prob), league or ""
                        )
                except Exception:
                    pass
                audit_db.log_pick(
                    match_id=m.get("id", f"{home}-{away}"),
                    league=league,
                    market=_norm_market,
                    predicted_probs={
                        "prob": prob_pick,
                        "prob_raw": float(_raw_prob) if _raw_prob is not None else None,  # #179: habilita recompute
                        "prob_deflated": _shadow_current,  # #179
                        "prob_shadow_v179": _shadow_v179,  # #179
                        "market": _norm_market,
                        "odd": odd_pick if odd_pick > 0 else None,
                        # #196: `book_odd` so quando a odd e REAL. Antes gravava
                        # odd_minima, que vira a odd justa (1/prob) quando nao ha
                        # mercado — entao brier_implied, a "casa" na comparacao
                        # modelo-vs-casa do /metrics/brier, era a propria
                        # probabilidade do modelo nesses picks. Eles entravam com
                        # delta zero e diluiam a vantagem medida.
                        "book_odd": float(_odds_reais) if _odds_reais else None,
                    },
                    pick_type=merc_status,
                    ev=ev_pick,
                    context={
                        "regime": stats.get("leagueRegime", ""),
                        "source": "cron_batch",
                        # Lambda data for compute_lambda_error in backtesting
                        "lambdaHome": stats.get("lambdaHome"),
                        "lambdaAway": stats.get("lambdaAway"),
                        "lambdaTotal": stats.get("lambdaTotal"),
                        # Actual goals for compute_lambda_error in backtesting
                        "goals_home": home_goals,
                        "goals_away": away_goals,
                        "total_goals": total_goals,
                        # Corners for corners accuracy
                        "total_corners": total_corners,
                        # Classification metadata
                        "pick_classification": merc.get("classification", merc_status),
                        "reason_codes": merc.get("reason_codes", []),  # #129d: for shadow SAFE tracking
                        "data_quality": merc.get("data_quality_score"),
                    },
                    actual_result=actual_outcome,
                )
            except Exception as _log_err:
                logger.debug(f"[Gap3] Could not log pick {merc_name}: {_log_err}")

        # Lambda error: average per-team delta (#119c — was sum, now mean)
        lh = stats.get("lambdaHome")
        la = stats.get("lambdaAway")
        match_lambda_err = None
        if lh is not None and la is not None:
            try:
                match_lambda_err = (abs(float(lh) - home_goals) + abs(float(la) - away_goals)) / 2
                lambda_errors.append(match_lambda_err)
            except (ValueError, TypeError):
                pass

        over25_prob = stats.get("over25Prob")
        match_brier = None
        if over25_prob is not None:
            actual_over25 = 1 if total_goals > 2.5 else 0
            match_brier = (over25_prob / 100.0 - actual_over25) ** 2
            brier_scores.append(match_brier)
            ou_predictions.append({"prob": over25_prob / 100.0, "outcome": actual_over25})  # #079

        match_results.append({
            "match_id": m.get("id", ""),
            "home_team": home,
            "away_team": away,
            "league": league,
            "score": f"{home_goals}x{away_goals}",
            "picks_correct": match_correct,
            "picks_total": match_total,
        })

        # Accumulate per-league metrics (#069, #079)
        if league:
            lm = league_metrics.setdefault(league, {
                "correct": 0, "total": 0,
                "safe_correct": 0, "safe_total": 0,
                "brier_scores": [], "lambda_errors": [],
                "ou_predictions": [],  # #079: for per-league Log-Loss
            })
            lm["correct"] += match_correct
            lm["total"] += match_total
            if match_brier is not None:
                lm["brier_scores"].append(match_brier)
            if match_lambda_err is not None:
                lm["lambda_errors"].append(match_lambda_err)
            if over25_prob is not None:
                lm["ou_predictions"].append({"prob": over25_prob / 100.0, "outcome": actual_over25})
            # Per-league SAFE: count picks classified as SAFE for this match
            for merc in mercados:
                ms = merc.get("status", merc.get("pick_type", "NEUTRO"))
                if ms == "SAFE":
                    lm["safe_total"] += 1
                    pick_d = {"mercado": merc.get("mercado", merc.get("market", ""))}
                    if _evaluate_pick_deterministic(pick_d, actual_result):
                        lm["safe_correct"] += 1

    # ── Dupla (combinada) accuracy: INTRA and INTER ──
    # Build actual_result lookup by match ID for leg evaluation
    _actual_by_id: dict[str, dict] = {}
    for m in finished_matches:
        mid = m.get("id", "")
        score = m.get("score") or {}
        hg = score.get("home") if score else None
        ag = score.get("away") if score else None
        if hg is None or ag is None:
            _hg_raw = m.get("home_team_goal_count") or m.get("homeGoals")
            _ag_raw = m.get("away_team_goal_count") or m.get("awayGoals")
            try:
                hg = int(_hg_raw) if _hg_raw is not None else None
                ag = int(_ag_raw) if _ag_raw is not None else None
            except (ValueError, TypeError):
                hg, ag = None, None
        if hg is None or ag is None:
            continue  # Skip matches without verified score
        tg = hg + ag
        _btts = hg > 0 and ag > 0
        _1x2 = "1" if hg > ag else ("X" if hg == ag else "2")
        # Extract corners for dupla leg evaluation
        _stats = m.get("stats", {})
        _hc = _stats.get("homeCornersCount") or m.get("home_team_corner_count") or 0
        _ac = _stats.get("awayCornersCount") or m.get("away_team_corner_count") or 0
        try:
            _hc = int(_hc) if _hc and int(_hc) >= 0 else 0
            _ac = int(_ac) if _ac and int(_ac) >= 0 else 0
            _tc = _hc + _ac
        except (ValueError, TypeError):
            _tc = 0
        _actual_by_id[mid] = {"total_goals": tg, "btts": _btts, "result_1x2": _1x2, "total_corners": _tc}
        # Also index by homeTeam+awayTeam for leg matching
        hname = team_name(m.get("homeTeam")).strip().lower()
        aname = team_name(m.get("awayTeam")).strip().lower()
        if hname and aname:
            _actual_by_id[f"{hname}|{aname}"] = _actual_by_id[mid]

    def _find_actual_for_leg(leg: dict) -> dict | None:
        """Find actual result for a dupla leg by team names."""
        h = team_name(leg.get("homeTeam")).strip().lower()
        a = team_name(leg.get("awayTeam")).strip().lower()
        if h and a:
            key = f"{h}|{a}"
            if key in _actual_by_id:
                return _actual_by_id[key]
        return None

    dupla_stats = {"intra": {"correct": 0, "total": 0}, "inter": {"correct": 0, "total": 0}}
    try:
        from backend.services.combinadas_service import gerar_combinadas
        combinadas = gerar_combinadas(finished_matches, tipos=["intra", "inter"])
        for tipo in ("intra", "inter"):
            for dupla in combinadas.get(tipo, []):
                leg1 = dupla.get("leg1", {})
                leg2 = dupla.get("leg2", {})
                actual1 = _find_actual_for_leg(leg1)
                actual2 = _find_actual_for_leg(leg2)
                if actual1 is None or actual2 is None:
                    continue
                hit1 = _evaluate_pick_deterministic({"mercado": leg1.get("mercado", "")}, actual1)
                hit2 = _evaluate_pick_deterministic({"mercado": leg2.get("mercado", "")}, actual2)
                dupla_stats[tipo]["total"] += 1
                if hit1 and hit2:
                    dupla_stats[tipo]["correct"] += 1
    except Exception as e:
        logger.warning(f"[audit] Dupla accuracy calculation failed: {e}")

    intra_acc = (dupla_stats["intra"]["correct"] / dupla_stats["intra"]["total"] * 100.0) if dupla_stats["intra"]["total"] > 0 else 0.0
    inter_acc = (dupla_stats["inter"]["correct"] / dupla_stats["inter"]["total"] * 100.0) if dupla_stats["inter"]["total"] > 0 else 0.0
    logger.info(
        f"[audit] Duplas: INTRA {dupla_stats['intra']['correct']}/{dupla_stats['intra']['total']} ({intra_acc:.1f}%) | "
        f"INTER {dupla_stats['inter']['correct']}/{dupla_stats['inter']['total']} ({inter_acc:.1f}%)"
    )

    # Aggregate
    overall_accuracy_pct = (overall_correct / overall_total * 100.0) if overall_total > 0 else 0.0
    safe_accuracy_pct = (safe_correct / safe_total * 100.0) if safe_total > 0 else None  # #162: None when 0/0
    neutro_accuracy_pct = (neutro_correct / neutro_total * 100.0) if neutro_total > 0 else None  # #162
    avg_brier = sum(brier_scores) / len(brier_scores) if brier_scores else 0.0
    avg_pick_brier = (
        sum(pick_brier_scores) / len(pick_brier_scores) if pick_brier_scores else None
    )
    avg_lambda_error = sum(lambda_errors) / len(lambda_errors) if lambda_errors else 0.0
    avg_ev = sum(ev_values) / len(ev_values) if ev_values else 0.0

    # Build prompt data
    market_accuracy_list = []
    for mkt, data in sorted(market_stats.items()):
        acc = (data["correct"] / data["total"] * 100.0) if data["total"] > 0 else 0.0
        market_accuracy_list.append(f"- {mkt}: {data['correct']}/{data['total']} ({acc:.1f}%)")

    matches_summary_lines = []
    for mr in match_results[:20]:
        matches_summary_lines.append(
            f"- {mr['home_team']} {mr['score']} {mr['away_team']} ({mr['league']}) | "
            f"{mr['picks_correct']}/{mr['picks_total']} acertos"
        )

    # Build per-league accuracy text (#069: was missing — Brier/SAFE were global-only)
    league_accuracy_lines = []
    for lg_name in sorted(league_metrics):
        lm = league_metrics[lg_name]
        lg_acc = (lm["correct"] / lm["total"] * 100.0) if lm["total"] > 0 else 0.0
        lg_brier = sum(lm["brier_scores"]) / len(lm["brier_scores"]) if lm["brier_scores"] else None
        lg_lambda = sum(lm["lambda_errors"]) / len(lm["lambda_errors"]) if lm["lambda_errors"] else None
        lg_safe_acc = (lm["safe_correct"] / lm["safe_total"] * 100.0) if lm["safe_total"] > 0 else None
        parts = [f"{lg_name}: {lm['correct']}/{lm['total']} ({lg_acc:.1f}%)"]
        if lg_brier is not None:
            parts.append(f"Brier={lg_brier:.4f}")
        if lg_lambda is not None:
            parts.append(f"λErr={lg_lambda:.2f}")
        if lg_safe_acc is not None:
            parts.append(f"SAFE={lm['safe_correct']}/{lm['safe_total']}({lg_safe_acc:.0f}%)")
        league_accuracy_lines.append("- " + ", ".join(parts))

    batch_summary = {
        "total_audited": len(match_results),
        "overall_correct": overall_correct,
        "overall_total": overall_total,
        "overall_accuracy_pct": overall_accuracy_pct,
        "safe_correct": safe_correct,
        "safe_total": safe_total,
        "safe_accuracy_pct": safe_accuracy_pct,
        "neutro_correct": neutro_correct,
        "neutro_total": neutro_total,
        "neutro_accuracy_pct": neutro_accuracy_pct,
        "avg_brier_score": avg_brier,
        "brier_picks": avg_pick_brier,
        "brier_picks_n": len(pick_brier_scores),
        "avg_lambda_error": avg_lambda_error,
        "avg_ev": avg_ev,
        "market_accuracy_text": "\n".join(market_accuracy_list) or "Sem dados",
        "league_accuracy_text": "\n".join(league_accuracy_lines) or "Sem dados",
        "matches_summary_text": "\n".join(matches_summary_lines) or "Sem detalhes",
        "dupla_intra_correct": dupla_stats["intra"]["correct"],
        "dupla_intra_total": dupla_stats["intra"]["total"],
        "dupla_intra_accuracy_pct": intra_acc,
        "dupla_inter_correct": dupla_stats["inter"]["correct"],
        "dupla_inter_total": dupla_stats["inter"]["total"],
        "dupla_inter_accuracy_pct": inter_acc,
    }

    # #079: Add new metrics to batch_summary
    from backend.services.backtesting import compute_log_loss
    batch_log_loss = compute_log_loss(ou_predictions)
    batch_summary["log_loss"] = batch_log_loss

    # #084: Compute all pending metrics (Sharpe, Hit Rate by EV, Calibration, ROI, Baseline)
    from backend.services.backtesting import (
        compute_sharpe_ratio,
        compute_hit_rate_by_ev_band,
        compute_calibration_bins,
        compute_ece,
        compute_roi,
        compute_implied_odds_brier,
    )

    # Sharpe Ratio
    sharpe_picks = [
        {"odd": p.get("odd"), "outcome": p.get("acertou"), "stake": 1.0}
        for p in all_evaluated_picks
        if p.get("odd") and p.get("odd") > 1
    ]
    batch_summary["sharpe_ratio"] = compute_sharpe_ratio(sharpe_picks)

    # Hit Rate by EV band
    ev_band_picks = [
        {"ev_pct": p.get("ev", 0), "outcome": p.get("acertou", False), "odd": p.get("odd")}
        for p in all_evaluated_picks
    ]
    batch_summary["hit_rate_by_ev"] = compute_hit_rate_by_ev_band(ev_band_picks)

    # Reliability Diagram + ECE by band (#084, #100)
    calibration_preds = [
        {"prob": p["prob"], "outcome": p["outcome"]}
        for p in ou_predictions
        if p.get("prob") is not None and p.get("outcome") is not None
    ]
    ece_result = compute_ece(calibration_preds, n_bins=5)
    batch_summary["calibration"] = {
        "bins": compute_calibration_bins(calibration_preds) if len(calibration_preds) >= 30 else [],
        "ece": ece_result.get("ece_global"),
        "ece_faixas": ece_result.get("faixas", []),
        "n": ece_result.get("n_total", 0),
        "aviso": ece_result.get("aviso"),
    }

    # ROI / Yield
    roi_picks = [
        {"odd": p.get("odd", 0), "outcome": p.get("acertou", False), "stake": 1.0}
        for p in all_evaluated_picks
        if p.get("odd") and p.get("odd") > 1
    ]
    batch_summary["roi"] = compute_roi(roi_picks)

    # Baseline: model vs house odds (Brier comparison)
    baseline_picks = [
        {
            "odd": p.get("odd", 0),
            "prob": p.get("prob", 50) / 100.0 if p.get("prob", 0) > 1 else p.get("prob", 0.5),
            "outcome": p.get("acertou", False),
        }
        for p in all_evaluated_picks
        if p.get("odd") and p.get("odd") > 1
    ]
    batch_summary["odds_baseline"] = compute_implied_odds_brier(baseline_picks)

    # #162: EV summary metrics
    from backend.services.backtesting import compute_ev_summary, compute_weighted_accuracy
    ev_summary_picks = [
        {"ev": p.get("ev"), "classification": p.get("classification")}
        for p in all_evaluated_picks
    ]
    batch_summary["ev_metrics"] = compute_ev_summary(ev_summary_picks)

    # #163: Weighted accuracy (1/fair_odd)
    w_acc_picks = [
        {
            "outcome": p.get("acertou"),
            "fair_odd": 1.0 / p["prob"] if p.get("prob") and p["prob"] > 0 else None,
            "classification": p.get("classification"),
        }
        for p in all_evaluated_picks
    ]
    batch_summary["weighted_accuracy"] = compute_weighted_accuracy(w_acc_picks)

    # Model evaluation: deterministic rules (#079, #082)
    model_evaluation = None
    try:
        from backend.services.deterministic_audit import generate_deterministic_audit_report
        model_evaluation = generate_deterministic_audit_report(batch_summary, league_metrics)
        logger.info(f"Deterministic evaluation: {model_evaluation.get('overall_assessment', 'UNKNOWN')}")
    except Exception as e:
        logger.error(f"Batch evaluation failed in cron: {e}")

    # Post-Match Diagnostic Engine (#083)
    diagnostic_report = None
    try:
        from backend.services.post_match_diagnostic import run_post_match_diagnostic
        diagnostic_report = run_post_match_diagnostic(
            evaluated_picks=all_evaluated_picks,
            match_results=match_results,
            league_metrics=league_metrics,
            batch_summary=batch_summary,
            use_mistral_narrative=bool(os.getenv("MISTRAL_API_KEY")),
        )
        _diag_summary = diagnostic_report.get("pattern_report", {}).get("summary", {})
        logger.info(
            f"Diagnostic: {_diag_summary.get('total_errors', 0)} errors, "
            f"{len(diagnostic_report.get('pattern_report', {}).get('patterns', []))} patterns detected"
        )
    except Exception as e:
        logger.error(f"Post-match diagnostic failed: {e}")

    # Store result
    try:
        audit_db.log_audit_result(
            match_id=f"cron_batch:{date_filter}:{datetime.now().strftime('%Y%m%d')}",
            league="ALL",
            audit_data={
                "overall_accuracy": overall_accuracy_pct,
                "safe_accuracy": safe_accuracy_pct,
                "neutro_accuracy": neutro_accuracy_pct,
                "total_matches": len(match_results),
                "avg_brier_score": avg_brier,
                "brier_picks": avg_pick_brier,
                "brier_picks_n": len(pick_brier_scores),
                "avg_lambda_error": avg_lambda_error,
                "avg_ev": avg_ev,
                # #196: estas quatro ja eram calculadas todo dia em
                # batch_summary e morriam com o processo — o registro guardava
                # 10 campos e nenhum deles. Sem historico de ROI e de acerto
                # por faixa de EV nao ha como responder "os picks de VALOR
                # DETECTADO se pagam?", que e a pergunta que importa: com odd
                # longa, errar a maioria e lucrar sao compativeis.
                "hit_rate_by_ev": batch_summary.get("hit_rate_by_ev", []),
                "roi": batch_summary.get("roi", {}),
                "ev_metrics": batch_summary.get("ev_metrics", {}),
                "sharpe_ratio": batch_summary.get("sharpe_ratio"),
                "model_evaluation_summary": model_evaluation.get("overall_assessment", "") if model_evaluation else "",
            },
            match_status="cron_batch_audit",
            user="cron",
        )
    except Exception as e:
        logger.warning(f"Could not store cron batch audit result: {e}")

    # Auto-apply high-confidence corrections from model evaluation (with validation)
    auto_applied = []
    rejected = []
    # #171 emergency: env-var-gated circuit breaker. Default 101 = impossible
    # to satisfy (max confidence is 80) → no auto-apply. Set to 80 to restore
    # legacy behaviour after root cause is fixed and validated.
    AUTO_APPLY_CONFIDENCE_THRESHOLD = int(os.getenv("AUTO_APPLY_CONFIDENCE_MIN", "101"))
    if model_evaluation and model_evaluation.get("recommended_corrections"):
        from backend.audit import validate_adjustment, audit_logger
        for corr in model_evaluation["recommended_corrections"]:
            confidence = corr.get("confidence", 0)
            # #171: gated by AUTO_APPLY_CONFIDENCE_MIN env var
            if confidence >= AUTO_APPLY_CONFIDENCE_THRESHOLD:
                try:
                    old_val = float(corr.get("current_value", 0))
                    new_val = float(corr.get("suggested_value", 0))
                    param = corr.get("parameter", "")
                    corr_type = corr.get("type", "")

                    # Validate adjustment is within safety limits
                    is_valid, reason = validate_adjustment(corr_type, param, old_val, new_val)
                    if not is_valid:
                        rejected.append(param)
                        logger.warning(f"Correction rejected: {param} — {reason}")
                        audit_logger.info(
                            f"[CRON] Correcao rejeitada: parameter={param}, "
                            f"old={old_val}, new={new_val}, reason={reason}"
                        )
                        continue

                    audit_db.log_correction(
                        match_id=f"cron_auto_{datetime.now().strftime('%Y%m%d')}",
                        league="ALL",
                        correction_type=corr_type,
                        parameter_name=param,
                        old_value=old_val,
                        new_value=new_val,
                        suggested_by="mistral_cron_audit",
                        applied_by="cron_auto",
                        audit_confidence=confidence,
                        reason=corr.get("reason", ""),
                    )
                    auto_applied.append(param)
                    logger.info(f"Auto-applied correction: {param} ({old_val} -> {new_val})")
                except Exception as e:
                    logger.warning(f"Failed to auto-apply correction: {e}")

    # Increment app version if corrections were applied
    if auto_applied:
        try:
            from backend.audit import increment_version, audit_logger as _al
            new_ver = increment_version()
            _al.info(f"[CRON] Versao atualizada: {new_ver} apos {len(auto_applied)} correcoes")
            logger.info(f"Version incremented to {new_ver}")
        except Exception as e:
            logger.warning(f"Failed to increment version: {e}")

    # Improvement #2: auto-trigger calibrator retraining after batch audit
    # when enough new data has been accumulated
    calibrator_results = []
    calibrator_retrain_status = "disabled_leaked_source"
    if not _calibrator_retrain_enabled():
        logger.warning(
            "[CRON][#200] Auto-retreino de calibradores IGNORADO: a fonte "
            "(audit_results) contem prognostico recomputado pos-jogo. "
            "Defina CRON_AUTO_RETRAIN_CALIBRATORS=1 para reabilitar."
        )
    else:
        calibrator_retrain_status = "enabled_by_env"
        try:
            from backend.modeling.calibrator import retrain_all_calibrators
            cal_results = retrain_all_calibrators()
            calibrator_results = [r for r in cal_results if r and r.get("accepted")]
            if calibrator_results:
                logger.info(
                    f"[CRON] Auto-retrained {len(calibrator_results)} calibrators "
                    f"after batch audit"
                )
        except Exception as e:
            calibrator_retrain_status = "error"
            logger.warning(f"[CRON] Calibrator retraining after audit failed: {e}")

    result = {
        "status": "success",
        "triggered_by": "eventbridge_cron",
        "timestamp": datetime.now().isoformat(),
        "audited_matches": len(match_results),
        "overall_accuracy": round(overall_accuracy_pct, 1),
        "safe_accuracy": round(safe_accuracy_pct, 1) if safe_accuracy_pct is not None else None,
        "neutro_accuracy": round(neutro_accuracy_pct, 1) if neutro_accuracy_pct is not None else None,
        "avg_brier_score": round(avg_brier, 4),
        "brier_picks": round(avg_pick_brier, 4) if avg_pick_brier is not None else None,
        "brier_picks_n": len(pick_brier_scores),
        "avg_ev": round(avg_ev, 4),
        "model_assessment": model_evaluation.get("overall_assessment", "") if model_evaluation else "N/A",
        "dupla_intra_accuracy": round(intra_acc, 1),
        "dupla_intra_total": dupla_stats["intra"]["total"],
        "dupla_inter_accuracy": round(inter_acc, 1),
        "dupla_inter_total": dupla_stats["inter"]["total"],
        "auto_corrections_applied": len(auto_applied),
        "auto_corrections": auto_applied,
        "rejected_corrections": len(rejected),
        "calibrators_retrained": len(calibrator_results),
        "calibrator_retrain_status": calibrator_retrain_status,
        "diagnostic": diagnostic_report,
        "ev_metrics": batch_summary.get("ev_metrics", {}),
        "hit_rate_by_ev": batch_summary.get("hit_rate_by_ev", []),
        "roi": batch_summary.get("roi", {}),
        "weighted_accuracy": batch_summary.get("weighted_accuracy", {}),
    }

    logger.info(f"Cron batch audit completed: {json.dumps(result)}")

    # Cleanup old reliability events (#102)
    try:
        from backend.services.reliability_tracker import cleanup_old_events
        cleanup_old_events(days=90)
    except Exception:
        pass

    # Update ELO ratings for finished matches (#107d)
    try:
        from backend.services.elo_service import update_elo_after_match
        for mr in match_results:
            score = mr.get("score", "0x0")
            parts = score.split("x") if "x" in str(score) else ["0", "0"]
            hg = int(parts[0]) if parts[0].isdigit() else 0
            ag = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
            update_elo_after_match(
                mr.get("home_team", ""), mr.get("away_team", ""),
                mr.get("league", ""), hg, ag,
            )
    except Exception:
        pass

    # Calculate and persist Brier snapshot (#109)
    try:
        from backend.services.brier_service import run_after_audit
        n_eval = len(all_evaluated_picks) if "all_evaluated_picks" in dir() else 0
        brier_snap = run_after_audit(new_picks=n_eval, audit_date=date_filter)
        if brier_snap:
            result["brier_snapshot"] = {
                "total_picks": brier_snap["total_picks"],
                "brier_model": brier_snap.get("brier_model"),
                "model_beats_house": brier_snap.get("model_beats_house"),
                "accuracy": brier_snap.get("accuracy"),
            }
    except Exception:
        pass

    # #129d: Check shadow SAFE activation
    try:
        _check_shadow_safe_activation(all_evaluated_picks if "all_evaluated_picks" in dir() else [])
    except Exception as e:
        logger.error(f"Shadow SAFE check failed: {e}")

    return result


def _check_shadow_safe_activation(recent_picks: list) -> None:
    """Check if shadow SAFE picks have enough data to activate SAFE.

    Queries audit_results for picks with SAFE_CIRCUIT_BREAKER reason code,
    counts hits, and if accuracy > 50% with N >= 50: activates SAFE.
    """
    MIN_SHADOW_PICKS = 50
    MIN_ACCURACY = 0.50

    # Count shadow SAFE picks from recent audit
    shadow_picks = [
        p for p in recent_picks
        if "SAFE_CIRCUIT_BREAKER" in str(p.get("reason_codes", p.get("pick_classification", "")))
    ]

    # Also count from full backtest (30 days)
    try:
        from backend.services.backtesting import run_backtest
        bt = run_backtest(days=30)
        # hit_rate gives overall accuracy but not per-classification
        # For now, log the count and defer to manual check
        n_picks = bt.get("n_picks", 0)
    except Exception:
        n_picks = 0

    total_shadow = len(shadow_picks)
    if total_shadow > 0:
        hits = sum(1 for p in shadow_picks if p.get("hit") or p.get("outcome") == "hit")
        accuracy = hits / total_shadow if total_shadow > 0 else 0
        logger.info(
            f"[shadow-safe] {total_shadow} shadow picks in this batch, "
            f"{hits} hits ({accuracy:.1%}). Need {MIN_SHADOW_PICKS} total for activation."
        )
    else:
        logger.info("[shadow-safe] No shadow SAFE picks in this batch.")

    # Note: Full shadow accuracy measurement requires querying audit_results
    # for all picks with SAFE_CIRCUIT_BREAKER. This is deferred to the
    # /health/safe-status endpoint which already tracks reactivation criteria.
    # The cron logs progress; manual activation via endpoint when ready.


def _run_late_audit() -> dict:
    """#160: Late-night audit for Americas matches finishing after 23:45 BRT.

    Scheduled: cron(0 5 * * ? *) → 05:00 UTC = 02:00 BRT.

    Strategy: runs batch_audit for "today" (BRT date = yesterday calendar since
    it's now 02:00 BRT of the new day). Uses the previous BRT calendar day to
    catch Liga MX, MLS, Copa Libertadores etc. that finished between 23:45-01:59 BRT.

    Only audits matches NOT already audited by today_audit (dedup by match ID).
    """
    from backend.routes.ai_analysis import _get_all_finished_matches
    from datetime import timezone as _tz_mod, timedelta as _td_local
    from datetime import datetime as _dt_local

    _BRT = _tz_mod(_td_local(hours=-3))
    # At 02:00 BRT, "yesterday" in BRT = the calendar day whose late matches we want
    yesterday_brt = (_dt_local.now(_BRT) - _td_local(days=1)).strftime("%Y-%m-%d")

    logger.info(f"[late_audit] Starting late audit for {yesterday_brt} (Americas late matches)")

    # Fetch all finished matches for that BRT date — no time cutoff
    result = _run_batch_audit(yesterday_brt)

    # Tag the result so we know it came from late_audit
    result["audit_type"] = "late_audit"
    result["target_date"] = yesterday_brt

    return result


def _calibrator_retrain_enabled() -> bool:
    """#200 - porta de seguranca do retreino automatico de calibradores.

    Os calibradores sao treinados a partir de `audit_results`, que hoje guarda
    o prognostico RECOMPUTADO depois do jogo, nao o publicado. Isso e vazamento:
    picks que erraram trocam de lado no recomputo e somem da amostra, entao a
    curva de calibracao aprende com um passado que nunca existiu - e ela entra
    em producao via `calibrate_prob()`, antes da classificacao e do EV.

    Enquanto o ledger de picks publicados nao existir, o retreino fica DESLIGADO
    por padrao. Ligar exige `CRON_AUTO_RETRAIN_CALIBRATORS=1` explicito.
    """
    return os.getenv("CRON_AUTO_RETRAIN_CALIBRATORS", "0").strip().lower() in (
        "1", "true", "yes", "on"
    )


def _run_retrain_calibrators(force: bool = False) -> dict:
    """Retrain Isotonic Regression calibrators for all active leagues (Gap 5).

    Scheduled weekly: cron(0 4 ? * MON *) → 04:00 UTC Monday.
    Uses season_start boundary per league (not a fixed 90-day window).
    """
    if not (force or _calibrator_retrain_enabled()):
        logger.warning(
            "[CRON][#200] Retreino semanal de calibradores IGNORADO: fonte "
            "com vazamento (audit_results recomputado). Use "
            "CRON_AUTO_RETRAIN_CALIBRATORS=1 ou event={'force': true}."
        )
        return {
            "status": "skipped",
            "reason": "calibrator_retrain_disabled",
            "detail": "audit_results contem prognostico recomputado pos-jogo (#200)",
        }
    try:
        from backend.modeling.calibrator import retrain_all_calibrators
        results = retrain_all_calibrators()
        logger.info(f"Calibrator retraining completed: {results}")
        return {"status": "success", "calibrators": results}
    except Exception as e:
        logger.error(f"Calibrator retraining failed: {e}")
        return {"status": "error", "message": str(e)}


def coletar_partidas_escanteios(
    cliente=None,
    ligas=None,
    n_temporadas: int = 2,
) -> dict:
    """Coleta partidas historicas por liga para o retrain de escanteios (#226).

    Substitui o bloco que nunca coletou nada: ele importava
    `footstats_client.get_league_matches` (que e **metodo** de
    `FootyStatsClient`, nao funcao de modulo) e `leagues_config.SUPPORTED_LEAGUES`
    (que nao existe — o nome e `LEAGUES_CONFIG`). Os dois no mesmo
    `try/except ImportError`, entao toda segunda-feira o job registrava
    "footstats_client not available" e devolvia `skipped` — com o modulo
    presente o tempo inteiro.

    `cliente` e `ligas` sao injetaveis para o teste rodar sem rede.

    Returns:
        {league_id: [partidas]} — so ligas que devolveram alguma partida.
    """
    from backend.config.leagues_config import LEAGUES_CONFIG

    if cliente is None:
        from backend.services.footstats_client import FootyStatsClient
        cliente = FootyStatsClient()

    ligas = LEAGUES_CONFIG if ligas is None else ligas
    coletadas: dict = {}

    for liga in ligas:
        league_id = primeiro_valido(liga.get("id"), liga.get("slug"), padrao="")
        if not league_id:
            continue
        try:
            temporadas = cliente.resolve_season_ids(
                liga.get("country", ""), liga.get("name", ""),
                alt_names=liga.get("alt_names"), n_seasons=n_temporadas,
            )
            if not temporadas:
                logger.warning(f"[Corners][coleta] {league_id}: sem season_id")
                continue

            partidas = []
            for season_id, _nome in temporadas:
                resposta = cliente.get_all_league_matches(int(season_id)) or {}
                partidas.extend(resposta.get("data") or [])

            if partidas:
                coletadas[league_id] = partidas
                logger.info(f"[Corners][coleta] {league_id}: {len(partidas)} partidas "
                            f"em {len(temporadas)} temporada(s)")
            else:
                logger.warning(f"[Corners][coleta] {league_id}: 0 partidas")
        except Exception as e:
            logger.warning(f"[Corners][coleta] {league_id} falhou: {e}")

    logger.info(f"[Corners][coleta] {len(coletadas)}/{len(ligas)} ligas com dados")
    return coletadas


def _run_retrain_corners() -> dict:
    """Retrain corner models for all leagues (weekly).

    Scheduled: cron(0 5 ? * MON *) → 05:00 UTC Monday.
    Runs end-to-end corner pipeline: train 3 models, compare, select champion,
    generate artifacts, determine operational states.

    Initial deployment: force_shadow=True (cap at NEUTRAL).
    """
    logger.info("[Corners] Starting weekly corner retrain")
    try:
        from backend.modeling.corners.retrain import retrain_all_leagues

        training_data = coletar_partidas_escanteios()

        if not training_data:
            return {
                "status": "skipped",
                "message": (
                    "coleta nao devolveu partidas — sem FOOTYSTATS_API_KEY valida "
                    "ou a API nao respondeu (ver avisos [Corners][coleta] acima)"
                ),
            }

        results = retrain_all_leagues(training_data, force_shadow=True)
        completed = [r for r in results if r.get("status") == "completed"]

        logger.info(
            f"[Corners] Retrain completed: {len(completed)}/{len(results)} leagues successful"
        )
        return {
            "status": "success",
            "leagues_processed": len(results),
            "leagues_completed": len(completed),
            "results": [{
                "league_id": r.get("league_id"),
                "status": r.get("status"),
                # #226: sem isto, `insufficient_data` nao diz SE faltou partida
                # ou se faltou CONTAGEM de escanteios nas partidas — que e o
                # que o #225-a mediu em 0/48 na championship.
                "n_matches": r.get("n_matches"),
                "n_valid_corners": r.get("n_valid_corners"),
                "champion": (r.get("champion_selection") or {}).get("dominant_champion"),
            } for r in results],
        }
    except Exception as e:
        logger.error(f"[Corners] Weekly retrain failed: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


def _run_snapshot_standings() -> dict:
    """Snapshot diario de standings em S3 (REGRA #173).

    Sem snapshots historicos, e impossivel fazer backtest de features de
    contexto de temporada (rebaixados, briga pelo titulo, meio da tabela).
    Em ~3-6 meses de coleta temos historico suficiente.

    Scheduled (recomendado): cron(0 6 * * ? *) -> 06:00 UTC = 03:00 BRT.
    Apos batch_audit (23:00 UTC) + late_audit (05:00 UTC) — fora do
    horario de pico para nao concorrer com auditoria.
    """
    logger.info("[snapshot_standings] Starting daily standings snapshot")
    try:
        from backend.services.standings_snapshot import snapshot_all_leagues_to_s3
        result = snapshot_all_leagues_to_s3()
        logger.info(f"[snapshot_standings] Done: {result.get('uploaded')}/{result.get('uploaded', 0) + result.get('failed', 0)} uploaded")
        return result
    except Exception as e:
        logger.error(f"[snapshot_standings] Failed: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


def _run_threshold_adjustment() -> dict:
    """Auto-adjust thresholds based on accumulated Brier scores."""
    from backend import audit as audit_db

    logger.info("Starting automated threshold adjustment")

    defaults = {
        "1X2": {"SAFE": 0.60, "NEUTRO": 0.50},
        "Over/Under": {"SAFE": 0.60, "NEUTRO": 0.50},
        "BTTS": {"SAFE": 0.60, "NEUTRO": 0.50},
        "Double Chance": {"SAFE": 0.60, "NEUTRO": 0.50},
    }

    try:
        audit_db.adjust_thresholds(defaults)
        logger.info("Threshold adjustment completed successfully")
        return {"status": "success", "message": "Thresholds ajustados com sucesso"}
    except Exception as e:
        logger.error(f"Threshold adjustment failed: {e}")
        return {"status": "error", "message": str(e)}
