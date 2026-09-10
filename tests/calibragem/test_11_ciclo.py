# -*- coding: utf-8 -*-
"""O ciclo e o fallback. Banco fora do ar NAO pode virar identidade."""
import copy
from datetime import datetime, timedelta, timezone

import pytest

from backend.modeling.calibragem import ciclo
from backend.modeling.calibragem.repositorio import Pick


@pytest.fixture(autouse=True)
def _ciclo_ligado(monkeypatch):
    """`CALIBRAGEM_ENABLED` e DESLIGADA por padrao (#248, C4). Os testes deste
    modulo exercitam o corpo de `executar()`, entao ligam a chave
    explicitamente — os dois testes da propria chave a sobrescrevem."""
    monkeypatch.setenv("CALIBRAGEM_ENABLED", "true")


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


# --- Rodada de correcao 1 do coordenador: `executar()` em si nao tinha
# nenhum teste commitado -- as correcoes A, B e C foram provadas so por
# dubles em memoria descartados. Formalizado aqui, reaproveitando o padrao
# de dublê de `_conn`/cursor de `test_09_auditoria.py`: `gravar_ciclo` e
# `garantir_tabela` continuam REAIS (nao mockados), rodando contra este
# dublê -- assim o teste prova o que de fato seria persistido, nao so o que
# `ciclo.py` monta em memoria antes de chamar o repositorio. ---


class _CursorGravador:
    """Protocolo de gerenciador de contexto nos dois niveis (`with _conn()
    as c, c.cursor() as cur:`), como em `test_09_auditoria.py`."""

    def __init__(self, registro):
        self.registro = registro

    def execute(self, sql, params=None):
        self.registro.append((" ".join(sql.split()), params))

    def fetchall(self):
        return []

    def fetchone(self):
        return None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _ConexaoGravadora:
    def __init__(self, registro):
        self._registro = registro

    def cursor(self):
        return _CursorGravador(self._registro)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


# A janela de reversao (#248, I1) e `publicado_em > criada_em`, entao os
# dubles precisam de datas: sem elas a janela e VAZIA de proposito e nenhuma
# reversao dispara.
ADOCAO = datetime(2026, 9, 1, 3, 0, tzinfo=timezone.utc)
DEPOIS = ADOCAO + timedelta(days=1)
ANTES = ADOCAO - timedelta(days=1)


def _servidos(n, liga="", p_raw=0.6, familia="Over/Under", y_periodico=5,
              publicado_em=DEPOIS):
    """Picks de um jogo cada, com odd ausente -- vale para os testes de
    reversao/sem_anterior, que nao precisam de `ev`/`edge`. `publicado_em`
    posterior a `ADOCAO` por padrao: sao os jogos que a vigente SERVIU."""
    return [Pick(f"jogo-{liga or 'g'}-{i}", familia, liga, p_raw,
                 1 if i % y_periodico else 0, None, "", publicado_em)
            for i in range(n)]


def _montar_ambiente(monkeypatch, *, picks, ajuste, vigentes,
                     anterior_por_celula, reversoes_por_celula=None):
    """Liga os dubles: leitura por monkeypatch direto em `repositorio.*`
    (como o resto deste arquivo ja faz com `carregar_parametros_para_curva`),
    escrita (`garantir_tabela`/`gravar_ciclo`) REAL, contra um `_conn` falso
    que grava cada `execute(sql, params)` em ordem. Devolve o registro.
    """
    import backend.modeling.calibragem.repositorio as repo

    registro = []
    monkeypatch.setattr(repo, "_conn", lambda: _ConexaoGravadora(registro))
    monkeypatch.setattr(ciclo.repositorio, "carregar_amostra",
                        lambda desde=None: picks)
    monkeypatch.setattr(ciclo.repositorio, "carregar_vigentes", lambda: vigentes)
    monkeypatch.setattr(
        ciclo.repositorio, "carregar_anterior",
        lambda familia, liga: anterior_por_celula.get((familia, liga)))
    reversoes = reversoes_por_celula or {}
    monkeypatch.setattr(
        ciclo.repositorio, "contar_reversoes_seguidas",
        lambda familia, liga: reversoes.get((familia, liga), 0))
    monkeypatch.setattr(ciclo.estimador, "ajustar_hierarquico",
                        lambda picks: dict(ajuste))
    return registro


def _linhas_persistidas(registro):
    """Os dicts de parametros das chamadas INSERT/UPDATE de linha (a UPDATE
    de promocao usa tupla, nao dict -- fica de fora por construcao)."""
    return [params for _, params in registro if isinstance(params, dict)]


RUIM = {"versao": 5, "a": -0.90, "b": 1.0, "criada_em": ADOCAO}
BOA_ANTERIOR = {"versao": 4, "a": 0.45, "b": 1.0}  # sobe a probabilidade


def test_reversao_dispara_quando_vigente_e_pior_que_a_anterior(monkeypatch):
    """Correcao A, prova pelo efeito observavel: SE `avaliar_reversao`
    recebesse o mesmo dict como `vigente` e `anterior` (o bug do brief
    literal), os dois Briers seriam sempre iguais e a acao seria sempre
    'manter'. Aqui `carregar_anterior` devolve uma versao DIFERENTE e
    melhor (BOA_ANTERIOR sobe a probabilidade; RUIM, a vigente, derruba) --
    com p_raw=0.6 e y=1 na maioria dos jogos, a vigente tem de perder."""
    picks = _servidos(30)   # >= MIN_N_JOGOS
    ajuste = {("Over/Under", ""): {"a": -0.90, "b": 1.0, "n_jogos": 30,
                                    "origem": "familia", "k_fixo": False}}
    registro = _montar_ambiente(
        monkeypatch, picks=picks, ajuste=ajuste,
        vigentes={("Over/Under", ""): dict(RUIM)},
        anterior_por_celula={("Over/Under", ""): dict(BOA_ANTERIOR)})

    resumo = ciclo.executar()

    assert resumo["erro"] is None
    assert resumo["revertidas"] == 1
    linhas = _linhas_persistidas(registro)
    assert any(p["status"] == "revertida" for p in linhas)


def test_valor_revertido_persistido_vem_da_anterior_nao_da_vigente(monkeypatch):
    """Correcao B, no mesmo cenario do teste anterior: o (a, b) que de fato
    seria GRAVADO no banco (via `gravar_ciclo` real) tem de ser o da
    ANTERIOR, nao o da vigente abandonada. Valores bem distintos (0.45 vs
    -0.90) para a asserção nao passar por coincidencia."""
    picks = _servidos(30)
    ajuste = {("Over/Under", ""): {"a": -0.90, "b": 1.0, "n_jogos": 30,
                                    "origem": "familia", "k_fixo": False}}
    registro = _montar_ambiente(
        monkeypatch, picks=picks, ajuste=ajuste,
        vigentes={("Over/Under", ""): dict(RUIM)},
        anterior_por_celula={("Over/Under", ""): dict(BOA_ANTERIOR)})

    ciclo.executar()

    linhas = _linhas_persistidas(registro)
    revertida = next(p for p in linhas if p["status"] == "revertida")
    assert revertida["a"] == pytest.approx(BOA_ANTERIOR["a"])
    assert revertida["b"] == pytest.approx(BOA_ANTERIOR["b"])
    assert revertida["a"] != pytest.approx(RUIM["a"])
    # A copia promovida a "vigente" tambem tem de carregar o par da anterior
    # -- e ela, nao a da vigente abandonada, que vale a partir daqui.
    vigente_promovida = next(
        p for p in linhas if p.get("status") == "vigente")
    assert vigente_promovida["a"] == pytest.approx(BOA_ANTERIOR["a"])
    assert vigente_promovida["b"] == pytest.approx(BOA_ANTERIOR["b"])


def test_reversao_pulada_sem_anterior_e_motivo_registra(monkeypatch):
    """Correcao A, o outro ramo: `carregar_anterior` devolve `None` (celula
    nova, o caso normal nos primeiros ciclos) -- a avaliacao de reversao e
    PULADA (nao ha erro, nao ha tentativa de reverter para nada) e o motivo
    da linha persistida contem 'sem_anterior'."""
    picks = _servidos(30, liga="x")
    ajuste = {("Over/Under", "x"): {"a": -0.90, "b": 1.0, "n_jogos": 30,
                                     "origem": "liga", "k_fixo": False}}
    registro = _montar_ambiente(
        monkeypatch, picks=picks, ajuste=ajuste,
        vigentes={("Over/Under", "x"): {"versao": 5, "a": -0.90, "b": 1.0}},
        anterior_por_celula={})   # sem anterior para NENHUMA celula

    resumo = ciclo.executar()

    assert resumo["erro"] is None
    assert resumo["revertidas"] == 0
    linhas = _linhas_persistidas(registro)
    linha = next(p for p in linhas
                if p["familia"] == "Over/Under" and p["liga"] == "x")
    assert "sem_anterior" in linha["motivo"]


def test_limiares_sao_rederivados_e_chegam_na_linha_sem_mexer_no_default(monkeypatch):
    """Correcao C: `rederivar` roda de verdade e o resultado chega na linha
    persistida; `DEFAULT_THRESHOLDS` (comparado por copia profunda antes e
    depois) fica intocado -- so a linha de auditoria carrega o resultado."""
    from backend.services.ev_classification import DEFAULT_THRESHOLDS
    antes = copy.deepcopy(DEFAULT_THRESHOLDS)

    # odd real (nao None) para o rederivar ter volume a preservar; p_raw e
    # odd variados para nao cair no atalho "sem preco -> nao mexe".
    picks = [
        Pick(f"jogoR{i}", "Over/Under", "", 0.30 + (i % 40) / 100.0,
            1 if i % 5 else 0, odd=1.5 + (i % 9) / 10.0)
        for i in range(300)
    ]
    ajuste = {("Over/Under", ""): {"a": 0.5, "b": 1.0, "n_jogos": 300,
                                    "origem": "familia", "k_fixo": False}}
    registro = _montar_ambiente(
        monkeypatch, picks=picks, ajuste=ajuste,
        vigentes={("Over/Under", ""): {"versao": 2, "a": 0.0, "b": 1.0}},
        anterior_por_celula={})

    resumo = ciclo.executar()
    assert resumo["erro"] is None

    linhas = _linhas_persistidas(registro)
    linha = next(p for p in linhas
                if p["familia"] == "Over/Under" and p["liga"] == "")
    campos = ("safe_ev", "neutro_ev", "safe_edge", "neutro_edge")
    for campo in campos:
        assert linha[campo] is not None, (
            f"{campo} deveria vir preenchido -- Correcao C quebrada")

    assert DEFAULT_THRESHOLDS == antes, (
        "DEFAULT_THRESHOLDS nao pode ser escrito pelo ciclo")

    # ao menos um dos quatro campos tem de ter se afastado do default --
    # senao pode ser so o valor "atual" passando direto sem recomputar
    # (por exemplo, o atalho de familia-sem-odd de `limiares.rederivar`).
    algum_mudou = any(
        linha[campo] != antes["Over/Under"][campo] for campo in campos)
    assert algum_mudou, (
        "nenhum campo de limiar mudou do default -- rederivar() pode nao "
        "ter rodado de verdade")


def test_toda_celula_gera_linha_em_todo_ciclo(monkeypatch):
    """N celulas (excluindo a entrada global `("", "")` de
    `ajustar_hierarquico`) produzem N linhas, quaisquer que sejam os
    status."""
    picks = _servidos(25, liga="") + _servidos(25, liga="y")
    ajuste = {
        ("Over/Under", ""): {"a": -0.90, "b": 1.0, "n_jogos": 25,
                             "origem": "familia", "k_fixo": False},
        ("Over/Under", "y"): {"a": -0.90, "b": 1.0, "n_jogos": 25,
                              "origem": "liga", "k_fixo": False},
        ("", ""): {"a": 0.0, "b": 1.0, "n_jogos": 50, "origem": "global",
                  "k_fixo": False},   # entrada global -- tem de ser ignorada
    }
    registro = _montar_ambiente(
        monkeypatch, picks=picks, ajuste=ajuste,
        vigentes={
            ("Over/Under", ""): {"versao": 5, "a": -0.90, "b": 1.0},
            ("Over/Under", "y"): {"versao": 3, "a": -0.90, "b": 1.0},
        },
        anterior_por_celula={})

    resumo = ciclo.executar()

    assert resumo["celulas"] == 2   # a celula global nao conta
    linhas = _linhas_persistidas(registro)
    chaves = {(p["familia"], p["liga"]) for p in linhas}
    assert chaves == {("Over/Under", ""), ("Over/Under", "y")}
    assert len(linhas) == 2   # proposta == vigente nas duas -> sem promocao


def test_executar_nunca_levanta_e_preenche_erro(monkeypatch):
    """Falha aberta: uma excecao na leitura da amostra nao propaga -- o
    resumo devolve `erro` preenchido."""
    def explode(desde=None):
        raise RuntimeError("ledger indisponivel")
    monkeypatch.setattr(ciclo.repositorio, "carregar_amostra", explode)

    resumo = ciclo.executar()

    assert resumo["erro"] is not None
    assert "ledger indisponivel" in resumo["erro"]
    assert resumo["celulas"] == 0
    assert resumo["jogos"] == 0


# --- C4: a chave de desligamento. Sem ela, o deploy E a ativacao, e o ciclo
# roda >= 2x/dia contra a RDS de producao desde o primeiro cron. ---


def test_flag_desligada_nao_toca_o_banco_e_devolve_desligado(monkeypatch):
    """Padrao de fabrica: NADA acontece. Nem DDL, nem leitura, nem escrita.

    A prova e por explosao: `_conn` levanta se for chamada, e as tres funcoes
    de leitura do ciclo tambem. Se qualquer uma for alcancada, o teste falha
    com a mensagem de quem foi alcancada — em vez de so olhar o resumo, que
    passaria mesmo se o ciclo tivesse rodado e falhado por outro motivo.
    """
    import backend.modeling.calibragem.repositorio as repo

    monkeypatch.delenv("CALIBRAGEM_ENABLED", raising=False)

    def _proibido(*a, **k):
        raise AssertionError("com a flag desligada nada pode ser chamado")

    monkeypatch.setattr(repo, "_conn", _proibido)
    monkeypatch.setattr(ciclo.repositorio, "garantir_tabela", _proibido)
    monkeypatch.setattr(ciclo.repositorio, "carregar_amostra", _proibido)
    monkeypatch.setattr(ciclo.repositorio, "carregar_vigentes", _proibido)
    monkeypatch.setattr(ciclo.repositorio, "gravar_ciclo", _proibido)

    resumo = ciclo.executar()

    assert resumo["status"] == "desligado"
    assert resumo["erro"] is None
    assert resumo["celulas"] == 0 and resumo["jogos"] == 0


@pytest.mark.parametrize("valor", ["1", "true", "TRUE", "yes", "on"])
def test_flag_ligada_executa_o_ciclo(monkeypatch, valor):
    """O outro estado: com a chave ligada (em qualquer das formas aceitas
    pelo padrao da casa) o corpo roda e o status sai 'executado'."""
    monkeypatch.setenv("CALIBRAGEM_ENABLED", valor)
    picks = _servidos(25)
    ajuste = {("Over/Under", ""): {"a": -0.90, "b": 1.0, "n_jogos": 25,
                                   "origem": "familia", "k_fixo": False}}
    _montar_ambiente(
        monkeypatch, picks=picks, ajuste=ajuste,
        vigentes={("Over/Under", ""): {"versao": 5, "a": -0.90, "b": 1.0}},
        anterior_por_celula={})

    resumo = ciclo.executar()

    assert resumo["status"] == "executado"
    assert resumo["erro"] is None
    assert resumo["celulas"] == 1


@pytest.mark.parametrize("valor", ["0", "false", "no", "off", ""])
def test_valores_falsos_mantem_desligado(monkeypatch, valor):
    monkeypatch.setenv("CALIBRAGEM_ENABLED", valor)
    assert ciclo.calibragem_habilitada() is False


# --- I1: a janela de reversao e FORA da amostra de ajuste ---


def test_janela_exclui_os_jogos_anteriores_a_versao():
    """A funcao pura, direto: so o que foi publicado DEPOIS da adocao."""
    antigos = _servidos(3, publicado_em=ANTES)
    novos = _servidos(4, liga="n", publicado_em=DEPOIS)
    na_janela = ciclo.janela_de_reversao(antigos + novos, ADOCAO)
    assert len(na_janela) == 4
    assert {p.publicado_em for p in na_janela} == {DEPOIS}


def test_janela_e_estrita_no_instante_da_adocao():
    """Publicado no MESMO instante nao foi servido pela versao adotada."""
    assert ciclo.janela_de_reversao(_servidos(5, publicado_em=ADOCAO), ADOCAO) == []


def test_janela_vazia_sem_criada_em_ou_sem_publicado_em():
    """Falta de informacao nao vira 'a amostra inteira' — vira janela vazia,
    e `avaliar_reversao` devolve `manter` por falta de jogos."""
    assert ciclo.janela_de_reversao(_servidos(5), None) == []
    assert ciclo.janela_de_reversao(_servidos(5, publicado_em=None), ADOCAO) == []


def test_reversao_nao_dispara_quando_a_janela_e_toda_in_sample(monkeypatch):
    """O defeito I1 pelo efeito: os MESMOS picks e a MESMA vigente ruim do
    teste de reversao, so que publicados ANTES da adocao. Antes da correcao
    a amostra inteira alimentava `avaliar_reversao` e estes 30 jogos
    reverteriam; agora estao fora da janela e nada acontece.
    """
    picks = _servidos(30, publicado_em=ANTES)
    ajuste = {("Over/Under", ""): {"a": -0.90, "b": 1.0, "n_jogos": 30,
                                   "origem": "familia", "k_fixo": False}}
    registro = _montar_ambiente(
        monkeypatch, picks=picks, ajuste=ajuste,
        vigentes={("Over/Under", ""): dict(RUIM)},
        anterior_por_celula={("Over/Under", ""): dict(BOA_ANTERIOR)})

    resumo = ciclo.executar()

    assert resumo["erro"] is None
    assert resumo["revertidas"] == 0
    linha = next(p for p in _linhas_persistidas(registro)
                 if p["familia"] == "Over/Under")
    assert linha["status"] != "revertida"
    assert "0 jogos" in linha["motivo"], linha["motivo"]


def test_a_janela_ignora_jogos_de_antes_mas_conta_os_de_depois(monkeypatch):
    """O par do teste anterior: metade antes, metade depois. So a metade de
    depois entra, e ela sozinha ja basta (>= MIN_N_JOGOS) para reverter."""
    antigos = _servidos(25, liga="", publicado_em=ANTES)
    novos = [p._replace(match_id=f"novo-{i}", publicado_em=DEPOIS)
             for i, p in enumerate(_servidos(25))]
    ajuste = {("Over/Under", ""): {"a": -0.90, "b": 1.0, "n_jogos": 50,
                                   "origem": "familia", "k_fixo": False}}
    registro = _montar_ambiente(
        monkeypatch, picks=antigos + novos, ajuste=ajuste,
        vigentes={("Over/Under", ""): dict(RUIM)},
        anterior_por_celula={("Over/Under", ""): dict(BOA_ANTERIOR)})

    resumo = ciclo.executar()

    assert resumo["revertidas"] == 1
    linha = next(p for p in _linhas_persistidas(registro)
                 if p["status"] == "revertida")
    assert "em 25 jogos" in linha["motivo"], linha["motivo"]
