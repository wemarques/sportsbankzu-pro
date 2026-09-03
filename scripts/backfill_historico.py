# -*- coding: utf-8 -*-
"""#227 - gera os picks historicos que o `medir_inclinacao.py` (#220) consome.

    python scripts/backfill_historico.py --liga championship --saida picks.json
    python scripts/backfill_historico.py --sintetico 400 --saida picks.json
    python scripts/medir_inclinacao.py --arquivo picks.json

Escanteios estao no escopo desde o #226-b, que mediu contagem e odds em 100%
nas 605 finalizadas da championship. Antes disso ficaram de fora por uma rota
que consultava a linha crua usando um nome criado pelo `data_mapper`.
"""
from __future__ import annotations

import argparse
import json
import logging
import pathlib
import sys
from typing import Any, Dict, List

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
_RAIZ = pathlib.Path(__file__).resolve().parents[1]

try:
    from dotenv import load_dotenv
    for _nome in (".env", "backend/.env"):
        if (_RAIZ / _nome).exists():
            load_dotenv(_RAIZ / _nome, override=False)
except ImportError:
    pass


def partidas_sinteticas(n: int, com_sinal: bool = True,
                        semente: int = 227) -> List[Dict[str, Any]]:
    """Liga gerada para provar o caminho — e para provar o INSTRUMENTO.

    `com_sinal=True`: gols saem de forcas de ataque/defesa por time, entao as
    medias moveis que o backfill reconstroi **carregam sinal** e a inclinacao
    tem de dar perto de 1. E o controle POSITIVO, sem o qual "SEM RESOLUCAO em
    tudo" seria indistinguivel de um backfill quebrado.

    `com_sinal=False`: gols sorteados de um Poisson fixo, sem efeito de time.
    Controle NEGATIVO — a inclinacao tem de encostar em zero.
    """
    import importlib.util
    import random

    caminho = _RAIZ / "scripts" / "retreinar_escanteios.py"
    spec = importlib.util.spec_from_file_location("_gerador", caminho)
    gerador = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gerador)

    rng = random.Random(semente)
    partidas = gerador.liga_sintetica(n, semente=semente)

    times = sorted({p["homeTeam"] for p in partidas} | {p["awayTeam"] for p in partidas})
    ataque = {t: rng.uniform(0.55, 2.10) for t in times}
    defesa = {t: rng.uniform(0.55, 2.10) for t in times}

    for p in partidas:
        if com_sinal:
            p["homeGoalCount"] = gerador._poisson(
                rng, ataque[p["homeTeam"]] * defesa[p["awayTeam"]] * 1.15)
            p["awayGoalCount"] = gerador._poisson(
                rng, ataque[p["awayTeam"]] * defesa[p["homeTeam"]] * 0.95)
        p["totalCornerCount"] = p["team_a_corners"] + p["team_b_corners"]
        p["team_a_yellow_cards"] = gerador._poisson(rng, 2.2)
        p["team_b_yellow_cards"] = gerador._poisson(rng, 2.4)
        _precificar(p, ataque, defesa, com_sinal, rng)
    return partidas


def _precificar(p: Dict[str, Any], ataque, defesa, com_sinal: bool, rng) -> None:
    """Odds coerentes com a probabilidade que GEROU o jogo, mais margem.

    Com `com_sinal`, o preco sai do lambda verdadeiro — entao o caminho
    `--prob-de mercado` tem controle positivo proprio: a casa sabe, e a
    inclinacao dela tem de dar perto de 1. Sem sinal, o preco e ruido, como o
    resto.
    """
    import math

    def _par(chave_over: str, chave_under: str, prob: float, margem: float = 1.06) -> None:
        prob = min(max(prob, 0.02), 0.98)
        p[chave_over] = round(1.0 / (prob * margem), 2)
        p[chave_under] = round(1.0 / ((1.0 - prob) * margem), 2)

    if com_sinal:
        lam_c = ataque[p["homeTeam"]] * defesa[p["awayTeam"]] * 1.15
        lam_f = ataque[p["awayTeam"]] * defesa[p["homeTeam"]] * 0.95
        lam = lam_c + lam_f
        def _over(linha: int) -> float:
            acum = sum(math.exp(-lam) * lam ** k / math.factorial(k)
                       for k in range(linha + 1))
            return 1.0 - acum
        _par("odds_ft_over25", "odds_ft_under25", _over(2))
        _par("odds_ft_over35", "odds_ft_under35", _over(3))
        _par("odds_btts_yes", "odds_btts_no",
             (1 - math.exp(-lam_c)) * (1 - math.exp(-lam_f)))
    else:
        _par("odds_ft_over25", "odds_ft_under25", rng.uniform(0.35, 0.65))
        _par("odds_ft_over35", "odds_ft_under35", rng.uniform(0.20, 0.45))
        _par("odds_btts_yes", "odds_btts_no", rng.uniform(0.35, 0.65))

    for linha in ("75", "85", "95", "105", "115"):
        _par(f"odds_corners_over_{linha}", f"odds_corners_under_{linha}",
             rng.uniform(0.25, 0.75))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--liga", default="championship")
    ap.add_argument("--sintetico", type=int, metavar="N",
                    help="gera a liga em vez de chamar a API")
    ap.add_argument("--sem-sinal", action="store_true",
                    help="controle negativo: gols sem efeito de time")
    ap.add_argument("--temporadas", type=int, default=2)
    ap.add_argument("--min-jogos", type=int, default=5)
    ap.add_argument("--familias", help="ex: gols,escanteios (padrao: todas)")
    ap.add_argument("--so-com-odd", action="store_true",
                    help="#227-b: mantem so os picks que tem preco. E o que "
                         "torna modelo e mercado comparaveis — medir o modelo "
                         "em 7860 e o mercado em 4184 compara conjuntos "
                         "diferentes, nao previsores.")
    ap.add_argument("--prob-de", choices=["modelo", "mercado"], default="modelo",
                    help="#227-a: 'mercado' usa a probabilidade da casa (de-vig "
                         "quando ha par over/under, 1/odd quando so ha a perna "
                         "over) no lugar da do modelo. E a referencia: se o "
                         "mercado tambem der inclinacao zero nos mesmos picks, o "
                         "problema nao esta no modelo.")
    ap.add_argument("--saida", default="picks_historicos.json")
    ap.add_argument("--verboso", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO if args.verboso else logging.WARNING,
                        format="%(levelname)s %(name)s: %(message)s")

    from backend.services.backfill_historico import reconstruir

    if args.sintetico:
        linhas = partidas_sinteticas(args.sintetico, com_sinal=not args.sem_sinal)
        liga = "sintetica"
    else:
        from backend.config.leagues_config import LEAGUES_CONFIG
        from backend.cron_handler import coletar_partidas_escanteios

        ligas = [l for l in LEAGUES_CONFIG if l.get("id") == args.liga]
        if not ligas:
            print(f"liga desconhecida: {args.liga}", file=sys.stderr)
            return 2
        dados = coletar_partidas_escanteios(ligas=ligas, n_temporadas=args.temporadas)
        linhas = dados.get(args.liga) or []
        liga = args.liga
        if not linhas:
            print("coleta vazia — rode com --verboso para ver o motivo", file=sys.stderr)
            return 1

    familias = [f.strip() for f in args.familias.split(",")] if args.familias else None
    saida = reconstruir(linhas, liga, min_jogos=args.min_jogos, familias=familias)

    picks = saida["picks"]
    if args.so_com_odd:
        picks = [p for p in picks if p["prob_mercado"] is not None]
        saida["resumo"]["picks_apos_so_com_odd"] = len(picks)
    if args.prob_de == "mercado":
        # Troca a fonte da probabilidade e descarta o que nao tem preco: medir
        # o mercado onde nao ha mercado nao mede nada.
        picks = [{**p, "prob": p["prob_mercado"], "prob_modelo": p["prob"]}
                 for p in picks if p["prob_mercado"] is not None]
        saida["resumo"]["picks_com_prob_de_mercado"] = len(picks)

    with open(args.saida, "w", encoding="utf-8") as f:
        json.dump(picks, f, ensure_ascii=False)

    print(json.dumps(saida["resumo"], indent=2, ensure_ascii=False))
    print(f"\nfonte da probabilidade: {args.prob_de}")
    print(f"{len(picks)} picks -> {args.saida}")
    print(f"proximo passo: python scripts/medir_inclinacao.py --arquivo {args.saida}")
    return 0 if picks else 1


if __name__ == "__main__":
    raise SystemExit(main())
