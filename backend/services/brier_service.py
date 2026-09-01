"""Brier Score calculation and persistence (#109).

Calculates segmented Brier after each batch audit and persists to PostgreSQL.
"""

import json
import logging
import os
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional

# #182 — scipy import lazy inside _with_ci. Top-level import broke production
# Lambda (numpy._core.tests missing in the bundled scipy/numpy combination).
# Locally scipy is available; lazily importing keeps the happy path intact and
# fails open with p_value=None when the Lambda Layer can't satisfy scipy.

logger = logging.getLogger("sportsbankzu.brier")

MIN_N = 20  # REGRA #079
BRIER_TARGET = 0.22  # #178: single canonical value — UI + alerts must align


def _conn():
    import psycopg2
    return psycopg2.connect(os.environ.get("DATABASE_URL", ""))


def _ensure_table():
    try:
        conn = _conn()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS brier_history (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP DEFAULT NOW(),
                total_picks INTEGER NOT NULL,
                brier_model FLOAT,
                brier_implied FLOAT,
                model_beats_house BOOLEAN,
                delta FLOAT,
                accuracy FLOAT,
                by_league JSONB,
                by_market JSONB,
                by_band JSONB,
                by_classification JSONB,
                by_league_market JSONB,
                new_picks INTEGER DEFAULT 0,
                audit_date TEXT
            )
        """)
        cur.execute("""
            ALTER TABLE brier_history
            ADD COLUMN IF NOT EXISTS by_league_market JSONB
        """)
        # #199: payload completo do snapshot. As colunas soltas nao guardam
        # model_beats_house_ci (que o ReliabilityCard le) nem os campos novos
        # do #197 — servir o card a partir das colunas quebraria a tela.
        cur.execute("""
            ALTER TABLE brier_history
            ADD COLUMN IF NOT EXISTS snapshot JSONB
        """)
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logger.debug(f"[Brier] ensure_table: {e}")


def _brier(probs, outcomes):
    if not probs:
        return None
    return sum((p - o) ** 2 for p, o in zip(probs, outcomes)) / len(probs)


def _with_ci(picks, brier_model, brier_implied):
    """#178 — model_beats_house with Wilcoxon paired test.

    Returns dict {beats_bool, delta, p_value, n, significant_at_5pct, below_min_n}.
    significant_at_5pct=False if N<MIN_N (REGRA #079) regardless of delta.
    """
    n = len(picks)
    if n < MIN_N or brier_model is None or brier_implied is None:
        return {
            "beats_bool": False,
            "delta": None,
            "p_value": None,
            "n": n,
            "significant_at_5pct": False,
            "below_min_n": n < MIN_N,
        }
    bm_per = [(p["prob"] - p["out"]) ** 2 for p in picks if p.get("odd")]
    bi_per = [((1.0 / p["odd"]) - p["out"]) ** 2 for p in picks if p.get("odd")]
    n_paired = min(len(bm_per), len(bi_per))
    if n_paired < MIN_N:
        return {
            "beats_bool": False,
            "delta": None,
            "p_value": None,
            "n": n_paired,
            "significant_at_5pct": False,
            "below_min_n": True,
        }
    try:
        # #182 — lazy import; ImportError on Lambda surfaces here, not at module load.
        from scipy.stats import wilcoxon
        _, pval = wilcoxon(bm_per[:n_paired], bi_per[:n_paired])
    except Exception:
        # Covers both ImportError (Lambda Layer mismatch) and degenerate-input
        # cases (e.g. all-zero diffs). p_value=None disables significance test;
        # significant_at_5pct will be False.
        pval = None
    delta = brier_implied - brier_model
    return {
        "beats_bool": bool(brier_model < brier_implied),
        "delta": round(delta, 5),
        "p_value": round(float(pval), 5) if pval is not None else None,
        "n": n_paired,
        "significant_at_5pct": bool(pval is not None and pval < 0.05 and delta > 0),
        "below_min_n": False,
    }


def _segment(picks):
    """Metricas de um recorte de picks.

    #197 — pareamento. A versao anterior fazia:

        odds = [p["odd"] for p in picks if p.get("odd")]
        bi = _brier([1/o for o in odds], outs[:len(odds)])

    `odds` e filtrado, `outs` nao. Os desfechos usados eram os dos PRIMEIROS
    len(odds) picks da lista, nao os dos picks que tem odd — comparacao com
    resultados de outros jogos sempre que algum pick nao tinha odd. Ate agora
    isso passava batido porque `book_odd` recebia odd_minima e quase todo pick
    tinha odd (5.844 pareados de 5.915, 1,2% de falta), e por isso o delta do
    _segment batia com o do _with_ci, que sempre pareou certo.

    O #196 passou a gravar book_odd so quando a odd e REAL — cerca de um terco
    dos picks fica sem odd. Sem esta correcao, brier_implied, delta e
    model_beats_house virariam ruido em todos os recortes a partir do proximo
    batch.

    #197 — comparacao no mesmo conjunto. `delta` agora e modelo-vs-casa sobre
    os MESMOS picks pareados. Antes comparava o Brier do modelo em todos os
    picks contra o da casa num subconjunto — grandezas de populacoes
    diferentes. `brier_model` segue reportado sobre o total (e a nota geral do
    modelo); quem decide "bate a casa?" e o par (brier_model_paired,
    brier_implied).
    """
    n = len(picks)
    if n == 0:
        return None
    probs = [p["prob"] for p in picks]
    outs = [p["out"] for p in picks]
    bm = _brier(probs, outs)
    acc = sum(outs) / n * 100

    paired = [p for p in picks if p.get("odd")]
    if len(paired) >= n * 0.5:
        bi = _brier([1.0 / p["odd"] for p in paired], [p["out"] for p in paired])
        bm_paired = _brier([p["prob"] for p in paired], [p["out"] for p in paired])
    else:
        bi = None
        bm_paired = None

    beats = bm_paired < bi if bm_paired is not None and bi is not None else None
    delta = bi - bm_paired if bm_paired is not None and bi is not None else None
    return {
        "n": n,
        "accuracy": round(acc, 1),
        "brier_model": round(bm, 4) if bm else None,
        "brier_model_paired": round(bm_paired, 4) if bm_paired else None,
        "brier_implied": round(bi, 4) if bi else None,
        "n_paired": len(paired),
        "model_beats_house": beats,
        "delta": round(delta, 4) if delta else None,
        "model_beats_house_ci": _with_ci(picks, bm_paired, bi),
    }


def _row_to_pick(market, league, result, pp_raw, ctx_raw, ptype) -> Optional[Dict]:
    """Normaliza uma linha de audit_results num pick comparavel. None = descartar."""
    outcome = 1 if result == "hit" else (0 if result == "miss" else None)
    if outcome is None:
        return None
    pp = json.loads(pp_raw) if isinstance(pp_raw, str) else (pp_raw or {})
    ctx = json.loads(ctx_raw) if isinstance(ctx_raw, str) else (ctx_raw or {})
    prob = pp.get("prob")
    if prob is None:
        return None
    prob = float(prob)
    if prob > 1:
        prob /= 100
    odd = pp.get("book_odd") or pp.get("odd")
    odd = float(odd) if odd and float(odd) > 1 else None
    cls = ctx.get("pick_classification", ptype or "?")
    return {"prob": prob, "odd": odd, "out": outcome, "league": league, "market": market, "cls": cls}


def _normalize_audit_date(value) -> Optional[str]:
    """Devolve uma data ISO utilizavel na query, ou None.

    #197 — o cron chama run_after_audit(audit_date=date_filter), e date_filter
    e um ROTULO ("today", "yesterday", "week"), nunca uma data. O #195 passou a
    injetar esse valor num `DATE("timestamp") = %s`; o Postgres recusa
    ("invalid input syntax for type date"), o except de _load_picks engolia a
    excecao, calculate_snapshot devolvia None e persist_snapshot nunca rodava —
    o snapshot noturno parou de ser gravado sem nenhum sinal na interface.

    Rotulo nao vira filtro: devolve None (snapshot completo, comportamento
    anterior ao #195) e registra o motivo.
    """
    if not value:
        return None
    text = str(value).strip()
    try:
        datetime.strptime(text, "%Y-%m-%d")
        return text
    except ValueError:
        logger.warning(
            "[Brier] audit_date=%r nao e uma data ISO — snapshot calculado sobre "
            "todos os picks (sem filtro de dia).", text
        )
        return None


def _load_picks(audit_date: str = None, since_days: int = None) -> Optional[List[Dict]]:
    """Le picks resolvidos de audit_results.

    #195: `audit_date` passa a filtrar de verdade. Antes `calculate_snapshot`
    aceitava o parametro e o unico uso era ecoa-lo no retorno — a query lia a
    tabela inteira, entao nao havia como fatiar o Brier por dia.

    #197: so filtra quando o valor e uma data ISO (ver _normalize_audit_date).
    """
    where = ["pick_type != 'AUDIT'"]
    params: list = []
    iso_date = _normalize_audit_date(audit_date)
    if iso_date:
        where.append('DATE("timestamp") = %s')
        params.append(iso_date)
    elif since_days:
        where.append('"timestamp" >= NOW() - MAKE_INTERVAL(days => %s)')
        params.append(int(since_days))
    try:
        conn = _conn()
        cur = conn.cursor()
        cur.execute(
            'SELECT market, league, actual_result, predicted_probs, context, pick_type, '
            'DATE("timestamp") AS d '
            "FROM audit_results WHERE " + " AND ".join(where),
            tuple(params),
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
    except Exception as e:
        # #197: era aqui que a regressao morria calada. Mantemos o fail-safe
        # (nunca derrubar o cron), mas o log passa a nomear a query.
        logger.error(f"[Brier] fetch failed (audit_date={audit_date!r}, since_days={since_days!r}): {e}")
        return None

    picks = []
    for market, league, result, pp_raw, ctx_raw, ptype, day in rows:
        pk = _row_to_pick(market, league, result, pp_raw, ctx_raw, ptype)
        if pk is None:
            continue
        pk["day"] = str(day) if day else None
        picks.append(pk)
    return picks


def daily_series(days: int = 30) -> List[Dict]:
    """#195: serie diaria de acuracia e Brier — uma linha por dia.

    E o que faltava para responder "a queda comecou no deploy X?": o snapshot
    cumulativo dilui qualquer degrau recente em milhares de picks antigos.
    """
    picks = _load_picks(since_days=days)
    if not picks:
        return []
    by_day = defaultdict(list)
    for p in picks:
        if p.get("day"):
            by_day[p["day"]].append(p)
    out = []
    for day in sorted(by_day.keys()):
        seg = _segment(by_day[day])
        if seg:
            out.append({"date": day, **seg})
    return out


def calculate_snapshot(audit_date: str = None) -> Optional[Dict]:
    """Calculate complete Brier snapshot.

    #195: com `audit_date` o snapshot cobre so aquele dia; sem ele, tudo.
    """
    picks = _load_picks(audit_date=audit_date)
    if not picks:
        return None

    gl = _segment(picks)

    # By league
    by_league = {}
    lg = defaultdict(list)
    for p in picks:
        lg[p["league"]].append(p)
    for k, v in lg.items():
        if len(v) >= MIN_N:
            by_league[k] = _segment(v)

    # By market
    by_market = {}
    mk = defaultdict(list)
    for p in picks:
        mk[p["market"]].append(p)
    for k, v in mk.items():
        if len(v) >= MIN_N:
            by_market[k] = _segment(v)

    # By band
    by_band = {}
    for lo, hi, label in [(0, 0.5, "<50%"), (0.5, 0.6, "50-60%"), (0.6, 0.7, "60-70%"), (0.7, 0.8, "70-80%"), (0.8, 1.01, "80%+")]:
        bp = [p for p in picks if lo <= p["prob"] < hi]
        if bp:
            ap = sum(p["prob"] for p in bp) / len(bp)
            ao = sum(p["out"] for p in bp) / len(bp)
            by_band[label] = {"n": len(bp), "avg_prob": round(ap, 3), "avg_outcome": round(ao, 3), "gap": round(ap - ao, 3), "calibrated": abs(ap - ao) < 0.05}

    # By classification
    by_cls = {}
    cg = defaultdict(list)
    for p in picks:
        cg[p["cls"]].append(p)
    for k, v in cg.items():
        by_cls[k] = _segment(v)

    # By league x market (joint - #177)
    # MIN_N=5 for diagnostic; segments with N<MIN_N (20, REGRA #079) carry diagnostic_only=True.
    JOINT_MIN_N_DIAGNOSTIC = 5
    by_league_market = {}
    lmk = defaultdict(list)
    for p in picks:
        if p.get("league") and p.get("market"):
            lmk[(p["league"], p["market"])].append(p)
    for (lg, mk), v in lmk.items():
        if len(v) >= JOINT_MIN_N_DIAGNOSTIC:
            seg = _segment(v)
            if seg:
                seg["diagnostic_only"] = len(v) < MIN_N
                by_league_market[f"{lg}|||{mk}"] = seg

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "total_picks": len(picks),
        "audit_date": audit_date or datetime.utcnow().strftime("%Y-%m-%d"),
        **gl,
        "by_league": by_league,
        "by_market": by_market,
        "by_band": by_band,
        "by_classification": by_cls,
        "by_league_market": by_league_market,
    }


def persist_snapshot(snapshot: Dict, new_picks: int = 0) -> bool:
    """Save snapshot to PostgreSQL."""
    try:
        _ensure_table()
        conn = _conn()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO brier_history (total_picks,brier_model,brier_implied,model_beats_house,"
            "delta,accuracy,by_league,by_market,by_band,by_classification,by_league_market,"
            "new_picks,audit_date,snapshot) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                snapshot["total_picks"], snapshot.get("brier_model"), snapshot.get("brier_implied"),
                snapshot.get("model_beats_house"), snapshot.get("delta"), snapshot.get("accuracy"),
                json.dumps(snapshot.get("by_league", {})), json.dumps(snapshot.get("by_market", {})),
                json.dumps(snapshot.get("by_band", {})), json.dumps(snapshot.get("by_classification", {})),
                json.dumps(snapshot.get("by_league_market", {})),
                new_picks, snapshot.get("audit_date"), json.dumps(snapshot),
            ),
        )
        conn.commit()
        cur.close()
        conn.close()
        logger.info(f"[Brier] Snapshot saved: {snapshot['total_picks']} picks, beats={snapshot.get('model_beats_house')}")
        return True
    except Exception as e:
        logger.error(f"[Brier] persist failed: {e}")
        return False


def latest_snapshot() -> Optional[Dict]:
    """#199: ultimo snapshot gravado, com a idade explicita.

    O /metrics/brier recalculava tudo a cada carregamento do dashboard — le
    audit_results inteira e segmenta por liga, mercado, banda, classificacao e
    liga x mercado. Entre um batch e outro o resultado e identico, entao era
    trabalho jogado fora, e passou a estourar o timeout da rota.

    A idade vai no payload de proposito: se o cron parar, o card mostra dado
    velho COM a etiqueta de quando foi, em vez de mentir por omissao.
    """
    try:
        conn = _conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT snapshot, timestamp FROM brier_history "
            "WHERE snapshot IS NOT NULL ORDER BY timestamp DESC LIMIT 1"
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
    except Exception as e:
        logger.warning(f"[Brier] latest_snapshot falhou: {e}")
        return None

    if not row or not row[0]:
        return None
    snap = json.loads(row[0]) if isinstance(row[0], str) else row[0]
    ts = row[1]
    age_min = None
    if ts is not None:
        try:
            age_min = int((datetime.utcnow() - ts).total_seconds() // 60)
        except Exception:
            age_min = None
    snap["_fromHistory"] = True
    snap["_snapshotAt"] = str(ts) if ts is not None else None
    snap["_ageMinutes"] = age_min
    return snap


def run_after_audit(new_picks: int = 0, audit_date: str = None) -> Optional[Dict]:
    """Ciclo do cron: calcula o snapshot CUMULATIVO e persiste.

    #202 — `audit_date` e ETIQUETA, nao recorte.

    O cron chama isto com date_filter, que ora e rotulo ("today"/"yesterday"),
    ora e data ISO ("2026-08-30", quando roda para um dia especifico). Depois do
    #197 a data ISO passou a FILTRAR de verdade, e o batch das 05:01 gravou em
    brier_history um snapshot de 170 picks (so os do dia) onde as linhas
    anteriores tinham 5.951 (acumulado). O #199 entao passou a servir esse
    snapshot diario como se fosse o global, e o ReliabilityCard exibiu 170.

    brier_history sempre foi cumulativo — quem fatia por dia e o daily_series.
    Aqui o snapshot volta a ser calculado sem recorte; a etiqueta e so gravada.
    """
    snap = calculate_snapshot()          # cumulativo, sempre
    if snap:
        if audit_date:
            snap["audit_date"] = str(audit_date)   # etiqueta preservada
        persist_snapshot(snap, new_picks)
    return snap


def get_history(limit: int = 30) -> List[Dict]:
    """Fetch recent snapshots for trend display."""
    try:
        conn = _conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT id,timestamp,total_picks,brier_model,brier_implied,model_beats_house,"
            "delta,accuracy,by_league,by_market,by_band,by_classification,by_league_market,"
            "new_picks,audit_date "
            "FROM brier_history ORDER BY timestamp DESC LIMIT %s",
            (limit,),
        )
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        cur.close()
        conn.close()
        for r in rows:
            if r.get("timestamp"):
                r["timestamp"] = str(r["timestamp"])
        return rows
    except Exception as e:
        logger.error(f"[Brier] history failed: {e}")
        return []
