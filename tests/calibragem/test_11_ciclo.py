# -*- coding: utf-8 -*-
"""O ciclo e o fallback. Banco fora do ar NAO pode virar identidade."""
import pytest

from backend.modeling.calibragem import ciclo


def test_banco_fora_cai_no_legado_e_marca(monkeypatch):
    ciclo.limpar_cache()  # isola do cache que outro teste deste modulo deixou
    def explode():
        raise RuntimeError("connection refused")
    monkeypatch.setattr(ciclo.repositorio, "carregar_parametros_para_curva", explode)
    monkeypatch.setattr(ciclo, "_SNAPSHOT", {})
    parametros, procedencia = ciclo.parametros_vigentes()
    assert parametros == {}
    assert procedencia == "legado"


def test_banco_fora_usa_o_snapshot_quando_existe(monkeypatch):
    ciclo.limpar_cache()  # isola do cache que outro teste deste modulo deixou
    def explode():
        raise RuntimeError("connection refused")
    monkeypatch.setattr(ciclo.repositorio, "carregar_parametros_para_curva", explode)
    monkeypatch.setattr(ciclo, "_SNAPSHOT", {("Corners", ""): (3, 0.4, 1.0)})
    parametros, procedencia = ciclo.parametros_vigentes()
    assert parametros == {("Corners", ""): (3, 0.4, 1.0)}
    assert procedencia == "snapshot"


def test_nunca_devolve_identidade_por_falha(monkeypatch):
    """a=0,b=1 publicaria o raw de uma vez por causa de rede."""
    ciclo.limpar_cache()  # isola do cache que outro teste deste modulo deixou
    def explode():
        raise RuntimeError("timeout")
    monkeypatch.setattr(ciclo.repositorio, "carregar_parametros_para_curva", explode)
    monkeypatch.setattr(ciclo, "_SNAPSHOT", {})
    parametros, _ = ciclo.parametros_vigentes()
    assert all(v[1:] != (0.0, 1.0) for v in parametros.values())


def test_cache_evita_segunda_ida_ao_banco(monkeypatch):
    chamadas = {"n": 0}

    def conta():
        chamadas["n"] += 1
        return {("Corners", ""): (2, 0.3, 1.0)}
    monkeypatch.setattr(ciclo.repositorio, "carregar_parametros_para_curva", conta)
    ciclo.limpar_cache()
    ciclo.parametros_vigentes()
    ciclo.parametros_vigentes()
    assert chamadas["n"] == 1
