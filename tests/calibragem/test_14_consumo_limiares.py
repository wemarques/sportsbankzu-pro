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
    """Os campos que `limiares` de fato le.

    `match_id` entrou com o piso de amostra do #249-a: o piso conta JOGOS
    distintos, porque picks do mesmo jogo dividem o placar.
    """

    def __init__(self, match_id, familia, p_legado, odd):
        self.match_id, self.familia = match_id, familia
        self.p_legado, self.odd = p_legado, odd


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
    novos, motivos = rederivar(picks, VERSAO_ZERO, PRIMEIRO_CICLO, atuais)

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

    # 2. as familias sob o piso do #249-a NAO re-derivam. Medido nesta
    #    amostra: 1X2 sustenta 0 picks publicados e Double Chance sustenta 1,
    #    de 1 jogo — abaixo dos 20 de #079 nos dois casos.
    sob_o_piso = {f for f, m in motivos.items() if m.startswith("limiares mantidos")}
    assert sob_o_piso == {"1X2", "Double Chance"}, sorted(sob_o_piso)
    for familia in sob_o_piso:
        assert servidos[familia] == atuais[familia]

    # 3. onde a re-derivacao roda, o volume volta ao que era — familia a
    #    familia, e nao so no total (compensacao entre familias esconderia
    #    uma subindo e outra caindo).
    for familia in antes:
        if familia in sob_o_piso:
            continue
        for classe in ("safe", "neutro"):
            assert abs(depois[familia][classe] - antes[familia][classe]) <= 2, (
                f"{familia}/{classe}: hoje={antes[familia][classe]} "
                f"depois={depois[familia][classe]}")
        assert (depois[familia]["safe"] + depois[familia]["neutro"]
                == antes[familia]["safe"] + antes[familia]["neutro"]), familia

    # 4. o preco de recusar a re-derivacao e a deriva das familias sob o
    #    piso: +1 pick em Double Chance. Um limiar de UMA observacao custaria
    #    mais que isso.
    deriva = total(depois) - total(antes)
    assert 0 <= deriva <= 2, f"hoje={total(antes)} depois={total(depois)}"
    assert (total(depois) - sum(depois[f]["safe"] + depois[f]["neutro"]
                                for f in sob_o_piso)
            == total(antes) - sum(antes[f]["safe"] + antes[f]["neutro"]
                                  for f in sob_o_piso)), (
        "fora das familias sob o piso o volume tem de ser EXATO")


# ─────────────── o piso de amostra do #249-a, isolado ───────────────

def _sinteticos(n_jogos, picks_por_jogo, familia="Corners", p=0.70, odd=1.60):
    return [_Pick(f"m{j}", familia, p, odd)
            for j in range(n_jogos) for _ in range(picks_por_jogo)]


def test_piso_do_ALVO_impede_limiar_estimado_de_um_jogo():
    """O caso medido no primeiro ciclo real: Double Chance.

    O conjunto COM PRECO era enorme (666 picks, 245 jogos) — o piso do pool
    nao pega nada. O que era pequeno era o ALVO: 1 pick publicado, de 1 jogo.
    Com alvo 1 o corte e o MAXIMO da amostra, e `safe_ev` saltava de 0,0400
    para 0,2397 por causa daquele unico pick.
    """
    atuais = {"Corners": {"safe_ev": 0.08, "neutro_ev": 0.02,
                          "safe_edge": 0.06, "neutro_edge": 0.02}}
    # 200 jogos com preco, mas EV de todos abaixo do corte, menos um
    picks = _sinteticos(200, 1, p=0.55, odd=1.60)          # ev = -0.12
    picks.append(_Pick("mALVO", "Corners", 0.95, 1.60))    # ev = +0.52

    novos, motivos = rederivar(picks, {"Corners": {"a": 0.0, "b": 1.0}},
                               {"Corners": {"a": 0.5, "b": 1.0}}, atuais)
    assert novos["Corners"] == atuais["Corners"]
    assert "volume publicado apoiado em 1 jogos < 20" in motivos["Corners"]


def test_piso_do_POOL_com_preco_tambem_existe_e_diz_outra_coisa():
    """Familia com preco em pouquissimos jogos: a amostra inteira e fina.

    Nao dispara em nenhuma familia real hoje (a mais fina, cartoes, tem 122
    jogos com preco), e por isso o motivo tem de ser distinguivel do piso do
    alvo — senao a tabela nao diz qual dos dois foi.
    """
    atuais = {"Corners": {"safe_ev": 0.08, "neutro_ev": 0.02,
                          "safe_edge": 0.06, "neutro_edge": 0.02}}
    picks = _sinteticos(5, 40, p=0.95, odd=1.60)   # 200 picks, 5 jogos
    novos, motivos = rederivar(picks, {"Corners": {"a": 0.0, "b": 1.0}},
                               {"Corners": {"a": 0.5, "b": 1.0}}, atuais)
    assert novos["Corners"] == atuais["Corners"]
    assert "5 jogos com preco < 20" in motivos["Corners"]


def test_os_tres_motivos_de_nao_rederivar_sao_DISTINGUIVEIS():
    """"Sem odd", "pool fino" e "alvo fino" viram a mesma linha muda se o
    motivo nao viajar. Alguem lendo a tabela em tres meses precisa saber."""
    atuais = {"Corners": {"safe_ev": 0.08, "neutro_ev": 0.02,
                          "safe_edge": 0.06, "neutro_edge": 0.02}}
    par = ({"Corners": {"a": 0.0, "b": 1.0}}, {"Corners": {"a": 0.5, "b": 1.0}})

    sem_odd = [_Pick(f"m{i}", "Corners", 0.70, None) for i in range(60)]
    pool_fino = _sinteticos(5, 40, p=0.95)
    alvo_fino = _sinteticos(200, 1, p=0.55) + [_Pick("mA", "Corners", 0.95, 1.60)]

    motivos = [rederivar(amostra, *par, atuais)[1]["Corners"]
               for amostra in (sem_odd, pool_fino, alvo_fino)]
    assert len(set(motivos)) == 3, motivos
    assert all(m.startswith("limiares mantidos") for m in motivos)


def test_o_piso_conta_JOGOS_e_nao_PICKS():
    """40 picks de 5 jogos nao sao 40 observacoes — dividem o placar."""
    atuais = {"Corners": {"safe_ev": 0.08, "neutro_ev": 0.02,
                          "safe_edge": 0.06, "neutro_edge": 0.02}}
    par = ({"Corners": {"a": 0.0, "b": 1.0}}, {"Corners": {"a": 0.5, "b": 1.0}})

    # mesmos 200 picks; muda so a quantidade de jogos distintos
    poucos_jogos = _sinteticos(5, 40, p=0.95)
    muitos_jogos = _sinteticos(200, 1, p=0.95)

    assert rederivar(poucos_jogos, *par, atuais)[0]["Corners"] == atuais["Corners"]
    assert rederivar(muitos_jogos, *par, atuais)[0]["Corners"] != atuais["Corners"]


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
