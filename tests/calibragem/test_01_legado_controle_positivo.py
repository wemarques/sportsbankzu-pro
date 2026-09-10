# -*- coding: utf-8 -*-
"""Teste 1 da spec — a versao 0 reproduz a producao com IGUALDADE EXATA.

A fixture foi capturada do codigo anterior ao refactor. Se este teste passar,
mover a pilha de deflacao para `legado.py` nao mudou nenhum numero publicado.
Se falhar, a costura esta errada e nada mais no pacote importa.
"""
import json
import pathlib

import pytest

from backend.modeling.calibragem.legado import calibrar_legado

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "golden_legado.json"


@pytest.fixture(autouse=True)
def _sem_calibracao_por_liga(monkeypatch):
    """#242 (mesmo defeito, outro teste) - `calibrar_legado` chama
    `_get_league_deflation`, que consulta `get_lambda_corrections` no banco
    via o cache TTL de 300s do #231-a. A fixture dourada foi capturada com o
    cache frio (consulta falhou -> caiu no padrao 0.90 documentado). Num
    proceso onde um teste anterior ja aqueceu o cache com a RDS real, 18 das
    22 ligas devolvem `lambda_multiplier: 1.0` e o resultado diverge da
    fixture por ORDEM de execucao, nao por defeito de logica. Aqui fixamos
    o estado (cache limpo + get_lambda_corrections mockado para {}) para
    reproduzir exatamente as condicoes em que a fixture foi capturada.
    """
    from backend.modeling import lambda_calculator as LC
    LC.limpar_cache_correcoes()
    monkeypatch.setattr(LC, "get_lambda_corrections", lambda league: {})
    yield
    LC.limpar_cache_correcoes()


@pytest.fixture(scope="module")
def casos():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_fixture_cobre_os_quatro_caminhos(casos):
    tipos = {c["tipo_banda"] for c in casos}
    assert {"meia-btts", "meia", "inteira"} <= tipos, tipos
    # #161: o extra de Under 2.5 (#113) so dispara quando
    # `_DEFAULT_OU_DEFLATION >= 1.0`. Em producao a constante e 0.90
    # (backend/modeling/poisson_matrix.py) e nao e afetada por market/
    # league_id/regime, entao o caminho e estruturalmente morto sob os
    # defaults atuais -- confirmado empiricamente ao capturar a fixture
    # (nenhum dos 13524 casos liga o extra). A fixture ainda cobre o
    # mercado-gatilho ("Under 2.5"); o que ela nao pode fazer e forcar o
    # extra a disparar sem mudar a constante, o que seria capturar um
    # cenario que a producao intacta nao produz.
    assert any(c["market"] == "Under 2.5" for c in casos), "mercado Under 2.5 nao coberto"
    assert not any(c["under25_extra"] for c in casos), (
        "extra de Under 2.5 disparou na captura -- _DEFAULT_OU_DEFLATION "
        "mudou de 0.90? revisar a suposicao de caminho morto do #161 antes "
        "de tratar isto como regressao."
    )


def test_legado_reproduz_a_producao_exatamente(casos):
    divergentes = []
    for c in casos:
        d = calibrar_legado(c["raw"], c["market"], c["league_id"], c["regime"])
        if d.final != c["final"]:
            divergentes.append((c["market"], c["league_id"], c["raw"],
                                c["final"], d.final))
    assert not divergentes, f"{len(divergentes)} divergencias: {divergentes[:5]}"


def test_legado_preserva_o_detalhe_inteiro(casos):
    for c in casos[:500]:
        d = calibrar_legado(c["raw"], c["market"], c["league_id"], c["regime"])
        assert d.iso == c["iso"]
        assert d.banda == c["banda"]
        assert d.tipo_banda == c["tipo_banda"]
        assert d.per_league == c["per_league"]
        assert d.ou_defl == c["ou_defl"]
        assert d.under25_extra == c["under25_extra"]
