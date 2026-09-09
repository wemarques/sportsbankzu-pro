# -*- coding: utf-8 -*-
"""A regra de contagem do ledger.

O `prediction_ledger` e append-only e guarda VARIAS geracoes por jogo. Toronto
x Nashville (09/09) tem duas, 03:09 e 11:09, com numeros diferentes. Treinar
em todas conta o mesmo jogo mais de uma vez e da mais peso aos jogos que foram
recomputados mais vezes.
"""
import datetime as dt

import pytest

from backend.modeling.calibragem.repositorio import escolher_ultima_geracao, Pick


def _linha(match_id, market, selection, publicado, kickoff, raw):
    return {
        "match_id": match_id, "market": market, "selection": selection,
        "published_at": publicado, "kickoff_utc": kickoff, "raw_prob": raw,
    }


KICK = dt.datetime(2026, 9, 9, 20, 30, tzinfo=dt.timezone.utc)


def test_mantem_a_ultima_geracao_antes_do_kickoff():
    linhas = [
        _linha("m1", "Over/Under", "Over 2.5", dt.datetime(2026, 9, 9, 3, 9, tzinfo=dt.timezone.utc), KICK, 0.61),
        _linha("m1", "Over/Under", "Over 2.5", dt.datetime(2026, 9, 9, 11, 9, tzinfo=dt.timezone.utc), KICK, 0.58),
    ]
    saida = escolher_ultima_geracao(linhas)
    assert len(saida) == 1
    assert saida[0]["raw_prob"] == 0.58


def test_descarta_geracao_posterior_ao_kickoff():
    """Recomputacao pos-jogo nao e prognostico — e o defeito do #200."""
    linhas = [
        _linha("m1", "Over/Under", "Over 2.5", dt.datetime(2026, 9, 9, 11, 9, tzinfo=dt.timezone.utc), KICK, 0.58),
        _linha("m1", "Over/Under", "Over 2.5", dt.datetime(2026, 9, 9, 23, 0, tzinfo=dt.timezone.utc), KICK, 0.99),
    ]
    saida = escolher_ultima_geracao(linhas)
    assert len(saida) == 1
    assert saida[0]["raw_prob"] == 0.58


def test_selecoes_diferentes_do_mesmo_jogo_sobrevivem_as_duas():
    linhas = [
        _linha("m1", "Over/Under", "Over 2.5", dt.datetime(2026, 9, 9, 3, 9, tzinfo=dt.timezone.utc), KICK, 0.61),
        _linha("m1", "Over/Under", "Under 3.5", dt.datetime(2026, 9, 9, 3, 9, tzinfo=dt.timezone.utc), KICK, 0.64),
    ]
    assert len(escolher_ultima_geracao(linhas)) == 2


def test_sem_kickoff_mantem_a_ultima_publicacao():
    """kickoff_utc e nulo em parte do historico; a regra degrada, nao quebra."""
    linhas = [
        _linha("m1", "BTTS", "BTTS Yes", dt.datetime(2026, 9, 9, 3, 9, tzinfo=dt.timezone.utc), None, 0.55),
        _linha("m1", "BTTS", "BTTS Yes", dt.datetime(2026, 9, 9, 11, 9, tzinfo=dt.timezone.utc), None, 0.57),
    ]
    saida = escolher_ultima_geracao(linhas)
    assert len(saida) == 1 and saida[0]["raw_prob"] == 0.57


def test_todas_as_geracoes_posteriores_ao_kickoff_nao_deixa_nada():
    linhas = [
        _linha("m1", "BTTS", "BTTS Yes", dt.datetime(2026, 9, 9, 23, 0, tzinfo=dt.timezone.utc), KICK, 0.99),
    ]
    assert escolher_ultima_geracao(linhas) == []


def test_nao_ha_caminho_de_codigo_para_audit_results():
    """Teste 9 da spec, aplicado cedo — a regra #244 vale desde o primeiro modulo."""
    import pathlib
    fonte = pathlib.Path("backend/modeling/calibragem/repositorio.py").read_text(encoding="utf-8")
    assert "audit_results" not in fonte


def test_pick_aceita_cinco_argumentos_posicionais_e_odd_sai_none():
    """Ancora a compatibilidade: tarefas anteriores constroem `Pick` com cinco
    argumentos posicionais (match_id, familia, liga, p_raw, y) e nao podem
    quebrar quando o sexto campo `odd` e adicionado.
    """
    p = Pick("m1", "Over/Under", "premier-league", 0.61, 1)
    assert p.match_id == "m1"
    assert p.familia == "Over/Under"
    assert p.liga == "premier-league"
    assert p.p_raw == 0.61
    assert p.y == 1
    assert p.odd is None
