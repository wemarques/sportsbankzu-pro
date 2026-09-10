# -*- coding: utf-8 -*-
"""Teste 8 da spec — nada acontece em silencio.

O #247 achou um gate (odds_value_added < -0,015) que NUNCA disparou em 33
ligas e ninguem sabia. O #246 so encontrou o filtro de corredor porque
[CORRIDOR-DROPPED] vazou no log de um teste. Um sistema que muda o numero
sozinho e so registra quando muda e um sistema onde a inacao e invisivel.
"""
from datetime import datetime, timezone

import pytest

from backend.modeling.calibragem.repositorio import (
    carregar_anterior, montar_linha_auditoria,
)


class _CursorGravador:
    """Dublê de cursor que registra cada `execute(sql, params)` em ordem, e
    devolve `fetchall`/`fetchone` fixos configurados no construtor.
    """

    def __init__(self, fetchall=None, fetchone=None, registro=None):
        self._fetchall = fetchall if fetchall is not None else []
        self._fetchone = fetchone
        self.registro = registro if registro is not None else []

    def execute(self, sql, params=None):
        self.registro.append((" ".join(sql.split()), params))

    def fetchall(self):
        return self._fetchall

    def fetchone(self):
        return self._fetchone

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _ConexaoGravadora:
    """#248, I6: `close()` faz parte do protocolo agora — `repositorio`
    fecha a conexao explicitamente num `finally`. Dublê sem `close` faria o
    teste passar com codigo que nunca fecha."""

    def __init__(self, cursor):
        self._cursor = cursor
        self.fechada = False

    def cursor(self):
        return self._cursor

    def close(self):
        self.fechada = True

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _tipo_sql(sql: str) -> str:
    s = sql.strip().upper()
    return "UPDATE" if s.startswith("UPDATE") else "INSERT" if s.startswith("INSERT") else s.split()[0]

CELULAS = [("Over/Under", ""), ("Corners", ""), ("Corners", "mls"),
           ("Cards", ""), ("BTTS", ""), ("1X2", ""), ("Double Chance", "")]


def test_toda_celula_gera_linha_qualquer_que_seja_o_status():
    linhas = [
        montar_linha_auditoria(f, l, versao=3, resultado={
            "a": 0.1, "b": 1.0, "status": st, "fator_encurtamento": None,
            "motivo": "",
        }, n_jogos=50, origem="familia", brier=None)
        for (f, l), st in zip(CELULAS, [
            "adotada", "encurtada", "rejeitada", "abaixo_do_piso",
            "inalterada", "revertida", "congelada"])
    ]
    assert len(linhas) == len(CELULAS)
    assert {ln["status"] for ln in linhas} == {
        "adotada", "encurtada", "rejeitada", "abaixo_do_piso",
        "inalterada", "revertida", "congelada"}


def test_linha_inalterada_tambem_carrega_os_parametros():
    ln = montar_linha_auditoria("BTTS", "", versao=7, resultado={
        "a": 0.2, "b": 0.95, "status": "inalterada",
        "fator_encurtamento": None, "motivo": "proposta identica",
    }, n_jogos=31, origem="familia", brier=0.2134)
    assert ln["a"] == 0.2 and ln["b"] == 0.95
    assert ln["n_jogos"] == 31 and ln["brier_validacao"] == 0.2134
    assert ln["motivo"] == "proposta identica"


def test_encurtada_grava_o_fator():
    ln = montar_linha_auditoria("Corners", "", versao=2, resultado={
        "a": 0.05, "b": 1.0, "status": "encurtada",
        "fator_encurtamento": 0.31, "motivo": "passo limitado",
    }, n_jogos=220, origem="familia", brier=None)
    assert ln["fator_encurtamento"] == 0.31


def test_status_desconhecido_levanta():
    with pytest.raises(ValueError, match="status"):
        montar_linha_auditoria("BTTS", "", versao=1, resultado={
            "a": 0.0, "b": 1.0, "status": "mais_ou_menos",
            "fator_encurtamento": None, "motivo": "",
        }, n_jogos=50, origem="familia", brier=None)


# --- Correcao A: curva e limiar mudam juntos, na mesma linha de auditoria ---

def test_com_limiares_a_linha_carrega_os_quatro_valores():
    ln = montar_linha_auditoria("Over/Under", "", versao=4, resultado={
        "a": 0.1, "b": 1.0, "status": "adotada",
        "fator_encurtamento": None, "motivo": "",
    }, n_jogos=50, origem="familia", brier=None, limiares={
        "safe_ev": 0.02, "neutro_ev": 0.0,
        "safe_edge": 0.05, "neutro_edge": 0.01,
    })
    assert ln["safe_ev"] == 0.02
    assert ln["neutro_ev"] == 0.0
    assert ln["safe_edge"] == 0.05
    assert ln["neutro_edge"] == 0.01


def test_sem_limiares_os_quatro_saem_none():
    ln = montar_linha_auditoria("Over/Under", "", versao=4, resultado={
        "a": 0.1, "b": 1.0, "status": "adotada",
        "fator_encurtamento": None, "motivo": "",
    }, n_jogos=50, origem="familia", brier=None)
    assert ln["safe_ev"] is None
    assert ln["neutro_ev"] is None
    assert ln["safe_edge"] is None
    assert ln["neutro_edge"] is None


# --- Correcao B: `carregar_anterior` nao pode devolver o mesmo dict do
# vigente, ou `avaliar_reversao` nunca reverte (dois Briers sempre iguais). ---

def test_carregar_anterior_formato_com_dublê(monkeypatch):
    import backend.modeling.calibragem.repositorio as repo

    class _CursorFalso:
        def __init__(self, linha):
            self._linha = linha

        def execute(self, *a, **k):
            pass

        def fetchone(self):
            return self._linha

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class _ConexaoFalsa:
        def __init__(self, linha):
            self._linha = linha

        def cursor(self):
            return _CursorFalso(self._linha)

        def close(self):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(repo, "_conn",
                        lambda: _ConexaoFalsa((5, 0.12, 0.98)))
    anterior = repo.carregar_anterior("BTTS", "")
    assert anterior == {"versao": 5, "a": 0.12, "b": 0.98}


def test_carregar_anterior_devolve_none_quando_nao_existe(monkeypatch):
    import backend.modeling.calibragem.repositorio as repo

    class _CursorVazio:
        def execute(self, *a, **k):
            pass

        def fetchone(self):
            return None

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class _ConexaoVazia:
        def cursor(self):
            return _CursorVazio()

        def close(self):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(repo, "_conn", lambda: _ConexaoVazia())
    assert repo.carregar_anterior("BTTS", "") is None


# --- Rodada de correcao 1: reversao tem de promover, e a promocao precisa
# de teste (dublê de conexao/cursor), nao so leitura de codigo. ---


@pytest.mark.parametrize("status", ["adotada", "encurtada", "revertida"])
def test_gravar_ciclo_promove_status_de_promocao(monkeypatch, status):
    """`revertida` promove igual a `adotada`/`encurtada`: sem isso a versao
    ruim continua `vigente` e a reversao vira so uma linha de log."""
    import backend.modeling.calibragem.repositorio as repo

    registro = []
    monkeypatch.setattr(repo, "_conn",
                        lambda: _ConexaoGravadora(_CursorGravador(registro=registro)))

    linha = montar_linha_auditoria("BTTS", "", versao=3, resultado={
        "a": 0.1, "b": 1.0, "status": status,
        "fator_encurtamento": None, "motivo": "",
    }, n_jogos=50, origem="familia", brier=None)

    n = repo.gravar_ciclo([linha])
    assert n == 1

    tipos = [_tipo_sql(sql) for sql, _ in registro]
    assert tipos == ["UPDATE", "INSERT", "INSERT"], (
        "promocao tem de ser UPDATE seguido de DOIS INSERTs, nessa ordem")

    _, params_update = registro[0]
    assert params_update == ("BTTS", "")

    _, params_vigente = registro[1]
    assert params_vigente["status"] == "vigente"
    assert params_vigente["a"] == 0.1 and params_vigente["b"] == 1.0

    _, params_historico = registro[2]
    assert params_historico["status"] == status


@pytest.mark.parametrize("status", [
    "rejeitada", "abaixo_do_piso", "inalterada", "congelada"])
def test_gravar_ciclo_nao_promove_status_fora_do_conjunto(monkeypatch, status):
    import backend.modeling.calibragem.repositorio as repo

    registro = []
    monkeypatch.setattr(repo, "_conn",
                        lambda: _ConexaoGravadora(_CursorGravador(registro=registro)))

    linha = montar_linha_auditoria("BTTS", "", versao=3, resultado={
        "a": 0.1, "b": 1.0, "status": status,
        "fator_encurtamento": None, "motivo": "",
    }, n_jogos=50, origem="familia", brier=None)

    n = repo.gravar_ciclo([linha])
    assert n == 1

    tipos = [_tipo_sql(sql) for sql, _ in registro]
    assert tipos == ["INSERT"], "sem promocao: nenhum UPDATE, um unico INSERT"

    _, params = registro[0]
    assert params["status"] == status


def test_gravar_ciclo_duas_celulas_promocao_isolada(monkeypatch):
    """Cada celula recebe o seu proprio UPDATE; a promocao de uma nao toca
    a outra."""
    import backend.modeling.calibragem.repositorio as repo

    registro = []
    monkeypatch.setattr(repo, "_conn",
                        lambda: _ConexaoGravadora(_CursorGravador(registro=registro)))

    linha_promovida = montar_linha_auditoria("BTTS", "", versao=1, resultado={
        "a": 0.1, "b": 1.0, "status": "adotada",
        "fator_encurtamento": None, "motivo": "",
    }, n_jogos=50, origem="familia", brier=None)
    linha_nao_promovida = montar_linha_auditoria("Corners", "", versao=1, resultado={
        "a": 0.2, "b": 1.0, "status": "inalterada",
        "fator_encurtamento": None, "motivo": "",
    }, n_jogos=50, origem="familia", brier=None)

    n = repo.gravar_ciclo([linha_promovida, linha_nao_promovida])
    assert n == 2

    tipos = [_tipo_sql(sql) for sql, _ in registro]
    assert tipos == ["UPDATE", "INSERT", "INSERT", "INSERT"]

    _, params_update = registro[0]
    assert params_update == ("BTTS", ""), "o UPDATE e so da celula promovida"

    familias_inseridas = [p["familia"] for _, p in registro[1:]]
    assert familias_inseridas == ["BTTS", "BTTS", "Corners"]


def test_gravar_ciclo_vazio_nao_abre_conexao(monkeypatch):
    import backend.modeling.calibragem.repositorio as repo

    def _conn_nao_deveria_ser_chamada():
        raise AssertionError("gravar_ciclo([]) nao deveria abrir conexao")

    monkeypatch.setattr(repo, "_conn", _conn_nao_deveria_ser_chamada)
    assert repo.gravar_ciclo([]) == 0


def test_carregar_vigentes_formato(monkeypatch):
    """`criada_em` viaja junto (#248, I1): e o inicio da janela de reversao,
    sem ele a janela seria a amostra inteira (in-sample)."""
    import backend.modeling.calibragem.repositorio as repo

    t1 = datetime(2026, 8, 1, 3, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 9, 1, 3, 0, tzinfo=timezone.utc)
    linhas = [("BTTS", "", 3, 0.1, 1.0, t1),
              ("Over/Under", "mls", 5, -0.2, 0.9, t2)]
    monkeypatch.setattr(repo, "_conn",
                        lambda: _ConexaoGravadora(_CursorGravador(fetchall=linhas)))

    assert repo.carregar_vigentes() == {
        ("BTTS", ""): {"versao": 3, "a": 0.1, "b": 1.0, "criada_em": t1},
        ("Over/Under", "mls"): {"versao": 5, "a": -0.2, "b": 0.9,
                                "criada_em": t2},
    }


def test_carregar_vigentes_vazio(monkeypatch):
    import backend.modeling.calibragem.repositorio as repo

    monkeypatch.setattr(repo, "_conn",
                        lambda: _ConexaoGravadora(_CursorGravador(fetchall=[])))
    assert repo.carregar_vigentes() == {}


def test_carregar_parametros_para_curva_formato(monkeypatch):
    import backend.modeling.calibragem.repositorio as repo

    linhas = [("BTTS", "", 3, 0.1, 1.0,
               datetime(2026, 8, 1, tzinfo=timezone.utc))]
    monkeypatch.setattr(repo, "_conn",
                        lambda: _ConexaoGravadora(_CursorGravador(fetchall=linhas)))

    assert repo.carregar_parametros_para_curva() == {("BTTS", ""): (3, 0.1, 1.0)}


def test_carregar_parametros_para_curva_vazio(monkeypatch):
    import backend.modeling.calibragem.repositorio as repo

    monkeypatch.setattr(repo, "_conn",
                        lambda: _ConexaoGravadora(_CursorGravador(fetchall=[])))
    assert repo.carregar_parametros_para_curva() == {}


@pytest.mark.parametrize("sequencia,esperado", [
    ([], 0),
    (["revertida"], 1),
    (["revertida", "revertida"], 2),
    (["adotada", "revertida"], 0),
])
def test_contar_reversoes_seguidas(monkeypatch, sequencia, esperado):
    """Sequencia na ordem devolvida pelo SQL (`ORDER BY id DESC`): a mais
    recente primeiro. `["adotada", "revertida"]` da zero — a adocao mais
    recente zera o contador; nao e uma tentativa que soma.

    `inalterada` fica de fora do `WHERE` de proposito (decisao do
    coordenador, nao um defeito): um ciclo sem tentativa nao zera a
    sequencia de reversoes, so uma adocao bem-sucedida zera.
    """
    import backend.modeling.calibragem.repositorio as repo

    fetchall = [(s,) for s in sequencia]
    monkeypatch.setattr(repo, "_conn",
                        lambda: _ConexaoGravadora(_CursorGravador(fetchall=fetchall)))

    assert repo.contar_reversoes_seguidas("BTTS", "") == esperado


# --- I2: o status congelado tem de ser LEGIVEL de volta, ou o congelamento
# nao sobrevive ao proximo ciclo. ---


@pytest.mark.parametrize("linha,esperado", [
    (("congelada",), "congelada"),
    (("adotada",), "adotada"),
    (None, None),
])
def test_ultimo_status_de_ciclo(monkeypatch, linha, esperado):
    import backend.modeling.calibragem.repositorio as repo

    registro = []
    monkeypatch.setattr(repo, "_conn", lambda: _ConexaoGravadora(
        _CursorGravador(fetchone=linha, registro=registro)))

    assert repo.ultimo_status_de_ciclo("BTTS", "") == esperado

    sql, params = registro[0]
    assert "ORDER BY id DESC" in sql and "LIMIT 1" in sql
    # `vigente` e `substituida` sao escrituracao, nao decisao: se entrassem
    # no filtro, a copia promovida (sempre a mais recente para uma celula
    # adotada) esconderia a decisao real.
    assert "vigente" not in params[2] and "substituida" not in params[2]
    assert "congelada" in params[2]


# --- I6/I7: a conexao tem prazo e e fechada; `vigente` e unica no indice ---


def test_conn_passa_connect_timeout(monkeypatch):
    """Sem `connect_timeout` o psycopg2 herda o do SO (minutos). Este modulo
    e alcancado pelo caminho de /fixtures, que ja namora o teto de 60s da
    Lambda."""
    import psycopg2

    import backend.modeling.calibragem.repositorio as repo

    capturado = {}

    def _falso_connect(dsn, **kwargs):
        capturado["dsn"] = dsn
        capturado["kwargs"] = kwargs
        return object()

    monkeypatch.setattr(psycopg2, "connect", _falso_connect)
    monkeypatch.setenv("DATABASE_URL", "postgres://exemplo/db")
    repo._conn()

    assert capturado["kwargs"]["connect_timeout"] == 5


def test_conexao_fecha_mesmo_quando_o_corpo_levanta(monkeypatch):
    """`with conn` do psycopg2 encerra a TRANSACAO, nao a conexao — o socket
    ficava aberto ate o coletor passar."""
    import backend.modeling.calibragem.repositorio as repo

    conexao = _ConexaoGravadora(_CursorGravador())
    monkeypatch.setattr(repo, "_conn", lambda: conexao)

    with pytest.raises(RuntimeError):
        with repo._conexao():
            raise RuntimeError("falha no meio do trabalho")

    assert conexao.fechada is True


def test_conexao_fecha_no_caminho_feliz(monkeypatch):
    import backend.modeling.calibragem.repositorio as repo

    conexao = _ConexaoGravadora(_CursorGravador())
    monkeypatch.setattr(repo, "_conn", lambda: conexao)
    with repo._conexao():
        pass
    assert conexao.fechada is True


def test_indice_de_vigente_e_unico_e_troca_o_antigo(monkeypatch):
    """O indice antigo tinha o mesmo nome e NAO era unico: `CREATE UNIQUE
    INDEX IF NOT EXISTS` com o mesmo nome seria um no-op sobre ele. Por isso
    o antigo e derrubado e o novo tem nome proprio."""
    import backend.modeling.calibragem.repositorio as repo

    registro = []
    monkeypatch.setattr(repo, "_conn", lambda: _ConexaoGravadora(
        _CursorGravador(registro=registro)))

    assert repo.garantir_indice_vigente_unico() is True

    sqls = [sql for sql, _ in registro]
    assert sqls[0].startswith("DROP INDEX IF EXISTS idx_calibragem_vigente")
    assert "CREATE UNIQUE INDEX" in sqls[1]
    assert "WHERE status = 'vigente'" in sqls[1]
    assert "idx_calibragem_vigente_unico" in sqls[1]


def test_indice_unico_falho_nao_derruba_garantir_tabela(monkeypatch, caplog):
    """Banco com duplicatas anteriores recusa o UNIQUE. Isso NAO pode
    quebrar a criacao da tabela, e as celulas culpadas tem de aparecer no
    log — nao ha conserto automatico, mas tampouco silencio."""
    import logging

    import backend.modeling.calibragem.repositorio as repo

    class _CursorQueRecusaIndice(_CursorGravador):
        def execute(self, sql, params=None):
            super().execute(sql, params)
            if "CREATE UNIQUE INDEX" in sql:
                raise RuntimeError(
                    "could not create unique index: key (familia, liga)=(Corners, ) "
                    "is duplicated")

    def _conexao_falsa():
        return _ConexaoGravadora(_CursorQueRecusaIndice(
            fetchall=[("Corners", "", 2)]))

    monkeypatch.setattr(repo, "_conn", _conexao_falsa)

    with caplog.at_level(logging.ERROR,
                         logger="sportsbankzu.calibragem.repositorio"):
        assert repo.garantir_tabela() is True          # a tabela foi criada
        assert repo.garantir_indice_vigente_unico() is False

    texto = caplog.text
    assert "NAO criado" in texto
    assert "Corners" in texto, texto
