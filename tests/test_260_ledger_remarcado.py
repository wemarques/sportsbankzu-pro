# -*- coding: utf-8 -*-
"""#260 — jogo remarcado deixa picks orfaos com desfecho nulo para sempre.

Caso real medido em producao em 2026-09-22 (`/ledger/dia?data=2026-09-21`):
o FootyStats moveu Criciuma x Operario PR de 2026-09-21T22:30Z para
2026-09-22T22:30Z. O cron gravou 7 picks novos sob o match_id novo
(epoch 1790116200.0); os 7 picks antigos (epoch 1790029800.0) ficam
`outcome` nulo para sempre porque o kickoff antigo nunca aconteceu, entao o
cron de desfechos nunca os resolve.

`remover_remarcados` (backend/services/amostra_ledger.py) e a funcao pura
que tira essas linhas da leitura. Este arquivo testa a funcao isolada
(casos de borda com dicts sinteticos) e a integracao via `dia`/`agregado`/
`picks` de `backend/services/ledger_leitura.py`, reaproveitando o dublê
`_Conn`/`_linha` de `tests/test_255_ledger_leitura.py` (proibicao 5 —
nao reimplementar o dublê de conexao).
"""
from datetime import datetime, timedelta, timezone

from backend.services import ledger_leitura as L
from backend.services.amostra_ledger import remover_remarcados
from tests.test_255_ledger_leitura import _Conn, _linha

_UTC = timezone.utc


class _CursorHonraJanela:
    """Diferente do `_Cursor` de test_255 (que ignora `params` e sempre
    devolve todas as linhas fixas), este dublê filtra por `published_at`
    entre os dois parametros de `execute`, como o SQL real
    (`l.published_at >= %s AND l.published_at < %s`). Necessario para
    reproduzir o bug do #260 fix round 1: a janela original de
    `_buscar_janela` corta em `fim` e nunca enxerga a geracao NOVA de um
    jogo remarcado, publicada depois de `fim`."""

    def __init__(self, linhas):
        self._linhas = linhas
        self.sql = None
        self.params = None
        self._resultado = []

    def execute(self, sql, params=None):
        self.sql = sql
        self.params = params
        inicio, fim = params
        # indice 7 = published_at, na ordem de `_linha()` (match_id,
        # league_id, market, selection, prob, book_odd, classification,
        # published_at, kickoff_utc, outcome, detail).
        self._resultado = [r for r in self._linhas if inicio <= r[7] < fim]

    def fetchall(self):
        return self._resultado

    def close(self):
        pass


class _ConnHonraJanela:
    def __init__(self, linhas):
        self.cur = _CursorHonraJanela(linhas)

    def cursor(self):
        return self.cur

    def close(self):
        pass

# IDs e kickoffs reais do caso medido em producao (2026-09-22).
_CRICIUMA_ANTIGO = "brasileirao-serie-b-Criciúma-Operário PR-1790029800.0"
_K_ANTIGO = datetime(2026, 9, 21, 22, 30, tzinfo=_UTC)
_CRICIUMA_NOVO = "brasileirao-serie-b-Criciúma-Operário PR-1790116200.0"
_K_NOVO = datetime(2026, 9, 22, 22, 30, tzinfo=_UTC)      # +24h, dentro dos 14 dias

_CUIABA_NAUTICO = "brasileirao-serie-b-Cuiabá-Náutico-1790037000.0"
_K_CUIABA = datetime(2026, 9, 22, 0, 30, tzinfo=_UTC)


# ---------------------------------------------------------------------------
# Casos de borda: funcao pura, dicts sinteticos (nao passam pelo SQL/dublê).
# ---------------------------------------------------------------------------

def _pick(match_id, kickoff_utc, outcome=None):
    return {"match_id": match_id, "kickoff_utc": kickoff_utc, "outcome": outcome}


def test_remarcado_sai():
    linhas = [
        _pick(_CRICIUMA_ANTIGO, _K_ANTIGO, outcome=None),
        _pick(_CRICIUMA_NOVO, _K_NOVO, outcome=None),
    ]
    mantidas, removidas = remover_remarcados(linhas)
    assert [l["match_id"] for l in mantidas] == [_CRICIUMA_NOVO]
    assert [l["match_id"] for l in removidas] == [_CRICIUMA_ANTIGO]


def test_com_desfecho_fica_ida_e_volta():
    """L com outcome preenchido NUNCA e remarcada, mesmo com M mais novo e
    kickoff proximo — sao dois jogos entre os mesmos times (ida/volta)."""
    base = "copa-do-brasil-Cuiabá-Náutico"
    k_ida = datetime(2026, 8, 1, 20, 0, tzinfo=_UTC)
    k_volta = datetime(2026, 8, 10, 20, 0, tzinfo=_UTC)
    linhas = [
        {"match_id": f"{base}-1785700800.0", "kickoff_utc": k_ida, "outcome": 1},
        {"match_id": f"{base}-1786478400.0", "kickoff_utc": k_volta, "outcome": 0},
    ]
    mantidas, removidas = remover_remarcados(linhas)
    assert len(mantidas) == 2
    assert removidas == []


def test_mesmo_epoch_fica():
    """Duas linhas (mercados diferentes) do MESMO match_id — epoch identico,
    nao e remarcacao (mesma geracao)."""
    linhas = [
        _pick(_CRICIUMA_ANTIGO, _K_ANTIGO, outcome=None),
        _pick(_CRICIUMA_ANTIGO, _K_ANTIGO, outcome=None),
    ]
    mantidas, removidas = remover_remarcados(linhas)
    assert len(mantidas) == 2
    assert removidas == []


def test_mais_de_14_dias_fica():
    """M com kickoff mais de 14 dias depois de L: L fica pendente (limitacao
    conhecida, documentada no docstring)."""
    base = "brasileirao-serie-b-Time A-Time B"
    k_l = datetime(2026, 9, 1, 20, 0, tzinfo=_UTC)
    k_m = k_l + timedelta(days=20)
    linhas = [
        {"match_id": f"{base}-1756757600.0", "kickoff_utc": k_l, "outcome": None},
        {"match_id": f"{base}-1758485600.0", "kickoff_utc": k_m, "outcome": None},
    ]
    mantidas, removidas = remover_remarcados(linhas)
    assert len(mantidas) == 2
    assert removidas == []


def test_base_sem_epoch_parseavel_fica():
    """match_id sem sufixo epoch numerico: nunca e considerada remarcada,
    mesmo existindo outra linha de base identica com epoch maior."""
    linhas = [
        {"match_id": "amistoso-Time A-Time B-final", "kickoff_utc": _K_ANTIGO, "outcome": None},
        {"match_id": "amistoso-Time A-Time B-final", "kickoff_utc": _K_NOVO, "outcome": None},
    ]
    mantidas, removidas = remover_remarcados(linhas)
    assert len(mantidas) == 2
    assert removidas == []


# ---------------------------------------------------------------------------
# Integracao: dia/agregado/picks todos sem o id antigo.
# ---------------------------------------------------------------------------

def _linhas_caso_real():
    pub_antigo = datetime(2026, 9, 18, 9, 0, tzinfo=_UTC)
    pub_novo = datetime(2026, 9, 21, 9, 0, tzinfo=_UTC)
    pub_cuiaba = datetime(2026, 9, 20, 9, 0, tzinfo=_UTC)
    return [
        # Criciuma x Operario — id ANTIGO, orfao (outcome nulo para sempre).
        _linha(_CRICIUMA_ANTIGO, "Over/Under", "Under 3.5", 0.6, 1.5, "SAFE",
              pub_antigo, _K_ANTIGO, outcome=None, league_id="brasileirao-serie-b"),
        _linha(_CRICIUMA_ANTIGO, "Cards", "Over 1.5", 0.55, 1.4, "SAFE",
              pub_antigo, _K_ANTIGO, outcome=None, league_id="brasileirao-serie-b"),
        # Criciuma x Operario — id NOVO, valido.
        _linha(_CRICIUMA_NOVO, "Over/Under", "Under 3.5", 0.6, 1.5, "SAFE",
              pub_novo, _K_NOVO, outcome=None, league_id="brasileirao-serie-b"),
        # Cuiaba x Nautico — controle, resolvido, nao afetado.
        _linha(_CUIABA_NAUTICO, "Corners", "Corners Over 4.5", 0.78, 1.3,
              "NEUTRO", pub_cuiaba, _K_CUIABA, outcome=1,
              detail={"total_corners": 11}, league_id="brasileirao-serie-b"),
    ]


def test_dia_21_nao_lista_id_antigo(monkeypatch):
    monkeypatch.setattr(L, "_conn", lambda: _Conn(_linhas_caso_real()))
    r = L.dia("2026-09-21")
    ids = {p["match_id"] for p in r["picks"]}
    assert _CRICIUMA_ANTIGO not in ids
    assert _CUIABA_NAUTICO in ids          # controle resolvido continua


def test_dia_22_lista_id_novo(monkeypatch):
    monkeypatch.setattr(L, "_conn", lambda: _Conn(_linhas_caso_real()))
    r = L.dia("2026-09-22")
    ids = {p["match_id"] for p in r["picks"]}
    assert _CRICIUMA_NOVO in ids
    assert _CRICIUMA_ANTIGO not in ids


def test_agregado_30d_nao_conta_id_antigo(monkeypatch):
    monkeypatch.setattr(L, "_conn", lambda: _Conn(_linhas_caso_real()))
    r = L.agregado("30d", hoje=datetime(2026, 9, 22, tzinfo=_UTC))
    # Cuiaba x Nautico e classificacao NEUTRO (nao conta no resumo, so
    # SAFE/NEUTRO_QUALIFICADO contam — spec §4.2). Sem a remocao do id
    # antigo, "picks" seria 2 (1 SAFE antigo pendente + 1 SAFE novo
    # pendente); com a regra #260, so sobra o novo.
    assert r["acerto"]["picks"] == 1
    assert r["acerto"]["resolvidos"] == 0


def test_picks_30d_nao_retorna_id_antigo(monkeypatch):
    monkeypatch.setattr(L, "_conn", lambda: _Conn(_linhas_caso_real()))
    r = L.picks("30d", hoje=datetime(2026, 9, 22, tzinfo=_UTC))
    ids = {p["match_id"] for p in r["picks"]}
    assert _CRICIUMA_ANTIGO not in ids


# ---------------------------------------------------------------------------
# #260 fix round 1: a geracao nova pode ser publicada DEPOIS do `fim` da
# janela consultada para o dia antigo — a consulta SQL precisa de folga para
# enxerga-la, senao `remover_remarcados` nunca ve o par e o id antigo
# continua aparecendo. Dublê `_ConnHonraJanela` (honra published_at do SQL,
# diferente de `_Conn` que ignora os parametros).
# ---------------------------------------------------------------------------

def test_dia_21_nao_lista_nem_o_id_antigo_nem_o_novo_260_round1(monkeypatch):
    """Caso real: antigo publicado 20/09 (kickoff 21/09 22:30Z, dentro da
    janela de dia=21/09); novo publicado 22/09 (kickoff 22/09 22:30Z) —
    published_at do novo cai DEPOIS do `fim` de dia=21/09 (22/09 03:00Z).
    `dia("2026-09-21")` nao pode listar nenhum dos dois (o antigo e
    remarcado; o novo pertence ao dia 22/09, fora da janela de kickoff).
    `dia("2026-09-22")` tem que listar o novo."""
    linhas = [
        _linha(_CRICIUMA_ANTIGO, "Over/Under", "Under 3.5", 0.6, 1.5, "SAFE",
              datetime(2026, 9, 20, 10, 0, tzinfo=_UTC), _K_ANTIGO,
              outcome=None, league_id="brasileirao-serie-b"),
        _linha(_CRICIUMA_NOVO, "Over/Under", "Under 3.5", 0.6, 1.5, "SAFE",
              datetime(2026, 9, 22, 9, 0, tzinfo=_UTC), _K_NOVO,
              outcome=None, league_id="brasileirao-serie-b"),
        _linha(_CUIABA_NAUTICO, "Corners", "Corners Over 4.5", 0.78, 1.3,
              "NEUTRO", datetime(2026, 9, 19, 9, 0, tzinfo=_UTC), _K_CUIABA,
              outcome=1, detail={"total_corners": 11}, league_id="brasileirao-serie-b"),
    ]
    monkeypatch.setattr(L, "_conn", lambda: _ConnHonraJanela(linhas))

    r21 = L.dia("2026-09-21")
    ids21 = {p["match_id"] for p in r21["picks"]}
    assert _CRICIUMA_ANTIGO not in ids21
    assert _CRICIUMA_NOVO not in ids21
    assert _CUIABA_NAUTICO in ids21          # controle continua

    r22 = L.dia("2026-09-22")
    ids22 = {p["match_id"] for p in r22["picks"]}
    assert _CRICIUMA_NOVO in ids22
