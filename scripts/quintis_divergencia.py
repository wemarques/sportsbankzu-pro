#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""#238-M1 - a divergencia |modelo - mercado| e um rotulo bom ou ruim?

"VALOR DETECTADO" nasce quando o modelo se afasta do mercado na direcao
favoravel a odd. Se a divergencia fosse informacao, os picks mais
divergentes teriam Brier MELHOR que os demais. Se for ruido do modelo, tera
Brier PIOR e ficara mais abaixo do piso da taxa-base. Esta medicao ordena os
picks em quintis de |prob_modelo - prob_mercado| e mede, por quintil, o Brier
do modelo, o do mercado e o piso deixa-um-jogo-fora (#235), com bootstrap
por JOGO (picks do mesmo jogo sao correlacionados).

    python scripts/quintis_divergencia.py --arquivo todas_mercado.json

Entrada: o JSON de `backfill_historico.py --prob-de mercado` (`prob` =
mercado, `prob_modelo` = modelo, `outcome`, `match_id`, `league_id`,
`market`). Tambem aceita um arquivo com `prob_mercado` no lugar de `prob`.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import random
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Sequence

_RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_RAIZ))
_spec = importlib.util.spec_from_file_location("cmp", _RAIZ / "scripts" / "comparar_com_mercado.py")
C = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(C)


def _normalizar(picks: List[Dict]) -> List[Dict]:
    out = []
    for p in picks:
        pm = p.get("prob_modelo")
        pk = p.get("prob") if "prob_modelo" in p else p.get("prob_mercado")
        if pm is None or pk is None or p.get("outcome") is None:
            continue
        out.append({"match_id": str(p.get("match_id")), "league_id": str(p.get("league_id", "?")),
                    "market": str(p.get("market", "?")), "prob_modelo": float(pm), "prob": float(pk),
                    "outcome": int(p["outcome"]), "div": float(pm) - float(pk)})
    return out


def _quintis(picks: List[Dict], k: int = 5) -> List[List[Dict]]:
    ordenado = sorted(picks, key=lambda p: abs(p["div"]))
    n = len(ordenado)
    return [ordenado[i * n // k:(i + 1) * n // k] for i in range(k)]


def _stats(grupo: Sequence[Dict]) -> Dict[str, float]:
    bm, bk = C._brier(grupo, "prob_modelo"), C._brier(grupo, "prob")
    piso = C._piso_logo(grupo)
    return {"n": len(grupo), "jogos": len({p["match_id"] for p in grupo}),
            "brier_modelo": bm, "brier_mercado": bk, "piso_logo": piso,
            "excesso_modelo": bm - piso, "excesso_mercado": bk - piso,
            "div_media": sum(abs(p["div"]) for p in grupo) / len(grupo)}


def _bootstrap_por_jogo(grupo: Sequence[Dict], reamostras: int, semente: int = 7):
    """IC95 de (Brier_modelo - piso) e de (Brier_modelo - Brier_mercado), reamostrando JOGOS."""
    por_jogo: Dict[str, List[Dict]] = defaultdict(list)
    for p in grupo:
        por_jogo[p["match_id"]].append(p)
    jogos = list(por_jogo)
    rng = random.Random(semente)
    exc, dif = [], []
    for _ in range(reamostras):
        amostra: List[Dict] = []
        for _j in range(len(jogos)):
            amostra.extend(por_jogo[jogos[rng.randrange(len(jogos))]])
        bm, bk, piso = C._brier(amostra, "prob_modelo"), C._brier(amostra, "prob"), C._piso_logo(amostra)
        exc.append(bm - piso); dif.append(bm - bk)
    def ic(v):
        v = sorted(v); return v[int(0.025 * len(v))], v[int(0.975 * len(v)) - 1]
    return ic(exc), ic(dif)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arquivo", required=True)
    ap.add_argument("--reamostras", type=int, default=300)
    ap.add_argument("--quintis", type=int, default=5)
    args = ap.parse_args()
    with open(args.arquivo, encoding="utf-8") as f:
        bruto = json.load(f)
    picks = _normalizar(bruto if isinstance(bruto, list) else bruto.get("picks", []))
    if not picks:
        print("sem picks com prob_modelo, prob(_mercado) e outcome", file=sys.stderr)
        return 1
    print(f"{len(picks)} picks em {len({p['match_id'] for p in picks})} jogos; "
          f"quintis de |modelo - mercado|; piso = deixa-um-jogo-fora; IC por jogo, {args.reamostras} reamostras\n")
    print(f"{'quintil':<8}{'|div| media':>12}{'n':>7}{'jogos':>7}{'Brier mod':>11}{'Brier mkt':>11}{'piso':>8}"
          f"{'mod-piso':>10}{'IC95':>20}{'mod-mkt':>9}{'IC95':>20}")
    for i, g in enumerate(_quintis(picks, args.quintis), 1):
        s = _stats(g)
        (elo, ehi), (dlo, dhi) = _bootstrap_por_jogo(g, args.reamostras, semente=i)
        print(f"Q{i:<7}{s['div_media']:>12.4f}{s['n']:>7}{s['jogos']:>7}{s['brier_modelo']:>11.4f}"
              f"{s['brier_mercado']:>11.4f}{s['piso_logo']:>8.4f}{s['excesso_modelo']:>+10.4f}"
              f"  [{elo:+.4f}, {ehi:+.4f}]{s['brier_modelo'] - s['brier_mercado']:>+9.4f}"
              f"  [{dlo:+.4f}, {dhi:+.4f}]")
    # o lado que vira "VALOR DETECTADO": modelo ACIMA do mercado no quintil mais divergente
    topo = _quintis(picks, args.quintis)[-1]
    acima = [p for p in topo if p["div"] > 0]
    abaixo = [p for p in topo if p["div"] < 0]
    print("\nquintil mais divergente, por sinal (modelo acima do mercado = onde o EV do modelo aparece):")
    for nome, g in (("modelo > mercado", acima), ("modelo < mercado", abaixo)):
        if len(g) < 30:
            print(f"  {nome:<18} n={len(g)} (sem veredito)"); continue
        s = _stats(g)
        (elo, ehi), _ = _bootstrap_por_jogo(g, args.reamostras, semente=99)
        taxa = sum(p["outcome"] for p in g) / len(g)
        pm = sum(p["prob_modelo"] for p in g) / len(g); pk = sum(p["prob"] for p in g) / len(g)
        print(f"  {nome:<18} n={s['n']:<6} jogos={s['jogos']:<5} prob media modelo {pm:.3f} | mercado {pk:.3f} | "
              f"taxa real {taxa:.3f} | Brier mod {s['brier_modelo']:.4f} mkt {s['brier_mercado']:.4f} | "
              f"mod-piso {s['excesso_modelo']:+.4f} [{elo:+.4f}, {ehi:+.4f}]")
    print("\nleitura: se Q5 tem o maior 'mod-piso' com IC acima de 0 e os demais nao, a divergencia e ruido do modelo — "
          "'VALOR DETECTADO' e o rotulo do pior quintil, medido.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
