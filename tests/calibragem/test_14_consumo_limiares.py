# -*- coding: utf-8 -*-
"""#249 — os limiares re-derivados deixam de ser escrita morta.

O #248 gravou `safe_ev`, `neutro_ev`, `safe_edge` e `neutro_edge` em
`calibragem_versoes` e NINGUEM os lia. Servir a curva nova com o limiar velho
publica ~1,8x mais picks de EV positivo (medido no #248: 13,8% -> 25,2%) — mais
picks, nao picks melhores. Estes testes travam o consumo: a terceira fonte de
`_get_thresholds`, aplicada por ultimo e so nos quatro campos de EV/edge.

O teste que justifica a tarefa inteira e o ultimo: VOLUME CONSTANTE ponta a
ponta, com picks reais e odds reais.
"""
import json
import logging
import pathlib

import pytest

from backend.modeling.calibragem import ciclo, curva, repositorio
from backend.modeling.calibragem.limiares import (
    CAMPOS, contar_por_classe, rederivar,
)
from backend.services import ev_classification as EV

# `(a, b)` da celula-familia no PRIMEIRO ciclo real, copiados da saida de
# `scripts/ensaio_calibragem.py` contra a RDS de producao (5.578 picks, 246
# jogos, 2026-09-10). Sao curvas ENCURTADAS pela trava de 2pp, ou seja, o que
# o painel de fato serviria no dia em que a camada for ligada — nao um par
# escolhido para o teste passar.
PRIMEIRO_CICLO = {
    "1X2":           {"a": 0.080, "b": 1.004},
    "BTTS":          {"a": 0.009, "b": 1.087},
    "Cards":         {"a": 0.065, "b": 1.038},
    "Corners":       {"a": 0.052, "b": 1.053},
    "Double Chance": {"a": 0.056, "b": 1.048},
    "Over/Under":    {"a": 0.047, "b": 1.057},
}
VERSAO_ZERO = {familia: {"a": 0.0, "b": 1.0} for familia in PRIMEIRO_CICLO}

FIXTURE = (pathlib.Path(__file__).parent / "fixtures" / "amostra_producao.json")


class _Pick:
    """Os tres campos que `limiares` de fato le."""

    def __init__(self, familia, p_legado, odd):
        self.familia, self.p_legado, self.odd = familia, p_legado, odd


def _picks_reais():
    dados = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return [_Pick(*linha) for linha in dados["picks"]]


def _limiares_de_hoje():
    """Os quatro campos, por familia, como `DEFAULT_THRESHOLDS` os tem."""
    return {familia: {campo: cfg[campo] for campo in CAMPOS}
            for familia, cfg in EV.DEFAULT_THRESHOLDS.items()}


# ─────────────────────────── dublê de banco ───────────────────────────
# `carregar_vigentes` e a UNICA consulta do serving (#249): a mesma leitura
# traz curva e limiares. O dublê e no `_conn`, e nao na funcao, para exercitar
# o SQL de verdade — inclusive a ordem das colunas, que vem de `CAMPOS`.

class _Cursor:
    def __init__(self, linhas, contador):
        self._linhas, self._contador = linhas, contador

    def execute(self, sql, params=None):
        self._contador["consultas"] += 1

    def fetchall(self):
        return self._linhas

    def fetchone(self):
        return None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _Conexao:
    def __init__(self, linhas, contador):
        self._linhas, self._contador = linhas, contador

    def cursor(self):
        return _Cursor(self._linhas, self._contador)

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _linha(familia, liga="", versao=1, a=0.05, b=1.05, limiares=None):
    limiares = limiares or {}
    return (familia, liga, versao, a, b, None) + tuple(
        limiares.get(campo) for campo in CAMPOS)


@pytest.fixture
def banco(monkeypatch):
    """Devolve `montar(linhas)` e o contador de consultas abertas."""
    contador = {"consultas": 0, "conexoes": 0}

    def montar(linhas):
        def _conn():
            contador["conexoes"] += 1
            return _Conexao(linhas, contador)
        monkeypatch.setattr(repositorio, "_conn", _conn)
        ciclo.limpar_cache()
    return montar, contador


@pytest.fixture(autouse=True)
def _fontes_1_e_2_estaveis(monkeypatch):
    """As duas fontes antigas ficam DETERMINISTICAS, e vivas.

    Nao sao desligadas: o ponto de metade destes testes e que a fonte nova
    nao pisa em `safe_prob`/`neutro_prob`, e para isso a fonte que os move
    tem de estar no caminho. `_get_dynamic_thresholds` real falaria com o
    banco de auditoria — bloqueado neste diretorio pelo conftest.
    """
    monkeypatch.setattr(EV, "_get_calibrated_threshold",
                        lambda league_id, market_category: None)
    import backend.services.market_service as MS
    monkeypatch.setattr(MS, "_get_dynamic_thresholds",
                        lambda cat: {"SAFE": 0.61, "NEUTRO": 0.49})


# ─────────────────────── vocabulario das familias ───────────────────────

def _familias_de_market_category():
    """Os rotulos que `_market_category` pode devolver, lidos por AST.

    Enumerar por AST em vez de chamar a funcao: um rotulo novo acrescentado
    la tem de aparecer aqui mesmo que ninguem se lembre de chamar o teste com
    ele. E a mesma tecnica do `test_12_guardas.py`, pelo mesmo motivo — foi
    divergencia de vocabulario que fez escanteios virarem gols e Double
    Chance ficar de fora da camada no #248.
    """
    import ast
    fonte = pathlib.Path(
        "backend/services/ev_classification.py").read_text(encoding="utf-8")
    for no in ast.walk(ast.parse(fonte)):
        if isinstance(no, ast.FunctionDef) and no.name == "_market_category":
            return {n.value.value for n in ast.walk(no)
                    if isinstance(n, ast.Return)
                    and isinstance(n.value, ast.Constant)
                    and isinstance(n.value.value, str)}
    raise AssertionError("_market_category sumiu de ev_classification.py")


def test_os_dois_vocabularios_de_familia_sao_O_MESMO_conjunto():
    """`market_category` (consumidor) x `familia_do_mercado` (produtor).

    Se divergirem, a chave gravada nunca casa com a chave consultada e o
    consumo volta a ser escrita morta — em silencio.
    """
    do_consumidor = _familias_de_market_category()
    do_produtor = {familia for _prefixo, familia in curva._FAMILIAS}
    do_default = set(EV.DEFAULT_THRESHOLDS)
    assert do_consumidor == do_produtor == do_default


# ─────────────────────────── o consumo em si ───────────────────────────

def test_sem_versao_vigente_os_limiares_sao_IDENTICOS_aos_de_hoje(banco):
    montar, _contador = banco
    montar([])
    for familia in EV.DEFAULT_THRESHOLDS:
        th = EV._get_thresholds(familia)
        for campo in CAMPOS:
            assert th[campo] == EV.DEFAULT_THRESHOLDS[familia][campo]
        # e as duas fontes antigas continuam mandando na prob
        assert th["safe_prob"] == 0.61
        assert th["neutro_prob"] == 0.49


def test_com_versao_vigente_SO_os_quatro_campos_mudam(banco):
    montar, _contador = banco
    novos = {"safe_ev": 0.1671, "neutro_ev": 0.0708,
             "safe_edge": 0.0407, "neutro_edge": 0.0187}
    montar([_linha("Corners", limiares=novos)])

    th = EV._get_thresholds("Corners")
    for campo, valor in novos.items():
        assert th[campo] == valor
    # proibicao 11: a classificacao usa prob RAW, entao a curva nao move prob
    # -- quem manda em `safe_prob`/`neutro_prob` continua sendo a fonte 2.
    assert th["safe_prob"] == 0.61
    assert th["neutro_prob"] == 0.49
    assert th["min_quality"] == EV.DEFAULT_THRESHOLDS["Corners"]["min_quality"]

    # familia sem linha vigente fica exatamente como hoje
    outra = EV._get_thresholds("BTTS")
    for campo in CAMPOS:
        assert outra[campo] == EV.DEFAULT_THRESHOLDS["BTTS"][campo]


def test_limiar_NULO_no_banco_nao_vira_zero(banco):
    """A linha de uma celula sem re-derivacao grava os quatro como NULL.

    `NULL -> 0.0` no caminho de decisao publicaria tudo (proibicao 15: o
    valor legitimo pode ser 0, entao so a AUSENCIA e detectavel).
    """
    montar, _contador = banco
    montar([_linha("Cards", limiares={"safe_ev": 0.1555, "neutro_ev": None,
                                      "safe_edge": None, "neutro_edge": None})])
    th = EV._get_thresholds("Cards")
    assert th["safe_ev"] == 0.1555
    assert th["neutro_ev"] == EV.DEFAULT_THRESHOLDS["Cards"]["neutro_ev"]
    assert th["safe_edge"] == EV.DEFAULT_THRESHOLDS["Cards"]["safe_edge"]
    assert th["neutro_edge"] == EV.DEFAULT_THRESHOLDS["Cards"]["neutro_edge"]


def test_banco_fora_do_ar_devolve_os_limiares_de_hoje_e_REGISTRA(
        monkeypatch, caplog):
    def explode():
        raise RuntimeError("connection refused")
    monkeypatch.setattr(repositorio, "carregar_vigentes", explode)
    ciclo.limpar_cache()

    with caplog.at_level(logging.ERROR, logger="sportsbankzu.calibragem.ciclo"):
        th = EV._get_thresholds("Over/Under")
    for campo in CAMPOS:
        assert th[campo] == EV.DEFAULT_THRESHOLDS["Over/Under"][campo]
    assert any("indisponiveis" in r.message or "indisponiveis" in r.getMessage()
               for r in caplog.records), caplog.text


def test_falha_dentro_do_consumidor_nao_derruba_o_pick(monkeypatch, caplog):
    """Nem uma falha inesperada (nao a de banco, que o ciclo ja trata)."""
    def explode():
        raise RuntimeError("qualquer coisa")
    monkeypatch.setattr(ciclo, "limiares_vigentes", explode)
    with caplog.at_level(logging.WARNING, logger="sportsbankzu.ev_classification"):
        th = EV._get_thresholds("BTTS")
    assert th["safe_ev"] == EV.DEFAULT_THRESHOLDS["BTTS"]["safe_ev"]
    assert "limiares da calibragem indisponiveis" in caplog.text


def test_uma_conexao_por_TTL_e_nao_por_chamada(banco):
    """`_get_thresholds` roda por mercado, por jogo, por liga."""
    montar, contador = banco
    montar([_linha("Corners", limiares={"safe_ev": 0.17})])
    for _ in range(50):
        for familia in EV.DEFAULT_THRESHOLDS:
            EV._get_thresholds(familia, league_id="mls")
    assert contador["conexoes"] == 1


def test_TTL_zero_desliga_o_cache_sem_quebrar_o_numero(banco, monkeypatch):
    montar, contador = banco
    montar([_linha("Corners", limiares={"safe_ev": 0.17})])
    monkeypatch.setenv("CALIBRAGEM_TTL_S", "0")
    assert EV._get_thresholds("Corners")["safe_ev"] == 0.17
    assert EV._get_thresholds("Corners")["safe_ev"] == 0.17
    assert contador["conexoes"] == 2


def test_celula_de_liga_supre_a_familia_sem_celula_familia(banco, caplog):
    """Familia congelada com liga vigente: a curva daquela liga ja se moveu.

    Deixar a familia sem limiar ai e publicar volume maior com o limiar
    velho — o defeito que a re-derivacao existe para impedir.
    """
    montar, _contador = banco
    montar([_linha("Corners", liga="mls", limiares={"safe_ev": 0.17})])
    with caplog.at_level(logging.WARNING,
                         logger="sportsbankzu.calibragem.repositorio"):
        assert EV._get_thresholds("Corners")["safe_ev"] == 0.17
    assert "sem celula-familia vigente" in caplog.text


def test_a_celula_familia_vence_a_de_liga(banco):
    montar, _contador = banco
    montar([_linha("Corners", liga="mls", limiares={"safe_ev": 0.99}),
            _linha("Corners", liga="", limiares={"safe_ev": 0.17})])
    assert EV._get_thresholds("Corners")["safe_ev"] == 0.17


# ───────────────── o teste que justifica a tarefa inteira ─────────────────

def test_volume_constante_PONTA_A_PONTA_com_picks_reais(banco):
    """A contagem por classe depois da camada bate com a de hoje.

    Picks reais: 3.831 linhas com odd de `prediction_ledger` x
    `ledger_outcomes` (246 jogos), capturadas da RDS de producao — `p_legado`
    calculado pelo proprio legado, odd de casa. `(a, b)` reais: o primeiro
    ciclo, encurtado pela trava de 2pp.

    Os limiares chegam pelo CAMINHO DE PRODUCAO (`_get_thresholds`), nao do
    dicionario que `rederivar` devolveu: e o consumo que esta sob teste, nao
    a re-derivacao (essa e o `test_10`).

    A folga de +-2 picks por familia esta documentada em
    `limiares._arredondar_para_baixo`: a causa dominante sao EMPATES exatos
    no quantil de corte, e `>=` leva o bloco inteiro.
    """
    picks = _picks_reais()
    assert len(picks) > 3000, "fixture de producao truncada"
    atuais = _limiares_de_hoje()

    antes = contar_por_classe(picks, VERSAO_ZERO, atuais)
    sem_rederivacao = contar_por_classe(picks, PRIMEIRO_CICLO, atuais)
    novos = rederivar(picks, VERSAO_ZERO, PRIMEIRO_CICLO, atuais)

    # os limiares sobem para o banco e voltam pelo caminho de producao
    montar, _contador = banco
    montar([_linha(familia, limiares=lim) for familia, lim in novos.items()])
    servidos = {familia: {campo: EV._get_thresholds(familia)[campo]
                          for campo in CAMPOS}
                for familia in EV.DEFAULT_THRESHOLDS}
    depois = contar_por_classe(picks, PRIMEIRO_CICLO, servidos)

    total = lambda c: sum(v["safe"] + v["neutro"] for v in c.values())  # noqa: E731

    # 1. o problema existe: sem re-derivacao o volume SOBE
    assert total(sem_rederivacao) > total(antes) + 50, (
        f"hoje={total(antes)} sem_rederivacao={total(sem_rederivacao)}")

    # 2. e o consumo o devolve ao que era, familia a familia
    for familia in antes:
        for classe in ("safe", "neutro"):
            assert abs(depois[familia][classe] - antes[familia][classe]) <= 2, (
                f"{familia}/{classe}: hoje={antes[familia][classe]} "
                f"depois={depois[familia][classe]}")
    assert total(depois) == total(antes), (
        f"hoje={total(antes)} depois={total(depois)}")


def test_com_a_camada_desligada_o_volume_e_bit_a_bit_o_de_hoje(banco):
    """Sem versao vigente, `_get_thresholds` e a funcao de antes do #249."""
    picks = _picks_reais()
    atuais = _limiares_de_hoje()
    montar, _contador = banco
    montar([])
    servidos = {familia: {campo: EV._get_thresholds(familia)[campo]
                          for campo in CAMPOS}
               for familia in EV.DEFAULT_THRESHOLDS}
    assert servidos == atuais
    assert (contar_por_classe(picks, VERSAO_ZERO, servidos)
            == contar_por_classe(picks, VERSAO_ZERO, atuais))
