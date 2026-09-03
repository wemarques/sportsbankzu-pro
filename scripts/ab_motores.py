# -*- coding: utf-8 -*-
"""#225-c - prova empirica do codemod: executa os dois motores, nao le o codigo.

O protocolo SDD (proibicao 14) exige diff de execucao real. Este script pega a
versao ANTES direto do git, carrega os dois modulos lado a lado e roda o MESMO
payload nos dois, com chaves PRESENTES valendo `None` — a forma exata que mata
`.get(k, alternativa)`.

    python scripts/ab_motores.py                 # contra 61804b7 (pre-#225-c)
    python scripts/ab_motores.py --ref <commit>
"""
from __future__ import annotations

import argparse
import importlib.util
import logging
import pathlib
import random
import subprocess
import sys
import tempfile
from typing import Any, Callable, Dict, Optional, Tuple

RAIZ = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

ANTES_PADRAO = "61804b7"  # #225-b, ultimo commit antes do codemod

# Valores plausiveis para toda chave que os dois motores leem.
BASE_CASA = {
    "cardsAVG_home": 2.4, "homeCardsPerMatch": 2.4, "cardsAVG_overall": 2.3,
    "homeCardsAgainstPerMatch": 2.1, "cardsAgainstAVG_home": 2.1,
    "cards_against_per_match": 2.0,
    "cornersAVG_home": 5.6, "homeCornersPerMatch": 5.6, "cornersAVG_overall": 5.4,
    "homeCornersAgainstPerMatch": 4.8, "cornersAgainstAVG_home": 4.8,
    "matchesPlayed_home": 12, "matchesPlayed_overall": 24,
    "corners_recorded_matches_num": 24, "cards_recorded_matches_num": 24,
}
BASE_FORA = {
    "cardsAVG_away": 2.6, "awayCardsPerMatch": 2.6, "cardsAVG_overall": 2.5,
    "awayCardsAgainstPerMatch": 2.2, "cardsAgainstAVG_away": 2.2,
    "cards_against_per_match": 2.1,
    "cornersAVG_away": 4.9, "awayCornersPerMatch": 4.9, "cornersAVG_overall": 5.1,
    "awayCornersAgainstPerMatch": 5.5, "cornersAgainstAVG_away": 5.5,
    "matchesPlayed_away": 12, "matchesPlayed_overall": 24,
    "corners_recorded_matches_num": 24, "cards_recorded_matches_num": 24,
}
BASE_LIGA = {
    "cardsAvg": 4.6, "leagueAvgCards": 4.6, "avg_cards_per_match": 4.6,
    "cornersAvg": 10.2, "leagueAvgCorners": 10.2, "avg_corners_per_match": 10.2,
    "cardsVariance": 1.8, "matches_completed": 240,
}


def _versao_antiga(ref: str, caminho: str, destino: pathlib.Path, apelido: str):
    fonte = subprocess.run(
        ["git", "show", f"{ref}:{caminho}"], cwd=RAIZ,
        capture_output=True, text=True, check=True,
    ).stdout
    # Nome .py real: spec_from_file_location nao infere loader de outra extensao.
    arquivo = destino / f"{apelido}.py"
    arquivo.write_text(fonte, encoding="utf-8")
    return _carregar(apelido, arquivo)


def _carregar(nome: str, caminho: pathlib.Path):
    spec = importlib.util.spec_from_file_location(nome, caminho)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"sem loader para {caminho}")
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[nome] = modulo
    spec.loader.exec_module(modulo)
    return modulo


def _anular(base: Dict[str, Any], rng: random.Random, p: float) -> Dict[str, Any]:
    """Chave PRESENTE valendo None — nao ausente. E a diferenca que importa."""
    return {k: (None if rng.random() < p else v) for k, v in base.items()}


def _comparar(nome: str, antes: Callable, depois: Callable,
              n: int, p: float, semente: int) -> Optional[Tuple]:
    rng = random.Random(semente)
    difs = 0
    exemplo = None
    for _ in range(n):
        casa = _anular(BASE_CASA, rng, p)
        fora = _anular(BASE_FORA, rng, p)
        liga = _anular(BASE_LIGA, rng, p)
        try:
            a = antes(casa, fora, liga)
        except Exception as erro:            # erro tambem e saida observavel
            a = ("ERRO", type(erro).__name__)
        try:
            d = depois(casa, fora, liga)
        except Exception as erro:
            d = ("ERRO", type(erro).__name__)
        if a != d:
            difs += 1
            if exemplo is None:
                exemplo = (casa, fora, liga, a, d)
    print(f"{nome}: {n} payloads | saida diferente em {difs} ({difs * 100 // n}%)")
    return exemplo


def _escalares(d: Dict[str, Any]) -> Dict[str, Any]:
    return {k: (round(v, 4) if isinstance(v, float) else v)
            for k, v in d.items() if isinstance(v, (int, float, str))}


def _records_de_referencia(cards_antes, cards_depois, corners_antes, corners_depois) -> None:
    """Os tres records REAIS do contrato do #223, sem injecao nenhuma.

    Sao pobres de proposito (uma partida sintetica, `teams=None`): servem para
    dizer se o codemod mexe no payload que da para reproduzir offline. Nao
    provam ausencia de efeito no feed de producao — o #225-b encontrou a forma
    divergente (`corners_recorded_matches_num` nula com `matchesPlayed_*`
    preenchida) num payload real da championship, e esta fixture nao tem
    historico de time para exercita-la.
    """
    from backend.config import contrato_record

    print("\nrecords de referencia (#223), sem injecao:")
    for i, registro in enumerate(contrato_record._cenarios()):
        casa = fora = registro.get("stats") or {}
        liga = registro.get("league_stats") or {}
        a_cards = cards_antes.predict_cards(casa, fora, "championship", liga)
        d_cards = cards_depois.predict_cards(casa, fora, "championship", liga)
        a_corn = corners_antes.estimate_corners_lambda(casa, fora, liga)
        d_corn = corners_depois.estimate_corners_lambda(casa, fora, liga)
        igual = (_escalares(a_cards) == _escalares(d_cards)
                 and round(a_corn, 4) == round(d_corn, 4))
        print(f"  cenario {i}: cards {a_cards.get('projected_total_cards')} -> "
              f"{d_cards.get('projected_total_cards')} | corners "
              f"{round(a_corn, 3)} -> {round(d_corn, 3)}  "
              f"{'IDENTICO' if igual else 'DIFERE'}")


def _comparar_features_escanteios(antes, depois, n: int, prob: float, semente: int) -> None:
    """#226 - o codemod em `corners/features.py`, medido nas duas entradas reais.

    Aqui o payload nao e inventado: sai do record do #223. A primeira leitura usa
    os records como estao; a segunda forca `None` em parte das chaves — a forma
    presente-e-nula que o #225-b encontrou no feed da championship.
    """
    from backend.config import contrato_record

    registros = list(contrato_record._cenarios())
    print("\ncorners/features (build_v2_match_features + build_match_corner_features):")

    iguais = 0
    for i, registro in enumerate(registros):
        st = registro.get("stats") or {}
        ls = registro.get("league_stats") or {}
        mesmo = (antes.build_v2_match_features(st, st, ls)
                 == depois.build_v2_match_features(st, st, ls)
                 and antes.build_match_corner_features(st, st, ls)
                 == depois.build_match_corner_features(st, st, ls))
        iguais += mesmo
        print(f"  record {i} sem injecao: {'IDENTICO' if mesmo else 'DIFERE'}")

    rng = random.Random(semente)
    base = registros[0].get("stats") or {}
    liga = registros[0].get("league_stats") or {}
    difs = 0
    exemplo = None
    for _ in range(n):
        st = {k: (None if rng.random() < prob else v) for k, v in base.items()}
        a = antes.build_v2_match_features(st, st, liga)
        d = depois.build_v2_match_features(st, st, liga)
        if a != d:
            difs += 1
            if exemplo is None:
                exemplo = sorted(k for k in set(a) | set(d) if a.get(k) != d.get(k))
    print(f"  {n} payloads com {int(prob * 100)}% presentes-e-nulas: "
          f"diferente em {difs} ({difs * 100 // n}%)")
    if exemplo:
        print(f"  features que mudam: {', '.join(exemplo[:6])}"
              f"{' ...' if len(exemplo) > 6 else ''}")


def _comparar_predictor(antes_features, n_ignorado=None) -> None:
    """#226 - o numero PUBLICADO, nao so a feature.

    O record de referencia sozinho nao serve: sem `matchesPlayed_*` o tier trava
    em INSUFFICIENT e `predict_corners` retorna antes de olhar as features. A
    forma usada aqui e a que o #225-b MEDIU na championship — contagem de
    escanteios nula com a temporada jogada — nao uma invencao conveniente.
    """
    from backend.config import contrato_record
    from backend.modeling.corners import predictor

    registro = next(iter(contrato_record._cenarios()))
    st = dict(registro.get("stats") or {})
    st.update({"matchesPlayed_home": 24, "matchesPlayed_away": 24,
               "matchesPlayed_overall": 24})
    ls = registro.get("league_stats") or {}

    def rodar():
        r = predictor.predict_corners(st, st, "championship", ls)
        proj = r.get("projection") or {}
        return {
            "expected_total_corners": r.get("expected_total_corners"),
            "tier": (r.get("data_quality") or {}).get("data_quality_tier"),
            "pressure_index": round(proj.get("pressure_index") or 0, 4),
        }

    guardados = (predictor.build_v2_match_features,
                 predictor.compute_matchup_pressure_index,
                 predictor.build_match_corner_features)
    predictor.build_v2_match_features = antes_features.build_v2_match_features
    predictor.compute_matchup_pressure_index = antes_features.compute_matchup_pressure_index
    predictor.build_match_corner_features = antes_features.build_match_corner_features
    try:
        a = rodar()
    finally:
        (predictor.build_v2_match_features,
         predictor.compute_matchup_pressure_index,
         predictor.build_match_corner_features) = guardados
    d = rodar()

    print("\npredict_corners (record + temporada jogada, forma medida no #225-b):")
    for chave in a:
        marca = "" if a[chave] == d[chave] else "   <<< MUDOU"
        print(f"  {chave:24s} {a[chave]}  ->  {d[chave]}{marca}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", default=ANTES_PADRAO)
    ap.add_argument("--n", type=int, default=400)
    ap.add_argument("--nulos", type=float, default=0.40)
    ap.add_argument("--semente", type=int, default=225)
    args = ap.parse_args()

    logging.disable(logging.CRITICAL)
    with tempfile.TemporaryDirectory() as tmp:
        destino = pathlib.Path(tmp)
        cards_antes = _versao_antiga(args.ref, "backend/modeling/cards_engine.py",
                                     destino, "cards_antes")
        corners_antes = _versao_antiga(args.ref, "backend/modeling/corners_engine.py",
                                       destino, "corners_antes")
        from backend.modeling import cards_engine as cards_depois
        from backend.modeling import corners_engine as corners_depois

        print(f"ANTES = {args.ref} | DEPOIS = arvore atual | "
              f"{int(args.nulos * 100)}% das chaves presentes-e-nulas\n")

        exemplo = _comparar(
            "cards_engine",
            lambda c, f, l: _escalares(cards_antes.predict_cards(c, f, "championship", l)),
            lambda c, f, l: _escalares(cards_depois.predict_cards(c, f, "championship", l)),
            args.n, args.nulos, args.semente,
        )
        _comparar(
            "corners_engine",
            lambda c, f, l: round(corners_antes.estimate_corners_lambda(c, f, l), 4),
            lambda c, f, l: round(corners_depois.estimate_corners_lambda(c, f, l), 4),
            args.n, args.nulos, args.semente,
        )
        _records_de_referencia(cards_antes, cards_depois,
                               corners_antes, corners_depois)

        feats_antes = _versao_antiga(args.ref, "backend/modeling/corners/features.py",
                                     destino, "feats_antes")
        from backend.modeling.corners import features as feats_depois
        _comparar_features_escanteios(feats_antes, feats_depois,
                                      args.n, args.nulos, args.semente)
        _comparar_predictor(feats_antes)
    logging.disable(logging.NOTSET)

    if exemplo:
        casa, fora, liga, antes, depois = exemplo
        nulas = sorted({k for d in (casa, fora, liga)
                        for k, v in d.items() if v is None})
        print("\nexemplo concreto (cards):")
        print("  presentes-e-nulas:", ", ".join(nulas[:8]))
        for chave in sorted(set(antes) | set(depois)):
            if antes.get(chave) != depois.get(chave):
                print(f"    {chave:26s} {antes.get(chave)}  ->  {depois.get(chave)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
