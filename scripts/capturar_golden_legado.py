#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Captura pares entrada->saida de `_calibrar_com_detalhe` ANTES do refactor.

A fixture existe para provar IGUALDADE EXATA depois que a pilha de deflacao
for movida para `calibragem/legado.py`. Rodar UMA vez, com o codigo ainda
intacto, e versionar o JSON. Rodar de novo depois do refactor invalida o
proprio controle.
"""
import json
import os
import pathlib
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

from backend.services.ev_classification import _calibrar_com_detalhe  # noqa: E402

MERCADOS = [
    "Over 0.5", "Over 1.5", "Over 2.5", "Over 3.5", "Over 4.5",
    "Under 1.5", "Under 2.5", "Under 3.5", "Under 4.5",
    "BTTS",
    "Escanteios Over 4.5", "Escanteios Over 7.5", "Escanteios Over 11.5",
    "Escanteios Under 8.5", "Escanteios Under 12.5",
    "Cartoes Over 1.5", "Cartoes Over 2.5", "Cartoes Under 4.5",
    "1X2 Home", "1X2 Draw", "DC 1X", "DC X2", "DC 12",
]
LIGAS = ["", "premier-league", "mls", "primeira-liga", "serie-a", "liga-inexistente"]
REGIMES = ["NORMAL", "HIPER-OFENSIVA"]
PROBS = [round(0.02 + i * 0.02, 2) for i in range(49)]   # 0.02 .. 0.98


def main() -> int:
    casos = []
    for market in MERCADOS:
        for league_id in LIGAS:
            for regime in REGIMES:
                for raw in PROBS:
                    d = _calibrar_com_detalhe(raw, market, league_id, regime)
                    casos.append({
                        "raw": raw, "market": market, "league_id": league_id,
                        "regime": regime,
                        "final": d.final, "iso": d.iso, "banda": d.banda,
                        "tipo_banda": d.tipo_banda, "per_league": d.per_league,
                        "ou_defl": d.ou_defl, "under25_extra": d.under25_extra,
                    })
    destino = pathlib.Path(RAIZ) / "tests/calibragem/fixtures/golden_legado.json"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(casos, ensure_ascii=False), encoding="utf-8")
    print(f"{len(casos)} casos gravados em {destino}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
