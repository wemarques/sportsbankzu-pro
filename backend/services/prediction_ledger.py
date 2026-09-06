"""Ledger imutavel de prognosticos (#218).

Por que existe
--------------
Os calibradores eram treinados a partir de `audit_results`, que e escrita com
`INSERT OR REPLACE` (audit_service.py:29). Cada reprocessamento pos-jogo
sobrescreve a linha, entao a tabela guarda o prognostico RECOMPUTADO depois do
resultado, nao o que foi publicado antes dele. Treinar calibrador nisso e
aprender com dados do futuro; foi o que o #200 fechou colocando o retreino
atras de um gate.

Este modulo e a fonte limpa que faltava. Duas regras, e so duas:

1. **So insere.** Nao existe UPDATE nem DELETE aqui. O desfecho do jogo entra
   em `ledger_outcomes`, uma segunda tabela, e as metricas saem de um JOIN.
   Uma linha do ledger, uma vez escrita, descreve para sempre o que o sistema
   sabia no momento em que publicou.
2. **Grava as ENTRADAS, nao so a saida.** Probabilidade sem os lambdas, sem o
   tamanho da amostra e sem a idade do dado registra o erro sem permitir
   explica-lo. Foi exatamente a lacuna que fez o #216 precisar de uma quarta
   coluna para descobrir que a isotonica estava inerte.

O que este modulo NAO faz
-------------------------
Nao decide nada. Nenhum caminho de publicacao le o ledger. Ele so observa, e
falha aberto: qualquer excecao vira log de debug e o pedido segue. Um site em
producao nao pode cair porque a telemetria caiu.

Desligado por padrao (`PREDICTION_LEDGER_ENABLED=0`).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

logger = logging.getLogger("sportsbankzu.ledger")

# Versao do conjunto de regras que produziu a linha. Sobe quando o calculo muda,
# para que o walk-forward do #221 nao misture geracoes do modelo.
LEDGER_MODEL_VERSION = os.getenv("LEDGER_MODEL_VERSION", "2026.09.03+230")

_MAX_LINHAS_POR_LOTE = 500


def ledger_habilitado() -> bool:
    return os.getenv("PREDICTION_LEDGER_ENABLED", "0").strip().lower() in (
        "1", "true", "yes", "on"
    )


def _conn():
    import psycopg2
    return psycopg2.connect(dsn_obrigatorio())


def dsn_obrigatorio() -> str:
    """#230-a - DSN vazio NAO pode cair no padrao da libpq.

    `psycopg2.connect("")` tenta localhost:5432 e falha com "Connection
    refused" — um erro sobre um servidor que ninguem configurou, no lugar do
    erro real: a variavel nao esta definida. Na Lambda, com a falha aberta do
    ledger, isso vira "ligado gravando nada" sem nenhuma pista no log.
    """
    dsn = (os.environ.get("DATABASE_URL") or "").strip()
    if not dsn:
        raise RuntimeError(
            "DATABASE_URL nao esta definida — defina no ambiente ou em .env; "
            "sem ela o psycopg2 tentaria localhost:5432, que nao e o banco"
        )
    return dsn


_DDL_LEDGER = """
CREATE TABLE IF NOT EXISTS prediction_ledger (
    id              BIGSERIAL PRIMARY KEY,
    published_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    match_id        TEXT NOT NULL,
    league_id       TEXT,
    kickoff_utc     TIMESTAMPTZ,
    market          TEXT NOT NULL,
    selection       TEXT,
    model_version   TEXT NOT NULL,
    raw_prob        DOUBLE PRECISION,
    iso_prob        DOUBLE PRECISION,
    calibrated_prob DOUBLE PRECISION,
    band_type       TEXT,
    book_odd        DOUBLE PRECISION,
    odd_source      TEXT,
    overround       DOUBLE PRECISION,
    ev              DOUBLE PRECISION,
    classification  TEXT,
    stake           DOUBLE PRECISION,
    reason_codes    JSONB,
    governance      JSONB,
    inputs          JSONB,
    payload_hash    TEXT NOT NULL,
    prob_mercado    DOUBLE PRECISION,
    mercado_metodo  TEXT,
    odd_par         DOUBLE PRECISION,
    margem_pp       DOUBLE PRECISION,
    frescor         TEXT,
    published_prob  DOUBLE PRECISION,
    prob_source     TEXT
);
"""

# #230 - a ancora de mercado gravada AO LADO da probabilidade publicada, no
# mesmo instante. E o que permite medir producao contra mercado nos mesmos
# picks (comparar_com_mercado.py --ledger) sem esperar nada alem do desfecho.
# Migracao idempotente para a tabela criada pelo #218.
_DDL_LEDGER_MIGRACAO = [
    "ALTER TABLE prediction_ledger ADD COLUMN IF NOT EXISTS prob_mercado DOUBLE PRECISION",
    "ALTER TABLE prediction_ledger ADD COLUMN IF NOT EXISTS mercado_metodo TEXT",
    "ALTER TABLE prediction_ledger ADD COLUMN IF NOT EXISTS odd_par DOUBLE PRECISION",
    "ALTER TABLE prediction_ledger ADD COLUMN IF NOT EXISTS margem_pp DOUBLE PRECISION",
    "ALTER TABLE prediction_ledger ADD COLUMN IF NOT EXISTS frescor TEXT",
    # #231 - o que foi PUBLICADO e de onde veio. `calibrated_prob` segue sendo
    # o modelo mesmo com PROB_SOURCE=mercado; sem esta separacao, ligar a flag
    # apagaria a medicao publicada x mercado que a autoriza.
    "ALTER TABLE prediction_ledger ADD COLUMN IF NOT EXISTS published_prob DOUBLE PRECISION",
    "ALTER TABLE prediction_ledger ADD COLUMN IF NOT EXISTS prob_source TEXT",
]

# A unicidade e por CONTEUDO, nao por (jogo, mercado). Republicar o mesmo pick
# identico nao cria linha nova (o /fixtures e chamado dezenas de vezes por dia);
# republicar com qualquer numero diferente cria. Assim o ledger fica com o
# historico das REVISOES do prognostico sem virar log de acesso.
_DDL_INDICES = [
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_ledger_conteudo "
    "ON prediction_ledger (match_id, market, payload_hash)",
    "CREATE INDEX IF NOT EXISTS ix_ledger_liga_mercado "
    "ON prediction_ledger (league_id, market, published_at)",
]

# #228 - o desfecho e por SELECAO, nao por tipo de mercado. `market` aqui e o
# tipo ("Over/Under", "Corners"), e um jogo tem Over 1.5, Over 2.5 e Under 2.5
# do mesmo tipo com desfechos diferentes. A versao anterior tinha
# UNIQUE (match_id, market): guardava UM desfecho por tipo e o JOIN do
# medir_inclinacao daria o mesmo resultado a todas as linhas do tipo — o ledger
# nunca poderia ter pontuado um pick corretamente. Ninguem notou porque nada
# escrevia em ledger_outcomes.
_DDL_OUTCOMES = """
CREATE TABLE IF NOT EXISTS ledger_outcomes (
    id            BIGSERIAL PRIMARY KEY,
    recorded_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    match_id      TEXT NOT NULL,
    market        TEXT NOT NULL,
    selection     TEXT NOT NULL DEFAULT '',
    outcome       INTEGER NOT NULL,
    detail        JSONB
);
"""

# Migracao idempotente para a tabela criada pela versao do #218: acrescenta a
# coluna, derruba a unicidade antiga (que impediria o segundo Over do mesmo
# jogo) e cria a nova. ADD COLUMN IF NOT EXISTS e DROP CONSTRAINT IF EXISTS
# existem no Postgres desde 9.6 / 9.0.
_DDL_OUTCOMES_MIGRACAO = [
    "ALTER TABLE ledger_outcomes ADD COLUMN IF NOT EXISTS selection TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE ledger_outcomes DROP CONSTRAINT IF EXISTS ledger_outcomes_match_id_market_key",
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_outcomes_selecao "
    "ON ledger_outcomes (match_id, market, selection)",
]


def garantir_tabelas() -> bool:
    """Cria as duas tabelas. Idempotente. Devolve False se nao deu (falha aberta)."""
    try:
        conn = _conn()
        cur = conn.cursor()
        cur.execute(_DDL_LEDGER)
        for ddl in _DDL_LEDGER_MIGRACAO:
            cur.execute(ddl)
        for ddl in _DDL_INDICES:
            cur.execute(ddl)
        cur.execute(_DDL_OUTCOMES)
        for ddl in _DDL_OUTCOMES_MIGRACAO:
            cur.execute(ddl)
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:                                   # noqa: BLE001
        logger.debug("[#218] garantir_tabelas: %s", e)
        return False


# #228 - ninguem chamava garantir_tabelas(). Com a flag ligada num banco novo,
# o primeiro INSERT falharia por tabela inexistente e a falha aberta engoliria
# o erro em DEBUG: o ledger ficaria "ligado" gravando nada, para sempre. Uma
# vez por processo (a Lambda reaproveita o container) e barato o bastante.
_tabelas_ok = False


def _garantir_uma_vez() -> None:
    global _tabelas_ok
    if not _tabelas_ok:
        _tabelas_ok = garantir_tabelas()


def _hash(linha: Dict[str, Any]) -> str:
    """Hash do conteudo que define 'e o mesmo prognostico'.

    De proposito NAO inclui published_at: o carimbo de tempo mudaria a cada
    chamada e o ledger viraria um log de requisicoes.
    """
    campos = (
        "match_id", "league_id", "market", "selection", "model_version",
        "raw_prob", "iso_prob", "calibrated_prob", "band_type",
        "book_odd", "odd_source", "overround", "ev", "classification",
        "stake", "reason_codes", "governance", "inputs",
        # #230: a odd do par e a prob de mercado entram — preco que mexeu e
        # informacao nova, e o ledger guarda REVISOES, nao acessos.
        "odd_par", "prob_mercado",
        # #231: trocar a fonte e uma revisao do prognostico.
        "published_prob", "prob_source",
    )
    bruto = json.dumps(
        {k: linha.get(k) for k in campos}, sort_keys=True, default=str,
    )
    return hashlib.sha256(bruto.encode("utf-8")).hexdigest()


def montar_linha(
    *,
    match_id: str,
    league_id: Optional[str],
    market: str,
    selection: Optional[str] = None,
    kickoff_utc: Optional[datetime] = None,
    raw_prob: Optional[float] = None,
    iso_prob: Optional[float] = None,
    calibrated_prob: Optional[float] = None,
    band_type: Optional[str] = None,
    book_odd: Optional[float] = None,
    odd_source: Optional[str] = None,
    overround: Optional[float] = None,
    ev: Optional[float] = None,
    classification: Optional[str] = None,
    stake: Optional[float] = None,
    reason_codes: Optional[Iterable[str]] = None,
    governance: Optional[Dict[str, Any]] = None,
    inputs: Optional[Dict[str, Any]] = None,
    prob_mercado: Optional[float] = None,
    mercado_metodo: Optional[str] = None,
    odd_par: Optional[float] = None,
    margem_pp: Optional[float] = None,
    frescor: Optional[str] = None,
    published_prob: Optional[float] = None,
    prob_source: Optional[str] = None,
) -> Dict[str, Any]:
    if published_prob is None:
        published_prob = calibrated_prob
    linha = {
        "match_id": str(match_id),
        "league_id": league_id,
        "kickoff_utc": kickoff_utc,
        "market": market,
        "selection": selection,
        "model_version": LEDGER_MODEL_VERSION,
        "raw_prob": raw_prob,
        "iso_prob": iso_prob,
        "calibrated_prob": calibrated_prob,
        "band_type": band_type,
        "book_odd": book_odd,
        "odd_source": odd_source,
        "overround": overround,
        "ev": ev,
        "classification": classification,
        "stake": stake,
        "reason_codes": sorted(str(c) for c in (reason_codes or [])),
        "governance": governance or {},
        "inputs": inputs or {},
        "prob_mercado": prob_mercado,
        "mercado_metodo": mercado_metodo,
        "odd_par": odd_par,
        "margem_pp": margem_pp,
        "frescor": frescor,
        "published_prob": published_prob,
        "prob_source": prob_source or "modelo",
    }
    linha["payload_hash"] = _hash(linha)
    return linha


_COLUNAS = (
    "match_id", "league_id", "kickoff_utc", "market", "selection",
    "model_version", "raw_prob", "iso_prob", "calibrated_prob", "band_type",
    "book_odd", "odd_source", "overround", "ev", "classification", "stake",
    "reason_codes", "governance", "inputs", "payload_hash",
    "prob_mercado", "mercado_metodo", "odd_par", "margem_pp", "frescor",
    "published_prob", "prob_source",
)


# ── #230 - a ancora de mercado ───────────────────────────────────────────
# Nomes REAIS do dicionario `odds` do record, depois do enriquecimento #120
# (routes/fixtures.py): gols `over25`/`under25` (0.5–5.5), BTTS `bttsYes`/
# `bttsNo`, escanteios `cornersOver95`/`cornersUnder95` (4.5–12.5), cartoes
# `cards_over_3.5`/`cards_under_3.5`, 1X2 `home`/`draw`/`away`. Medidos, nao
# presumidos — a licao do #226-b.
def _linha_do_rotulo(selection: str) -> Optional[str]:
    import re
    m = re.search(r"(\d+\.5)", selection or "")
    return m.group(1) if m else None


def par_de_odds(market: str, selection: str, odds: Optional[Dict[str, Any]]
                ) -> Tuple[Optional[float], Optional[float]]:
    """(odd da propria selecao, odd da perna oposta) a partir do `odds` do record."""
    odds = odds or {}

    def _v(k: Optional[str]) -> Optional[float]:
        if not k:
            return None
        try:
            v = float(odds.get(k) or 0)
        except (TypeError, ValueError):
            return None
        return v if v > 1.0 else None

    m = (market or "").strip()
    s = (selection or "").strip()
    sl = s.lower()
    linha = _linha_do_rotulo(s)
    if m == "Over/Under" and linha:
        sfx = linha.replace(".", "")
        a, b = (f"over{sfx}", f"under{sfx}") if sl.startswith("over") else (f"under{sfx}", f"over{sfx}")
        return _v(a), _v(b)
    if m == "BTTS":
        return (_v("bttsYes"), _v("bttsNo")) if "yes" in sl else (_v("bttsNo"), _v("bttsYes"))
    if m == "Corners" and linha:
        sfx = linha.replace(".", "")
        over, under = f"cornersOver{sfx}", f"cornersUnder{sfx}"
        return (_v(over), _v(under)) if "over" in sl else (_v(under), _v(over))
    if m == "Cards" and linha:
        over, under = f"cards_over_{linha}", f"cards_under_{linha}"
        return (_v(over), _v(under)) if "over" in sl else (_v(under), _v(over))
    if m == "1X2":
        chave = {"home": "home", "draw": "draw", "away": "away"}.get(sl)
        return _v(chave), None          # tres pernas: ver _trio_1x2 / prob_mercado_do_pick
    if m == "Double Chance":
        chave = {"dc 1x": "dc_1x", "dc 12": "dc_12", "dc x2": "dc_x2"}.get(sl)
        return _v(chave), None
    return None, None


_PERNA_1X2 = {"home": 0, "draw": 1, "away": 2}
_PERNAS_DC = {"dc 1x": (0, 1), "dc 12": (0, 2), "dc x2": (1, 2)}


def _trio_1x2(odds: Optional[Dict[str, Any]]) -> Optional[List[float]]:
    """(home, draw, away) quando as tres existem e sao preco (> 1.0)."""
    odds = odds or {}
    trio = []
    for k in ("home", "draw", "away"):
        try:
            v = float(odds.get(k) or 0)
        except (TypeError, ValueError):
            return None
        if v <= 1.0:
            return None
        trio.append(v)
    return trio


def prob_mercado_do_pick(market: str, selection: str, odds: Optional[Dict[str, Any]]
                         ) -> Dict[str, Any]:
    """Probabilidade justa do mercado para a selecao, com o metodo e o frescor.

    devig      — par over/under existe: Shin (#219), margem medida e frescor
                 pelo detector do #219 (`odds_utilizaveis`).
    implicita  — so a propria perna: 1/odd, margem inteira embutida.
    sem_odd    — nada utilizavel.
    """
    propria, par = par_de_odds(market, selection, odds)
    out: Dict[str, Any] = {"prob_mercado": None, "mercado_metodo": "sem_odd",
                           "odd_par": par, "margem_pp": None, "frescor": None}

    # #230-e - 1X2 e Dupla Chance saem do de-vig de TRES pernas (Shin
    # generaliza). A primeira versao deixava 1X2 "implicita" (margem inteira
    # dentro) e nao dava ancora nenhuma a DC: 831 linhas de DC sem
    # prob_mercado e 222 de Draw carregando ~5,6 pp de margem contra o
    # mercado. Medido na tabela de cobertura do #230-d.
    m = (market or "").strip()
    sl = (selection or "").strip().lower()
    if m in ("1X2", "Double Chance"):
        trio = _trio_1x2(odds)
        if trio:
            try:
                from backend.services.devig import devig, odds_utilizaveis
                justas = devig(trio)
                ok, margem, motivo = odds_utilizaveis(trio)
                if justas and len(justas) == 3:
                    if m == "1X2" and sl in _PERNA_1X2:
                        pj = justas[_PERNA_1X2[sl]]
                    elif m == "Double Chance" and sl in _PERNAS_DC:
                        i, j = _PERNAS_DC[sl]
                        pj = justas[i] + justas[j]
                    else:
                        pj = None
                    if pj is not None and 0.0 < pj < 1.0:
                        out.update({"prob_mercado": round(pj, 6), "mercado_metodo": "devig3",
                                    "margem_pp": margem, "frescor": motivo})
                        return out
            except Exception as e:                           # noqa: BLE001
                logger.debug("[#230] devig 3 pernas falhou: %s", e)
        # sem o trio: a propria odd (1X2 ou dc_*), com a margem dentro
        if propria is not None:
            out.update({"prob_mercado": round(1.0 / propria, 6), "mercado_metodo": "implicita"})
        return out

    if propria is None:
        return out
    if par is not None:
        try:
            from backend.services.devig import odds_utilizaveis, prob_justa
            ok, margem, motivo = odds_utilizaveis([propria, par])
            p = prob_justa([propria, par], 0)
            if p is not None and 0.0 < p < 1.0:
                out.update({"prob_mercado": round(p, 6), "mercado_metodo": "devig",
                            "margem_pp": margem, "frescor": motivo})
                return out
        except Exception as e:                               # noqa: BLE001
            logger.debug("[#230] devig falhou: %s", e)
    out.update({"prob_mercado": round(1.0 / propria, 6), "mercado_metodo": "implicita"})
    return out


def registrar(linhas: List[Dict[str, Any]]) -> int:
    """Anexa linhas ao ledger. Devolve quantas entraram de fato.

    Falha aberta em qualquer erro — o pedido do usuario nunca pode quebrar
    porque a telemetria quebrou.
    """
    if not linhas or not ledger_habilitado():
        return 0
    if len(linhas) > _MAX_LINHAS_POR_LOTE:
        logger.warning("[#218] lote de %d linhas truncado em %d",
                       len(linhas), _MAX_LINHAS_POR_LOTE)
        linhas = linhas[:_MAX_LINHAS_POR_LOTE]
    try:
        from psycopg2.extras import Json, execute_values

        _garantir_uma_vez()
        valores = [
            tuple(
                Json(l.get(c)) if c in ("reason_codes", "governance", "inputs")
                else l.get(c)
                for c in _COLUNAS
            )
            for l in linhas
        ]
        conn = _conn()
        cur = conn.cursor()
        execute_values(
            cur,
            f"INSERT INTO prediction_ledger ({', '.join(_COLUNAS)}) VALUES %s "
            f"ON CONFLICT (match_id, market, payload_hash) DO NOTHING",
            valores,
        )
        gravadas = cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
        conn.commit()
        cur.close()
        conn.close()
        logger.info("[#218] ledger: %d de %d linha(s) novas", gravadas, len(linhas))
        return gravadas
    except Exception as e:                                   # noqa: BLE001
        logger.debug("[#218] registrar falhou (falha aberta): %s", e)
        return 0


def registrar_desfecho(match_id: str, market: str, outcome: int,
                       detail: Optional[Dict[str, Any]] = None,
                       selection: str = "") -> bool:
    """Anexa o desfecho real de UMA selecao. Tabela separada, nunca toca o ledger."""
    if not ledger_habilitado():
        return False
    try:
        from psycopg2.extras import Json
        _garantir_uma_vez()
        conn = _conn()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO ledger_outcomes (match_id, market, selection, outcome, detail) "
            "VALUES (%s, %s, %s, %s, %s) "
            "ON CONFLICT (match_id, market, selection) DO NOTHING",
            (str(match_id), market, selection or "", int(outcome), Json(detail or {})),
        )
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:                                   # noqa: BLE001
        logger.debug("[#218] registrar_desfecho falhou: %s", e)
        return False


# #228 - o rotulo que o avaliador deterministico entende, montado a partir do
# par (market, selection) que o ledger grava. O avaliador e a unica verdade
# sobre "acertou ou errou" (checklist #006, item 7); aqui so se traduz.
#
#   Over/Under  "Over 2.5"          -> "Over 2.5"           (acha 2.5 + OVER)
#   Cards       "Over 3.5"          -> "Cartoes Over 3.5"   (sem prefixo viraria GOLS)
#   Corners     "Corners Over 9.5"  -> como esta            (acha CORNER)
#   1X2         "Home"/"Draw"/"Away"-> "1"/"X"/"2"          ("HOME" sozinho nao casa)
#   BTTS, DC    como estao
_1X2 = {"home": "1", "draw": "X", "away": "2", "1": "1", "x": "X", "2": "2"}


def rotulo_para_avaliador(market: str, selection: str) -> str:
    m = (market or "").strip()
    s = (selection or "").strip()
    if m == "1X2":
        return _1X2.get(s.lower(), s)
    if m == "Cards" and not s.lower().startswith(("cart", "card")):
        return f"Cartoes {s}"
    return s


def desfecho_do_pick(market: str, selection: str, actual_result: Dict[str, Any]) -> int:
    from backend.routes.ai_analysis import _evaluate_pick_deterministic
    return int(_evaluate_pick_deterministic(
        {"mercado": rotulo_para_avaliador(market, selection)}, actual_result))


def registrar_desfechos_do_jogo(match_id: str, actual_result: Dict[str, Any]) -> int:
    """Pontua TODAS as selecoes que o ledger tem para este jogo.

    Le do proprio ledger quais (market, selection) foram publicados — nao
    enumera mercados possiveis, porque o ledger e a lista do que existe. Chamado
    pelo batch audit depois de montar o `actual_result` (a unica fonte de
    placar/escanteios/cartoes que o sistema ja valida). Falha aberta.
    """
    if not ledger_habilitado():
        return 0
    try:
        _garantir_uma_vez()
        conn = _conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT DISTINCT market, COALESCE(selection, '') FROM prediction_ledger "
            "WHERE match_id = %s",
            (str(match_id),),
        )
        pares = cur.fetchall()
        cur.close()
        conn.close()
    except Exception as e:                                   # noqa: BLE001
        logger.debug("[#228] leitura das selecoes falhou: %s", e)
        return 0

    gravados = 0
    for market, selection in pares:
        outcome = desfecho_do_pick(market, selection, actual_result)
        if registrar_desfecho(match_id, market, outcome,
                              detail=actual_result, selection=selection):
            gravados += 1
    if pares:
        logger.info("[#228] desfechos: %d/%d selecoes do jogo %s",
                    gravados, len(pares), match_id)
    return gravados


def _prob_do_modelo(m) -> Optional[float]:
    """#231 - a probabilidade do modelo, esteja a flag ligada ou nao."""
    modelo = getattr(m, "model_probability", None)
    if modelo is not None and getattr(m, "prob_source", None) is not None:
        return modelo
    return getattr(m, "calibrated_probability", None)


def linhas_do_bundle(bundle, match_data: Optional[Dict[str, Any]] = None,
                     stats: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Traduz um MarketBundle ja classificado em linhas do ledger.

    As ENTRADAS que acompanham cada linha sao as que explicam o numero:
    os dois lambdas, o lambda de cartoes e o de escanteios, o tamanho da
    amostra de cada lado e a idade do dado. Sem elas o ledger registra o erro
    sem permitir diagnostica-lo.
    """
    stats = stats or {}
    match_data = match_data or {}
    # #223 - MEDIDO contra um record real: 6 destas 10 entradas vinham NULAS.
    # O ledger existe para "registrar o erro permitindo explica-lo", e estava
    # gravando `None` justamente nas entradas que explicam. As chaves lidas nao
    # existiam com aquele nome:
    #
    #   homeMatchesPlayed/awayMatchesPlayed -> matchesPlayed_home/_away
    #   leagueMatchesCompleted              -> vive em league_stats, nao em stats
    #   cardsLambda / expectedTotalCorners  -> nao existem em lugar nenhum;
    #                                          gravamos os componentes que existem
    #   dataAgeHours                        -> nao existe; lacuna real, ver abaixo
    #
    # Foi a terceira vez que o mesmo defeito passou — desta vez DENTRO do patch
    # escrito para corrigir essa classe de defeito. Por isso o contrato do #223
    # e um teste, nao um paragrafo.
    _ls = (match_data.get("league_stats") or {}) if isinstance(match_data, dict) else {}
    entradas_comuns = {
        "lambda_home": stats.get("lambdaHome"),
        "lambda_away": stats.get("lambdaAway"),
        "lambda_total": stats.get("lambdaTotal"),
        # Nao ha lambda de cartoes nem total esperado de escanteios no record;
        # o que existe sao os componentes de onde eles sairiam. Gravar os
        # componentes e verdadeiro; gravar um None chamado "cards_lambda" seria
        # registrar uma ausencia com nome de medida.
        "cards_home_pm": stats.get("homeCardsPerMatch"),
        "cards_away_pm": stats.get("awayCardsPerMatch"),
        "cards_league_avg": stats.get("leagueAvgCards"),
        "corners_home_pm": stats.get("homeCornersPerMatch"),
        "corners_away_pm": stats.get("awayCornersPerMatch"),
        "corners_league_avg": stats.get("leagueAvgCorners"),
        "home_matches": stats.get("matchesPlayed_home"),
        "away_matches": stats.get("matchesPlayed_away"),
        "league_matches_completed": _ls.get("matches_completed"),
        # LACUNA CONHECIDA: a idade do dado nao e registrada em lugar nenhum do
        # record. Fica fora do ledger ate existir de verdade — um campo sempre
        # nulo e pior que campo ausente, porque parece medicao.
        "chaos_detected": stats.get("chaosDetected"),
        "data_quality_score": getattr(bundle, "data_quality_score", None),
    }
    odds = (match_data.get("odds") or {}) if isinstance(match_data, dict) else {}
    linhas: List[Dict[str, Any]] = []
    for m in getattr(bundle, "markets", []) or []:
        ancora = prob_mercado_do_pick(getattr(m, "market_type", "") or "",
                                      getattr(m, "selection", "") or "", odds)
        gov = {}
        if getattr(m, "corner_governance", None):
            gov["corner"] = m.corner_governance
        if getattr(m, "corner_veto", None):
            gov["veto"] = m.corner_veto
        linhas.append(montar_linha(
            match_id=getattr(bundle, "match_id", "") or match_data.get("id", ""),
            league_id=getattr(bundle, "league_id", None),
            market=getattr(m, "market_type", "") or "",
            selection=getattr(m, "selection", None),
            raw_prob=getattr(m, "raw_probability", None),
            iso_prob=getattr(m, "iso_probability", None),
            # #231: com PROB_SOURCE=mercado a `calibrated_probability` do
            # MarketOutput e a ancora; o modelo esta em `model_probability`.
            # O ledger grava o MODELO em calibrated_prob (a serie que o gate
            # #230 mede) e a publicada em published_prob.
            calibrated_prob=_prob_do_modelo(m),
            published_prob=getattr(m, "calibrated_probability", None),
            prob_source=getattr(m, "prob_source", None),
            band_type=getattr(m, "deflation_band_type", None),
            book_odd=getattr(m, "book_odd", None),
            ev=getattr(m, "ev", None),
            classification=getattr(getattr(m, "classification", None), "value", None),
            reason_codes=[getattr(rc, "value", str(rc)) for rc in (getattr(m, "reason_codes", []) or [])],
            governance=gov,
            inputs=entradas_comuns,
            **ancora,
        ))
    return linhas
