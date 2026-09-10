# -*- coding: utf-8 -*-
"""A regra de contagem do ledger.

O `prediction_ledger` e append-only e guarda VARIAS geracoes por jogo. Toronto
x Nashville (09/09) tem duas, 03:09 e 11:09, com numeros diferentes. Treinar
em todas conta o mesmo jogo mais de uma vez e da mais peso aos jogos que foram
recomputados mais vezes.
"""
import datetime as dt

import pytest

from backend.modeling.calibragem.repositorio import (
    classificar_familia, escolher_ultima_geracao, Pick,
)


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


@pytest.mark.parametrize("market,selection,esperado", [
    ("Corners", "Corners Over 7.5", "Corners"),
    ("Cards", "Over 2.5", "Cards"),
    ("Over/Under", "Over 2.5", "Over/Under"),
    ("Double Chance", "DC 1X", "Double Chance"),
    ("BTTS", "BTTS Yes", "BTTS"),
    ("1X2", "Draw", "1X2"),
])
def test_classificar_familia_com_as_formas_reais_do_ledger(market, selection, esperado):
    """`market` e `selection` como o ledger de fato guarda -- ingles, nao os
    rotulos de exibicao em pt-BR. Achado da rodada 1: escanteios e cartoes
    caiam em Over/Under porque so o rotulo concatenado era testado.
    """
    assert classificar_familia(market, selection) == esperado


@pytest.mark.parametrize("market,selection", [
    ("Corners", "Corners Over 7.5"),
    ("Corners", "Corners Under 9.5"),
])
def test_escanteios_nunca_classifica_como_over_under(market, selection):
    """Trava de regressao do achado critico da rodada 1: um pick de
    escanteios, na forma real do ledger, nunca pode virar Over/Under -- isso
    envenenaria a curva de gols com outra distribuicao.
    """
    assert classificar_familia(market, selection) == "Corners"


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


# ─── o custo de reconstruir `p_legado` (#248, Task 13) ──────────────────────
#
# `carregar_amostra` passou a chamar o legado uma vez por pick, e o ramo de
# Over/Under do legado consulta `lambda_calculator.get_lambda_corrections`,
# que vai ao banco. Sao 5.484 picks em producao. A invariante que este teste
# trava: UMA consulta por LIGA, nunca uma por PICK.


class _CursorDaAmostra:
    """Devolve as linhas do SELECT de `carregar_amostra`, na ordem da query."""

    def __init__(self, linhas):
        self._linhas = linhas

    def execute(self, sql, params=None):
        pass

    def fetchall(self):
        return self._linhas

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _ConexaoDaAmostra:
    def __init__(self, linhas):
        self._linhas = linhas

    def cursor(self):
        return _CursorDaAmostra(self._linhas)

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _linhas_do_ledger(n_por_liga, ligas):
    """Picks de Over/Under -- o unico ramo do legado que consulta o banco."""
    saida = []
    for liga in ligas:
        for i in range(n_por_liga):
            saida.append((f"m-{liga}-{i}", liga, "Over/Under", "Over 2.5",
                          0.55 + (i % 7) / 100.0, None, None, 1.90, 1))
    return saida


def test_uma_consulta_de_correcoes_por_liga_nao_por_pick(monkeypatch,
                                                         _cache_limpo):
    """`_cache_limpo` yielda a `get_lambda_corrections` ORIGINAL.

    Contar chamadas a ela mediria o numero errado: o cache por liga do
    #231-a mora DENTRO dela. O que vai ao banco e
    `backend.audit.get_active_corrections`, e e ele que este teste conta.
    """
    import backend.audit as audit
    import backend.modeling.calibragem.repositorio as repo
    from backend.modeling import lambda_calculator as LC

    # O TTL e fixado: a invariante vale sob a configuracao PADRAO. Com
    # `LAMBDA_CORRECTIONS_TTL_S=0` o operador desligou o cache do #231-a de
    # proposito e o numero volta a ser um por pick -- verificado por mutacao
    # (o teste cai com 200 consultas), e registrado na docstring de
    # `repositorio._aquecer_correcoes_por_liga`.
    monkeypatch.setenv("LAMBDA_CORRECTIONS_TTL_S", "300")

    ligas = ["premier-league", "la-liga", "serie-a", "bundesliga"]
    linhas = _linhas_do_ledger(50, ligas)          # 200 picks, 4 ligas
    monkeypatch.setattr(repo, "_conn", lambda: _ConexaoDaAmostra(linhas))

    chamadas = []
    monkeypatch.setattr(LC, "get_lambda_corrections", _cache_limpo)
    monkeypatch.setattr(audit, "get_active_corrections",
                        lambda league: chamadas.append(league) or {})
    LC.limpar_cache_correcoes()

    picks = repo.carregar_amostra()
    assert len(picks) == 200
    assert all(p.p_legado is not None for p in picks)
    assert len(chamadas) == len(ligas), (
        f"{len(chamadas)} consultas de correcoes para {len(ligas)} ligas e "
        f"{len(picks)} picks -- a invariante 'uma por liga' quebrou")
    assert set(chamadas) == set(ligas)


def test_o_p_legado_reconstruido_fica_abaixo_do_raw(monkeypatch):
    """Prova que o legado foi de fato aplicado, e nao que `p_legado` copiou
    `p_raw`: a versao 0 deflaciona."""
    import backend.modeling.calibragem.repositorio as repo

    linhas = _linhas_do_ledger(5, ["premier-league"])
    monkeypatch.setattr(repo, "_conn", lambda: _ConexaoDaAmostra(linhas))
    for p in repo.carregar_amostra():
        assert p.p_legado < p.p_raw, (p.p_raw, p.p_legado)
