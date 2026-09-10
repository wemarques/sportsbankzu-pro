# -*- coding: utf-8 -*-
"""A semente do backfill entra como amostra, e o decaimento e a propria conta."""
import json

import pytest

from backend.modeling.calibragem import (
    MIN_PICKS_PARA_VALIDAR_SEMENTE, N_PRIOR_NAO_VALIDADA, TETO_N_PRIOR,
)
from backend.modeling.calibragem.estimador import (
    aplicar_semente, medir_concordancia, n_prior_da_concordancia,
)
from backend.modeling.calibragem.repositorio import Pick, carregar_semente_backfill


def _p(mid, raw):
    return Pick(mid, "Over/Under", "liga", raw, 1)


def test_concordancia_perfeita():
    a = [_p("m1", 0.60), _p("m2", 0.40)]
    b = [_p("m1", 0.60), _p("m2", 0.40)]
    c, n = medir_concordancia(a, b)
    assert n == 2 and c == pytest.approx(1.0)


def test_concordancia_conta_dentro_de_dois_pontos():
    a = [_p("m1", 0.60), _p("m2", 0.40)]
    b = [_p("m1", 0.615), _p("m2", 0.50)]      # o primeiro entra, o segundo nao
    c, n = medir_concordancia(a, b)
    assert n == 2 and c == pytest.approx(0.5)


def test_n_prior_escala_com_a_concordancia():
    assert n_prior_da_concordancia(1.0, 500)[0] == TETO_N_PRIOR
    assert n_prior_da_concordancia(0.5, 500)[0] == TETO_N_PRIOR // 2
    assert n_prior_da_concordancia(0.0, 500)[0] == 0


def test_sobreposicao_pequena_cai_no_valor_nao_validado():
    n, status = n_prior_da_concordancia(1.0, MIN_PICKS_PARA_VALIDAR_SEMENTE - 1)
    assert n == N_PRIOR_NAO_VALIDADA
    assert status == "semente_nao_validada"


def test_semente_domina_quando_o_ledger_e_pequeno():
    ledger = {("Over/Under", ""): {"a": 0.0, "b": 1.0, "n_jogos": 10, "origem": "familia", "k_fixo": True}}
    semente = {("Over/Under", ""): {"a": 1.0, "b": 1.0, "n_jogos": 8403, "origem": "semente", "k_fixo": True}}
    r = aplicar_semente(ledger, semente, n_prior=150)
    assert r[("Over/Under", "")]["a"] == pytest.approx(150 / 160, abs=0.001)


def test_ledger_domina_quando_cresce():
    """O decaimento e a propria aritmetica — nao ha segundo mecanismo."""
    ledger = {("Over/Under", ""): {"a": 0.0, "b": 1.0, "n_jogos": 3000, "origem": "familia", "k_fixo": False}}
    semente = {("Over/Under", ""): {"a": 1.0, "b": 1.0, "n_jogos": 8403, "origem": "semente", "k_fixo": True}}
    r = aplicar_semente(ledger, semente, n_prior=150)
    assert r[("Over/Under", "")]["a"] < 0.06


def test_celula_so_na_semente_sobrevive():
    ledger = {}
    semente = {("Cards", ""): {"a": 0.9, "b": 1.0, "n_jogos": 400, "origem": "semente", "k_fixo": True}}
    r = aplicar_semente(ledger, semente, n_prior=150)
    assert r[("Cards", "")]["a"] == pytest.approx(0.9)
    assert r[("Cards", "")]["origem"] == "semente"


# --- carregar_semente_backfill: arquivo ausente / ilegivel (nao esta no brief) ---

def test_semente_arquivo_ausente_devolve_lista_vazia(tmp_path, caplog):
    caminho = str(tmp_path / "nao_existe.json")
    with caplog.at_level("INFO", logger="sportsbankzu.calibragem.repositorio"):
        saida = carregar_semente_backfill(caminho)
    assert saida == []


def test_semente_arquivo_ilegivel_devolve_lista_vazia(tmp_path, caplog):
    caminho = tmp_path / "corrompido.json"
    caminho.write_text("{nao e json valido", encoding="utf-8")
    with caplog.at_level("WARNING", logger="sportsbankzu.calibragem.repositorio"):
        saida = carregar_semente_backfill(str(caminho))
    assert saida == []


def test_semente_prioriza_market_isolado_sobre_token_da_selection():
    """`classificar_familia` resolve por `market` isolado ANTES de tentar o
    rotulo concatenado (repositorio.py, docstring de `classificar_familia`).
    Isso importa quando `selection` carrega um token de outra familia que
    aparece mais cedo na lista ordenada de `curva._FAMILIAS` do que o token
    do proprio `market` -- nesse caso, resolver direto no rotulo concatenado
    (como o Step 3/4 do brief propunha) classifica errado; resolver por
    `market` primeiro classifica certo. Caso verificado empiricamente: com
    market='Cards' e selection='Corners Adjustment 7.5', chamar
    `familia_do_mercado` no rotulo concatenado devolve 'Corners' (errado --
    'corners' vem antes de 'cards' em `_FAMILIAS`); `classificar_familia`
    devolve 'Cards' (certo), porque resolve 'Cards' pelo `market` isolado
    antes de sequer olhar para `selection`."""
    from backend.modeling.calibragem.curva import familia_do_mercado
    market, selection = "Cards", "Corners Adjustment 7.5"

    rotulo_concatenado = f"{market} {selection}".strip()
    assert familia_do_mercado(rotulo_concatenado) == "Corners"      # o jeito errado

    from backend.modeling.calibragem.repositorio import classificar_familia
    assert classificar_familia(market, selection) == "Cards"         # o jeito certo


def test_concordancia_nao_mistura_linhas_diferentes_do_mesmo_jogo_e_familia():
    """Regressao da rodada de correcao 1: `Pick` nao carregava `selecao`, e
    `medir_concordancia` indexava so por (match_id, familia, liga). Duas
    linhas distintas do mesmo jogo e familia (aqui, 'Corners Over 1.5' e
    'Corners Over 2.5') caiam no mesmo balde; o pareamento escolhia a
    `p_raw` mais proxima em vez de comparar a mesma aposta, e como o
    candidato casado nao era consumido, o mesmo valor do ledger podia casar
    com mais de uma linha da semente -- so subindo a concordancia, nunca
    descendo.

    Cenario: a linha 'Over 1.5' da semente (0.56) NAO concorda com a sua
    propria linha no ledger (0.90, |diff|=0.34) -- discorda de verdade. A
    linha 'Over 2.5' da semente (0.55) concorda com a sua (0.55). O
    resultado certo e concordancia 0.5 (1 de 2), nao 1.0: com a indexacao
    antiga (sem `selecao`), a linha 'Over 1.5' da semente casava por engano
    com o valor 0.55 do ledger (que e de 'Over 2.5', |diff|=0.01) porque o
    balde nao distinguia as duas linhas e o candidato nao era consumido --
    inflando a concordancia para 1.0 nas duas.
    """
    ledger = [
        Pick("m1", "Corners", "liga", 0.90, 1, None, "Corners Over 1.5"),
        Pick("m1", "Corners", "liga", 0.55, 1, None, "Corners Over 2.5"),
    ]
    semente = [
        Pick("m1", "Corners", "liga", 0.56, 1, None, "Corners Over 1.5"),
        Pick("m1", "Corners", "liga", 0.55, 1, None, "Corners Over 2.5"),
    ]
    c, n = medir_concordancia(semente, ledger)
    assert n == 2
    assert c == pytest.approx(0.5)


def test_pick_aceita_cinco_argumentos_posicionais_odd_e_selecao_saem_default():
    """Ancora de compatibilidade para o setimo campo: tarefas anteriores
    constroem `Pick` com cinco ou seis argumentos posicionais e nao podem
    quebrar quando `selecao` e acrescentado no final. Mesmo espirito do
    teste ja existente para `odd` em test_03_repositorio_amostra.py."""
    p = Pick("m1", "Over/Under", "premier-league", 0.61, 1)
    assert p.match_id == "m1"
    assert p.familia == "Over/Under"
    assert p.liga == "premier-league"
    assert p.p_raw == 0.61
    assert p.y == 1
    assert p.odd is None
    assert p.selecao == ""


def test_semente_classifica_formas_reais_do_ledger(tmp_path):
    """Sanidade fim a fim com as formas reais de `market`/`selection` do
    ledger (mesmas usadas em test_03_repositorio_amostra.py) -- confirma que
    `carregar_semente_backfill` produz a familia certa para os casos comuns,
    ainda que estes nao distingam `classificar_familia` de
    `familia_do_mercado` direto (ver teste acima para o caso que distingue)."""
    caminho = tmp_path / "semente.json"
    dados = [
        {"match_id": "m1", "market": "Corners", "selection": "Corners Over 7.5",
         "league_id": "39", "raw_prob": 0.55, "outcome": 1},
        {"match_id": "m2", "market": "Cards", "selection": "Under 2.5",
         "league_id": "39", "raw_prob": 0.40, "outcome": 0},
    ]
    caminho.write_text(json.dumps(dados), encoding="utf-8")
    saida = carregar_semente_backfill(str(caminho))
    familias = {p.familia for p in saida}
    assert familias == {"Corners", "Cards"}
    selecoes = {p.selecao for p in saida}
    assert selecoes == {"Corners Over 7.5", "Under 2.5"}
