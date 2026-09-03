# -*- coding: utf-8 -*-
"""#226 - roda o retrain de escanteios de verdade e mostra o que saiu.

O job semanal (`cron(0 5 ? * MON *)`) nunca treinou nada: importava dois nomes
que nao existem e caia no `except ImportError`. Este script executa o mesmo
caminho, agora corrigido, e imprime o resumo — inclusive quantas partidas
trouxeram **contagem de escanteios**, que e o insumo que o #225-a mediu em
0/48 na championship.

    python scripts/retreinar_escanteios.py --sintetico 200   # offline, sem API
    python scripts/retreinar_escanteios.py --liga championship
    python scripts/retreinar_escanteios.py --todas
"""
from __future__ import annotations

import argparse
import json
import logging
import pathlib
import random
import sys
from typing import Any, Dict, List

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
_RAIZ = pathlib.Path(__file__).resolve().parents[1]


def _carregar_env() -> None:
    """Le `.env` e `backend/.env` se `python-dotenv` estiver instalado.

    Sem isto o script exige `FOOTYSTATS_API_KEY` exportada na sessao, e o erro
    que aparece e "coleta vazia" — que parece problema de API, nao de chave.
    Nao sobrescreve variavel ja definida no ambiente.
    """
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    for nome in (".env", "backend/.env"):
        caminho = _RAIZ / nome
        if caminho.exists():
            load_dotenv(caminho, override=False)


_carregar_env()


def liga_sintetica(n: int = 200, semente: int = 226) -> List[Dict[str, Any]]:
    """Partidas no formato de linha da FootyStats, com escanteios reais.

    Serve para provar que o pipeline TREINA — nao para estimar nada sobre
    futebol. Os times tem forcas diferentes para que as features rolantes
    tenham sinal; a contagem sai de um Poisson por time.
    """
    rng = random.Random(semente)
    times = [f"Time {chr(65 + i)}" for i in range(20)]
    forca = {t: rng.uniform(3.8, 6.4) for t in times}
    partidas = []
    for i in range(n):
        casa, fora = rng.sample(times, 2)
        c_casa = _poisson(rng, forca[casa] * 1.10)   # mando: +10%
        c_fora = _poisson(rng, forca[fora] * 0.92)
        partidas.append({
            "id": i + 1,
            "date_unix": 1_700_000_000 + i * 86_400,
            "status": "complete",
            "homeTeam": casa, "awayTeam": fora,
            "team_a_corners": c_casa, "team_b_corners": c_fora,
            "team_a_shots": _poisson(rng, 12.5), "team_b_shots": _poisson(rng, 11.0),
            "team_a_shotsOnTarget": _poisson(rng, 4.5),
            "team_b_shotsOnTarget": _poisson(rng, 3.9),
            "team_a_possession": round(rng.uniform(40, 60), 1),
            "team_b_possession": round(rng.uniform(40, 60), 1),
            "team_a_xg": round(rng.uniform(0.5, 2.6), 2),
            "team_b_xg": round(rng.uniform(0.4, 2.2), 2),
            "homeGoalCount": _poisson(rng, 1.5), "awayGoalCount": _poisson(rng, 1.2),
        })
    return partidas


def _poisson(rng: random.Random, lam: float) -> int:
    """Knuth — sem depender de numpy so para gerar fixture."""
    import math
    limite, k, p = math.exp(-lam), 0, 1.0
    while True:
        k += 1
        p *= rng.random()
        if p <= limite:
            return k - 1


def _resumir(resumo: Dict[str, Any]) -> Dict[str, Any]:
    campeao = (resumo.get("champion_selection") or {}).get("dominant_champion")
    return {
        "league_id": resumo.get("league_id"),
        "status": resumo.get("status"),
        "n_matches": resumo.get("n_matches"),
        "n_valid_corners": resumo.get("n_valid_corners"),
        "n_feature_samples": resumo.get("n_feature_samples"),
        "n_features": resumo.get("n_features"),
        "training_results": resumo.get("training_results"),
        "champion": campeao,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sintetico", type=int, metavar="N",
                    help="treina numa liga gerada, sem chamar a API")
    ap.add_argument("--liga", help="league_id de LEAGUES_CONFIG")
    ap.add_argument("--todas", action="store_true")
    ap.add_argument("--temporadas", type=int, default=2)
    ap.add_argument("--verboso", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verboso else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    from backend.modeling.corners.retrain import retrain_league, retrain_all_leagues

    if args.sintetico:
        partidas = liga_sintetica(args.sintetico)
        resumo = retrain_league(partidas, "sintetica",
                                {"average_corners_per_match": 10.2}, force_shadow=True)
        print(json.dumps(_resumir(resumo), indent=2, ensure_ascii=False))
        return 0 if resumo.get("status") == "completed" else 1

    from backend.cron_handler import coletar_partidas_escanteios
    from backend.config.leagues_config import LEAGUES_CONFIG

    ligas = LEAGUES_CONFIG
    if args.liga:
        ligas = [l for l in LEAGUES_CONFIG if l.get("id") == args.liga]
        if not ligas:
            print(f"liga desconhecida: {args.liga}", file=sys.stderr)
            return 2
    elif not args.todas:
        print("escolha --sintetico N, --liga <id> ou --todas", file=sys.stderr)
        return 2

    import os
    chave = os.getenv("FOOTYSTATS_API_KEY")
    if not chave:
        print("FOOTYSTATS_API_KEY nao esta no ambiente nem em .env / backend/.env — "
              "a coleta vai voltar vazia", file=sys.stderr)
    elif args.verboso:
        print(f"chave presente ({len(chave)} chars)", file=sys.stderr)

    dados = coletar_partidas_escanteios(ligas=ligas, n_temporadas=args.temporadas)
    if not dados:
        print("coleta vazia — chave invalida, liga sem season_id, ou API sem resposta "
              "(rode com --verboso para ver o motivo por liga)", file=sys.stderr)
        return 1

    resultados = retrain_all_leagues(dados, force_shadow=True)
    print(json.dumps([_resumir(r) for r in resultados], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
