# -*- coding: utf-8 -*-
"""#235 - piso deixa-um-jogo-fora e teto de calibracao no caminho do ledger.

Na primeira leitura com 196 jogos o comparador imprimiu modelo E mercado 7%
"abaixo de nao saber nada": o piso in-sample usa o desfecho do proprio pick
e, com ~10 picks correlacionados por jogo, fica otimista demais. O piso
honesto e o que se forma com os OUTROS jogos. E o criterio (b) do gate #230
(teto de calibracao da publicada) nao era impresso no ledger porque vivia
dentro da secao MOTOR x INGENUO, que o ledger nunca tem.
"""
import importlib.util
import io
import contextlib
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "comparar_com_mercado", Path(__file__).resolve().parents[1] / "scripts" / "comparar_com_mercado.py")
C = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(C)


def _pick(jogo, y, p=0.5):
    return {"match_id": str(jogo), "league_id": "L", "market": "Over 2.5",
            "outcome": y, "prob": p, "prob_modelo": p}


def test_um_pick_por_jogo_logo_e_a_taxa_dos_outros_jogos():
    picks = [_pick(i, i % 2) for i in range(40)]           # 20 uns, 20 zeros
    assert C._piso(picks) == pytest.approx(0.25)
    # outcome 1 -> taxa dos outros = 19/39; outcome 0 -> 20/39; erro igual nos dois
    assert C._piso_logo(picks) == pytest.approx((1 - 19 / 39) ** 2, abs=1e-9)
    assert C._piso_logo(picks) > C._piso(picks)             # honesto e maior


def test_dez_picks_correlacionados_por_jogo_ampliam_o_otimismo_in_sample():
    picks = [_pick(j, j % 2) for j in range(20) for _ in range(10)]
    assert C._piso(picks) == pytest.approx(0.25)            # in-sample nao ve a correlacao
    assert C._piso_logo(picks) == pytest.approx((10 / 19) ** 2, abs=1e-9)   # 0.277: ve


def test_celula_com_um_jogo_so_cai_para_a_taxa_in_sample():
    picks = [_pick(1, 1), _pick(1, 0)]
    assert C._piso_logo(picks) == pytest.approx(C._piso(picks))


def test_decomposicao_e_teto_imprimem_sem_prob_ingenuo():
    picks = [_pick(i, i % 2, 0.55 if i % 2 else 0.45) for i in range(60)]
    saida = io.StringIO()
    with contextlib.redirect_stdout(saida):
        C._decomposicao_e_teto(picks, C._piso(picks), (("publicada", "prob_modelo"), ("mercado", "prob")))
    texto = saida.getvalue()
    assert "teto apos calibracao linear otima" in texto and "publicada" in texto
    assert "mercado" in texto and "ha algo a extrair" in texto   # sinal > 0 por construcao
