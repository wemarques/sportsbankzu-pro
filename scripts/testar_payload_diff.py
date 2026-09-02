#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""#222 - prova empirica antes/depois sobre o payload MONTADO.

    python scripts/testar_payload_diff.py --antes antes.json --depois depois.json
    python scripts/testar_payload_diff.py --antes antes.json --depois depois.json --json

Como obter os dois arquivos (o `$B` e a Function URL):

    curl -s "$B/fixtures?leagues=championship&date=today" > antes.json
    # ... aplica o patch, deploy ...
    curl -s "$B/fixtures?leagues=championship&date=today" > depois.json

Por que este script existe
--------------------------
O #221 anunciava, no proprio commit, que o EARLY_SEASON_FALLBACK sairia das
ligas maduras. Medido, o payload saia IDENTICO com e sem a contagem: faltava um
quarto elo (o record nao publicava `league_stats`). A leitura do codigo estava
certa e a conclusao estava errada.

Sai com codigo 1 quando os dois payloads sao equivalentes nos campos que
decidem publicacao. Pela regra #222 isso REPROVA a entrega: patch que promete
efeito e nao move nada tem elo quebrado na esteira de dados, ainda que cada
funcao esteja perfeita isoladamente.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Campos que decidem se um pick e publicado e com que forca. Diferenca em
# qualquer um deles e efeito real; o resto e ruido de serializacao.
CAMPOS = ("status", "classification", "reason_codes", "prob_max",
          "odd_minima", "ev", "raw_probability", "iso_probability",
          "calibrated_probability", "banda", "corner_veto")


def _jogos(caminho):
    with open(caminho, encoding="utf-8") as f:
        d = json.load(f)
    return d.get("matches", d) if isinstance(d, dict) else d


def _indexar(jogos):
    """(jogo, mercado) -> dict dos campos que importam."""
    out = {}
    for j in jogos:
        rot = (f"{(j.get('homeTeam') or {}).get('name','?')} x "
               f"{(j.get('awayTeam') or {}).get('name','?')}")
        for m in (j.get("mercados") or []):
            out[(rot, str(m.get("mercado", "")))] = {c: m.get(c) for c in CAMPOS}
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--antes", required=True)
    ap.add_argument("--depois", required=True)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    A, D = _indexar(_jogos(a.antes)), _indexar(_jogos(a.depois))
    so_antes = sorted(set(A) - set(D))
    so_depois = sorted(set(D) - set(A))
    mudaram = []
    for k in sorted(set(A) & set(D)):
        dif = {c: [A[k][c], D[k][c]] for c in CAMPOS if A[k][c] != D[k][c]}
        if dif:
            mudaram.append({"jogo": k[0], "mercado": k[1], "campos": dif})

    resumo = {
        "picks_antes": len(A), "picks_depois": len(D),
        "sumiram": len(so_antes), "surgiram": len(so_depois),
        "mudaram": len(mudaram),
    }
    if a.json:
        print(json.dumps({"resumo": resumo, "mudaram": mudaram,
                          "sumiram": [list(k) for k in so_antes],
                          "surgiram": [list(k) for k in so_depois]},
                         ensure_ascii=False, indent=2, default=str))
    else:
        print(f"{resumo['picks_antes']} picks antes, {resumo['picks_depois']} depois")
        for k in so_antes:
            print(f"  SUMIU    {k[0]} | {k[1]}")
        for k in so_depois:
            print(f"  SURGIU   {k[0]} | {k[1]}")
        for m in mudaram:
            print(f"  MUDOU    {m['jogo']} | {m['mercado']}")
            for c, (x, y) in m["campos"].items():
                print(f"             {c}: {x} -> {y}")

    if not (so_antes or so_depois or mudaram):
        print("\nPAYLOAD IDENTICO nos campos que decidem publicacao.")
        print("Pela regra #222 a entrega esta REPROVADA: se o patch prometia")
        print("efeito, ha elo quebrado na esteira de dados. Rastreie os 4 elos")
        print("(origem, montagem, consumo, impacto) antes de concluir.")
        return 1
    print(f"\nefeito medido: {resumo['mudaram']} pick(s) alterados, "
          f"{resumo['sumiram']} sumiram, {resumo['surgiram']} surgiram.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
