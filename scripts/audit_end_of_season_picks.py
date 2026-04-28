"""
audit_end_of_season_picks.py — Etapa 0 (medir antes de prescrever).

Le audit_results dos ultimos N dias e segmenta picks por fase relativa
da temporada DE CADA LIGA (early/mid/late, baseado em percentil de data).

NAO usa standings historicas — porque elas nao existem persistidas.
Usa proxy temporal: assume que os ultimos 20% dos jogos disputados de
uma liga concentram a maioria dos cenarios "fim de temporada"
(times rebaixados, titulo decidido, meio da tabela com nada em jogo).

Output: relatorio markdown com Brier × accuracy por liga × bucket × mercado.

Decision rule:
- Se o bucket "late" mostrar Brier >= 15% pior que "early/mid" em >= 3 ligas
  com N suficiente (>=20 picks por bucket, REGRA #079), o sinal e real
  e justifica investimento em features de contexto de temporada.
- Caso contrario, e ruido amostral. Encerrar investigacao e registrar
  como divida tecnica de baixa prioridade.

Uso:
    DATABASE_URL=postgresql://... python scripts/audit_end_of_season_picks.py
    DATABASE_URL=postgresql://... python scripts/audit_end_of_season_picks.py --days 90
    python scripts/audit_end_of_season_picks.py --sqlite audit.db --days 60
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

MIN_N_PER_BUCKET = 20  # REGRA #079 — abaixo disso e ruido
SIGNAL_THRESHOLD_PCT = 15.0  # Brier degradacao % entre early e late
EARLY_PERCENTILE = 0.40  # primeiros 40% da janela
LATE_PERCENTILE = 0.80   # ultimos 20% da janela


def _connect(sqlite_path: Optional[str] = None):
    """Conecta a PostgreSQL via DATABASE_URL ou SQLite local."""
    if sqlite_path:
        import sqlite3
        return sqlite3.connect(sqlite_path), False
    db_url = os.environ.get("DATABASE_URL", "")
    if db_url:
        try:
            import psycopg2  # type: ignore
        except ImportError:
            print("ERRO: psycopg2 nao instalado. pip install psycopg2-binary", file=sys.stderr)
            sys.exit(1)
        return psycopg2.connect(db_url), True
    # fallback: local audit.db
    import sqlite3
    local = ROOT / "audit.db"
    if not local.exists():
        print(f"ERRO: nem DATABASE_URL configurada nem {local} existe.", file=sys.stderr)
        sys.exit(1)
    return sqlite3.connect(str(local)), False


def _fetch_picks(days: int, sqlite_path: Optional[str] = None) -> list[dict]:
    conn, is_pg = _connect(sqlite_path)
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    cur = conn.cursor()
    ph = "%s" if is_pg else "?"
    ts_col = '"timestamp"' if is_pg else "timestamp"
    query = (
        f"SELECT league, market, predicted_probs, actual_result, brier_score, "
        f"ev, context, {ts_col} "
        f"FROM audit_results "
        f"WHERE {ts_col} >= {ph} AND actual_result IS NOT NULL "
        f"AND pick_type != 'AUDIT' "
        f"ORDER BY {ts_col} ASC"
    )
    cur.execute(query, (cutoff,))
    rows = cur.fetchall()
    cur.close()
    conn.close()

    picks: list[dict] = []
    for r in rows:
        league, market, probs_raw, actual, brier, ev, ctx_raw, ts = r
        if not league or not market:
            continue
        try:
            probs = json.loads(probs_raw) if isinstance(probs_raw, str) else (probs_raw or {})
        except Exception:
            probs = {}
        prob = probs.get("prob")
        odd = probs.get("book_odd") or probs.get("odd")
        is_hit = 1 if str(actual).lower() == "hit" else 0
        # Brier se faltar — calcular manualmente
        if brier is None and prob is not None:
            try:
                brier = (float(prob) - is_hit) ** 2
            except Exception:
                brier = None
        ts_dt = ts if isinstance(ts, datetime) else datetime.fromisoformat(str(ts).replace("Z", ""))
        picks.append({
            "league": league,
            "market": market.upper().strip(),
            "prob": float(prob) if prob is not None else None,
            "odd": float(odd) if odd else None,
            "hit": is_hit,
            "brier": float(brier) if brier is not None else None,
            "ev": float(ev) if ev is not None else None,
            "ts": ts_dt,
        })
    return picks


def _bucket_by_season_phase(picks: list[dict]) -> dict[str, dict[str, list[dict]]]:
    """Agrupa picks por (liga, fase) onde fase = early|mid|late.

    Cada liga tem sua janela temporal independente. Os percentis sao
    calculados sobre a janela observada (ate `days` parametro).
    """
    by_league: dict[str, list[dict]] = defaultdict(list)
    for p in picks:
        by_league[p["league"]].append(p)

    result: dict[str, dict[str, list[dict]]] = {}
    for league, lp in by_league.items():
        lp.sort(key=lambda x: x["ts"])
        if len(lp) < MIN_N_PER_BUCKET * 3:
            # Sem N suficiente para 3 buckets — ainda registra mas com flag
            result[league] = {"early": [], "mid": [], "late": lp, "_insufficient": True}  # type: ignore[dict-item]
            continue
        ts_first = lp[0]["ts"]
        ts_last = lp[-1]["ts"]
        span = (ts_last - ts_first).total_seconds()
        if span <= 0:
            result[league] = {"early": [], "mid": [], "late": lp}
            continue
        early, mid, late = [], [], []
        for p in lp:
            frac = (p["ts"] - ts_first).total_seconds() / span
            if frac <= EARLY_PERCENTILE:
                early.append(p)
            elif frac >= LATE_PERCENTILE:
                late.append(p)
            else:
                mid.append(p)
        result[league] = {"early": early, "mid": mid, "late": late}
    return result


def _agg_metrics(picks: list[dict]) -> dict:
    if not picks:
        return {"n": 0, "brier": None, "accuracy": None, "ev_avg": None}
    n = len(picks)
    briers = [p["brier"] for p in picks if p["brier"] is not None]
    hits = sum(p["hit"] for p in picks)
    evs = [p["ev"] for p in picks if p["ev"] is not None]
    return {
        "n": n,
        "brier": round(sum(briers) / len(briers), 4) if briers else None,
        "accuracy": round(hits / n * 100, 1),
        "ev_avg": round(sum(evs) / len(evs) * 100, 2) if evs else None,
    }


def _market_breakdown(picks: list[dict]) -> dict[str, dict]:
    by_market: dict[str, list[dict]] = defaultdict(list)
    for p in picks:
        by_market[p["market"]].append(p)
    return {m: _agg_metrics(ps) for m, ps in by_market.items() if len(ps) >= 5}


def _build_report(buckets: dict[str, dict[str, list[dict]]], days: int) -> str:
    lines: list[str] = []
    lines.append(f"# Auditoria: Picks por Fase de Temporada (ultimos {days} dias)")
    lines.append("")
    lines.append(f"Gerado: {datetime.utcnow().isoformat()}Z")
    lines.append(f"MIN_N_PER_BUCKET: {MIN_N_PER_BUCKET}  |  Sinal forte se Brier(late) >= Brier(early) * {1 + SIGNAL_THRESHOLD_PCT/100:.2f}")
    lines.append("")
    lines.append("## Resumo por Liga")
    lines.append("")
    lines.append("| Liga | N early | N mid | N late | Brier early | Brier mid | Brier late | Δ late vs early | Sinal? |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|:---:|")

    flagged = []
    for league in sorted(buckets):
        b = buckets[league]
        early_m = _agg_metrics(b.get("early", []))
        mid_m = _agg_metrics(b.get("mid", []))
        late_m = _agg_metrics(b.get("late", []))

        # Sinal se: late tem N suficiente E Brier degradou >= threshold
        signal = "—"
        delta_pct = None
        if early_m["brier"] and late_m["brier"] and late_m["n"] >= MIN_N_PER_BUCKET and early_m["n"] >= MIN_N_PER_BUCKET:
            delta_pct = (late_m["brier"] - early_m["brier"]) / early_m["brier"] * 100
            if delta_pct >= SIGNAL_THRESHOLD_PCT:
                signal = "🚩 SIM"
                flagged.append((league, delta_pct, early_m, late_m))
            elif delta_pct <= -SIGNAL_THRESHOLD_PCT:
                signal = "✅ MELHOR"
            else:
                signal = "—"

        delta_str = f"{delta_pct:+.1f}%" if delta_pct is not None else "n/a"
        lines.append(
            f"| {league} | {early_m['n']} | {mid_m['n']} | {late_m['n']} | "
            f"{early_m['brier'] or 'n/a'} | {mid_m['brier'] or 'n/a'} | "
            f"{late_m['brier'] or 'n/a'} | {delta_str} | {signal} |"
        )

    lines.append("")
    lines.append("## Veredito")
    lines.append("")
    if len(flagged) >= 3:
        lines.append(f"🚩 **SINAL REAL** — {len(flagged)} ligas com Brier(late) >= {1 + SIGNAL_THRESHOLD_PCT/100:.2f}× Brier(early).")
        lines.append("")
        lines.append("Justifica investimento em features de contexto de temporada.")
        lines.append("Proximos passos:")
        lines.append("- Implementar Caminho 2 (snapshot standings) imediatamente")
        lines.append("- Aguardar 30-60 dias de coleta")
        lines.append("- Re-rodar este script com standings para isolar causa real")
    elif len(flagged) >= 1:
        lines.append(f"⚠️ **SINAL FRACO** — apenas {len(flagged)} liga(s) com sinal. Pode ser ruido.")
        lines.append("")
        lines.append("Recomendado: Caminho 2 com baixa prioridade. Reavaliar em 30 dias.")
    else:
        lines.append("✅ **SEM SINAL** — Brier nao degrada significativamente no fim da temporada.")
        lines.append("")
        lines.append("Recomendado: registrar como divida tecnica de baixa prioridade.")
        lines.append("Modelo atual ja absorve contexto via odds bookmaker (regra implicita).")

    if flagged:
        lines.append("")
        lines.append("### Ligas com sinal")
        lines.append("")
        for league, delta_pct, early_m, late_m in sorted(flagged, key=lambda x: -x[1]):
            lines.append(f"- **{league}**: Brier {early_m['brier']} → {late_m['brier']} ({delta_pct:+.1f}%), N late={late_m['n']}, accuracy {early_m['accuracy']}% → {late_m['accuracy']}%")

    # Breakdown por mercado para ligas com sinal
    if flagged:
        lines.append("")
        lines.append("## Breakdown por mercado (ligas sinalizadas)")
        for league, _, _, _ in flagged:
            lines.append("")
            lines.append(f"### {league}")
            b = buckets[league]
            for phase in ("early", "mid", "late"):
                mb = _market_breakdown(b.get(phase, []))
                if not mb:
                    continue
                lines.append(f"**{phase}** (N={sum(m['n'] for m in mb.values())})")
                for mkt, m in sorted(mb.items()):
                    lines.append(f"- {mkt}: N={m['n']}, Brier={m['brier']}, acc={m['accuracy']}%")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=60, help="Janela em dias (default: 60)")
    parser.add_argument("--sqlite", type=str, default=None, help="Caminho do SQLite (em vez de DATABASE_URL)")
    parser.add_argument("--output", type=str, default="reports/end_of_season_audit.md", help="Caminho de saida do relatorio")
    args = parser.parse_args()

    print(f"Lendo picks dos ultimos {args.days} dias...")
    picks = _fetch_picks(args.days, args.sqlite)
    print(f"Total de picks: {len(picks)}")
    if not picks:
        print("Sem dados. Verifique DATABASE_URL e janela --days.")
        sys.exit(1)

    leagues = {p["league"] for p in picks}
    print(f"Ligas distintas: {len(leagues)}")

    buckets = _bucket_by_season_phase(picks)
    report = _build_report(buckets, args.days)

    out_path = ROOT / args.output
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")
    print(f"Relatorio salvo em: {out_path}")

    # Tambem imprime resumo no stdout
    print()
    print("=" * 60)
    print(report.split("## Veredito")[1].split("##")[0] if "## Veredito" in report else "")


if __name__ == "__main__":
    main()
