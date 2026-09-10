# -*- coding: utf-8 -*-
"""Testes 1b, 7 e 9 da spec — os invariantes que atravessam modulos."""
import pathlib

import pytest

from backend.modeling.calibragem.curva import aplicar
from backend.services.ev_classification import _filter_corridor_bets

PACOTE = pathlib.Path("backend/modeling/calibragem")


def test_9_nenhum_modulo_do_pacote_le_audit_results():
    """Regra #244: a fonte de calibracao e o ledger, nunca o audit."""
    ofensores = [f.name for f in PACOTE.glob("*.py")
                 if "audit_results" in f.read_text(encoding="utf-8")]
    assert not ofensores, ofensores


def test_1b_legado_so_tem_um_chamador():
    """Enquanto houver celula na versao 0 o legado vive — com UM chamador."""
    chamadores = [f.name for f in PACOTE.glob("*.py")
                  if f.name != "legado.py"
                  and "calibrar_legado" in f.read_text(encoding="utf-8")]
    assert chamadores == ["curva.py"], chamadores


def test_1b_legado_esta_marcado_como_congelado():
    fonte = (PACOTE / "legado.py").read_text(encoding="utf-8")
    assert "PROIBIDO EDITAR" in fonte


class _M:
    """Dublê minimo de MarketOutput para o filtro de corredor."""
    def __init__(self, market_type, selection, prob):
        self.market_type = market_type
        self.selection = selection
        self.calibrated_probability = prob
        self.raw_probability = prob


def test_7_a_curva_preserva_a_decisao_do_corredor():
    """A monotonicidade protege o #246-a: a correcao nao pode reordenar linhas.

    Numeros reais de Toronto x Nashville SC (09/09/2026), geracao 03:09.
    """
    brutos = {"Over 1.5": 0.810, "Under 2.5": 0.425, "Over 2.5": 0.575,
              "Under 3.5": 0.649, "Over 3.5": 0.351, "Under 4.5": 0.816}

    def decidir(probs):
        mercados = [_M("Over/Under", sel, p) for sel, p in probs.items()]
        sobreviventes = _filter_corridor_bets(mercados)
        return sorted(m.selection for m in sobreviventes)

    sem_camada = decidir(brutos)
    for a, b in ((0.45, 1.0), (0.0, 0.7), (0.3, 1.2), (-0.2, 0.9), (0.9, 1.5)):
        com_camada = decidir({s: aplicar(p, a, b) for s, p in brutos.items()})
        assert com_camada == sem_camada, (a, b, com_camada, sem_camada)


def test_7_qualquer_b_positivo_preserva_a_ordem():
    brutos = [0.05, 0.2, 0.351, 0.5, 0.649, 0.81, 0.95]
    for a, b in ((0.0, 0.1), (2.0, 3.0), (-1.5, 0.4)):
        corrigidos = [aplicar(p, a, b) for p in brutos]
        assert corrigidos == sorted(corrigidos), (a, b)
