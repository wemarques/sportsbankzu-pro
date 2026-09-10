# -*- coding: utf-8 -*-
"""Unico modulo do pacote que toca o banco.

FONTE PROIBIDA: a tabela de auditoria recomputada pos-jogo (#200). A regra
#244 proibe usa-la como fonte de calibracao. Nao ha caminho de codigo para
ela aqui, e um teste guarda isso (inclusive contra o nome dela em comentario).
"""
import logging
import os
from contextlib import contextmanager
from typing import Any, Dict, List, NamedTuple, Optional

from backend.modeling.calibragem.curva import (
    base_da_composicao, familia_do_mercado,
)
from backend.modeling.calibragem.limiares import CAMPOS as CAMPOS_LIMIAR

logger = logging.getLogger("sportsbankzu.calibragem.repositorio")

DDL = """
CREATE TABLE IF NOT EXISTS calibragem_versoes (
    id                  BIGSERIAL PRIMARY KEY,
    criada_em           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    familia             TEXT NOT NULL,
    liga                TEXT NOT NULL DEFAULT '',
    versao              INTEGER NOT NULL,
    a                   DOUBLE PRECISION,
    b                   DOUBLE PRECISION,
    n_jogos             INTEGER NOT NULL DEFAULT 0,
    brier_validacao     DOUBLE PRECISION,
    origem              TEXT,
    status              TEXT NOT NULL,
    fator_encurtamento  DOUBLE PRECISION,
    motivo              TEXT,
    safe_ev             DOUBLE PRECISION,
    neutro_ev           DOUBLE PRECISION,
    safe_edge           DOUBLE PRECISION,
    neutro_edge         DOUBLE PRECISION
);
CREATE INDEX IF NOT EXISTS idx_calibragem_celula
    ON calibragem_versoes (familia, liga, versao DESC);
"""

# #248, I7: o indice de `vigente` tem de ser UNICO. Sem isso, duas linhas
# `vigente` para a mesma celula sao possiveis, e `carregar_vigentes` (que
# monta um dict por (familia, liga)) escolheria uma das duas pela ordem de
# retorno do Postgres — silenciosamente, e diferente a cada consulta.
#
# Migracao: o indice antigo NAO era unico e tinha este nome. `CREATE UNIQUE
# INDEX IF NOT EXISTS` com o mesmo nome seria um no-op sobre o indice antigo,
# entao ele e derrubado e o novo nasce com nome proprio — assim um banco a
# meio caminho nunca fica com os dois.
DROP_INDICE_VIGENTE_ANTIGO = "DROP INDEX IF EXISTS idx_calibragem_vigente"
DDL_INDICE_VIGENTE_UNICO = """
CREATE UNIQUE INDEX IF NOT EXISTS idx_calibragem_vigente_unico
    ON calibragem_versoes (familia, liga) WHERE status = 'vigente'
"""

SQL_VIGENTES_DUPLICADAS = """
    SELECT familia, liga, COUNT(*) FROM calibragem_versoes
     WHERE status = 'vigente'
     GROUP BY familia, liga HAVING COUNT(*) > 1
"""


class Pick(NamedTuple):
    match_id: str
    familia: str
    liga: str
    p_raw: float
    y: int
    odd: Optional[float] = None
    selecao: str = ""
    # Quando a linha foi PUBLICADA (`prediction_ledger.published_at`). Existe
    # para a janela de reversao (#248, I1): uma versao so pode ser julgada
    # pelos jogos que ela SERVIU, ou seja, os publicados depois de ela virar
    # vigente. Sem este campo a janela era in-sample -- a vigente era avaliada
    # sobre os mesmos jogos em que foi ajustada, um MLE quase sempre ganha no
    # proprio treino, e a acao era sempre `manter`.
    publicado_em: Optional[Any] = None
    # O que a VERSAO 0 publicaria para este pick: `legado(p_raw)`. E o
    # REGRESSOR da camada desde a composicao (#248, C1) -- o estimador ajusta
    # `(a, b)` sobre `logit(p_legado)`, a governanca mede o Brier sobre
    # `aplicar(p_legado, a, b)`, e a re-derivacao de limiares conta volume
    # sobre a mesma entrada. `None` e defeito de construcao, nunca fallback:
    # `curva.entrada_da_curva` levanta em vez de cair em `p_raw`.
    #
    # Fica por ultimo, com default, para nao quebrar a construcao posicional
    # de cinco argumentos que `test_03` ancora.
    p_legado: Optional[float] = None


# #248, I6: `_calibrar_com_detalhe` alcanca este modulo pelo caminho de
# `/fixtures`, que ja namora o teto de 60s da Lambda. Sem `connect_timeout` o
# psycopg2 herda o do SO — na pratica, minutos — e uma RDS inalcancavel vira
# timeout da funcao inteira em vez de um erro de 5s com fallback marcado.
_CONNECT_TIMEOUT_S = 5


def _conn():
    import psycopg2
    return psycopg2.connect(os.environ["DATABASE_URL"],
                            connect_timeout=_CONNECT_TIMEOUT_S)


@contextmanager
def _conexao():
    """`with conn` do psycopg2 encerra a TRANSACAO, nao a conexao.

    Todo uso do modulo passava por `with _conn() as c` e deixava o socket
    aberto ate o coletor de lixo passar — numa Lambda que fica viva entre
    invocacoes, isso acumula. Fechar e explicito, como em
    `prediction_ledger.py` e `brier_service.py` (#248, I6).
    """
    c = _conn()
    try:
        with c:
            yield c
    finally:
        c.close()


def garantir_tabela() -> bool:
    try:
        with _conexao() as c, c.cursor() as cur:
            cur.execute(DDL)
    except Exception as e:                                   # noqa: BLE001
        logger.warning("[calibragem] tabela nao garantida: %s", e)
        return False
    # Transacao SEPARADA de proposito: se o indice unico falhar (banco com
    # duplicatas anteriores a esta versao), o Postgres aborta a transacao
    # inteira, e a criacao da tabela nao pode cair junto.
    garantir_indice_vigente_unico()
    return True


def garantir_indice_vigente_unico() -> bool:
    """Troca o indice de `vigente` por um UNIQUE. Nunca derruba o ciclo.

    Um banco que ja tenha duas linhas `vigente` para a mesma celula recusa o
    `CREATE UNIQUE INDEX`. Isso NAO pode quebrar `garantir_tabela`: a falha e
    registrada com as celulas culpadas nomeadas, e o ciclo segue sem a
    garantia — que e exatamente o estado de antes. Consertar as duplicatas e
    acao humana; esconder que elas existem seria o defeito.
    """
    try:
        with _conexao() as c, c.cursor() as cur:
            cur.execute(DROP_INDICE_VIGENTE_ANTIGO)
            cur.execute(DDL_INDICE_VIGENTE_UNICO)
        return True
    except Exception as e:                                   # noqa: BLE001
        logger.error(
            "[calibragem] indice UNIQUE de `vigente` NAO criado: %s — o banco "
            "provavelmente ja tem celulas com duas linhas vigentes; "
            "carregar_vigentes escolhe uma delas sem criterio ate isso ser "
            "resolvido a mao", e)
        _logar_vigentes_duplicadas()
        return False


def _logar_vigentes_duplicadas() -> None:
    """Nomeia as celulas culpadas. Melhor esforco: se nem isso der, silencia
    — o erro que importa ja foi registrado por quem chamou."""
    try:
        with _conexao() as c, c.cursor() as cur:
            cur.execute(SQL_VIGENTES_DUPLICADAS)
            duplicadas = cur.fetchall()
        if duplicadas:
            logger.error("[calibragem] celulas com vigente duplicada: %s",
                         [(f, l, n) for f, l, n in duplicadas])
    except Exception as e:                                   # noqa: BLE001
        logger.warning("[calibragem] nao foi possivel listar duplicatas: %s", e)


def classificar_familia(market: str, selection: str) -> Optional[str]:
    """Familia do pick a partir de `market` + `selection` do ledger, pura e
    testavel sem banco.

    `market` no ledger ja E o nome da familia na maioria dos casos
    ("Corners", "Cards", "BTTS", "1X2") e resolve sozinho. "Over/Under" (sem
    espaco antes de "under") e "Double Chance" (em ingles) nao casam nenhum
    token so com o `market` e so resolvem pelo rotulo "market selection"
    concatenado, que casa "over "/"dc ". Retorna None (nao levanta) quando
    nada resolve, para o chamador decidir o que fazer com o descarte.

    Achado da rodada 1 de correcao: casar so o rotulo concatenado deixava
    "over " de "Corners Over 7.5" vencer antes de "corners" -- escanteios e
    cartoes viravam Over/Under silenciosamente e envenenavam a curva de
    gols. Resolver primeiro pelo `market` isolado fecha essa rota.
    """
    try:
        return familia_do_mercado(market)
    except ValueError:
        pass
    rotulo = f"{market} {selection}".strip()
    try:
        return familia_do_mercado(rotulo)
    except ValueError:
        return None


# O ledger NAO grava o regime (`prediction_ledger` nao tem a coluna, e
# `inputs` tampouco carrega a chave -- verificado). "NORMAL" e o regime
# padrao e o unico que o pacote pode assumir sem inventar dado. Efeito
# medido do que se perde: `regime` so entra em `calibrate_prob` como a
# SEGUNDA chave da cadeia de fallback (`market|""|regime`), consultada
# apenas quando nao existe modelo `market|liga|""`; a deflacao por banda,
# por liga e o ramo meia/inteira nao olham o regime. LACUNA REGISTRADA:
# picks servidos em HIPER-OFENSIVA sao reconstruidos como NORMAL aqui.
REGIME_DA_AMOSTRA = "NORMAL"


def rotulo_do_legado(market: str, selection: str) -> Optional[str]:
    """O rotulo de EXIBICAO que `calibrar_legado` espera, a partir do par
    (market, selection) que o ledger grava em ingles.

    Isto NAO e cosmetico e nao pode ser aproximado. O rotulo decide duas
    coisas dentro da versao 0:

      1. o MODELO ISOTONICO (`calibrator.calibrate_prob` procura o pickle
         por `market|liga`, depois `market|regime`, depois `market|global`,
         depois `familia|...`) -- rotulo errado, modelo errado;
      2. o RAMO DA BANDA (`market.upper() == "BTTS"` -> meia-btts;
         `market.lower().startswith(("over ","under "))` -> meia; qualquer
         outro -> banda INTEIRA). Um escanteio que chegasse como
         "Corners Over 9.5" comeca com "corners", cai no ramo `else` e
         acerta a banda por acidente; um cartao que chegasse como
         "Over 3.5" (a forma CRUA do ledger) cairia na meia banda -- a
         familia inteira sairia da banda errada, e o `p_legado` iria com ela.

    A tabela abaixo REPRODUZ o que `backend/services/ev_classification.py`
    passa a `_calibrar_com_detalhe` em producao, lido linha a linha do
    proprio arquivo (blocos de 1X2, O/U, BTTS, DC, escanteios e cartoes) e
    conferido contra os 44 pares (market, selection) que o
    `prediction_ledger` de fato guarda hoje:

        ledger                                -> rotulo do legado
        1X2            | Home/Draw/Away        -> 1X2_home / 1X2_draw / 1X2_away
        Over/Under     | Over 2.5              -> Over 2.5            (identico)
        BTTS           | BTTS Yes              -> BTTS
        Double Chance  | DC 1X / DC 12 / DC X2 -> Double Chance 1X/12/X2
        Corners        | Corners Over 9.5      -> Escanteios Over 9.5
        Cards          | Over 3.5              -> Cartoes Over 3.5

    `None` (nao um palpite) quando o `market` nao esta na tabela: sem o
    rotulo certo nao ha `p_legado` correto, e treinar sobre um `p_legado`
    da banda errada e pior que descartar o pick. O chamador loga e descarta.
    """
    m = (market or "").strip()
    s = (selection or "").strip()
    if not s and m != "BTTS":
        return None
    if m == "1X2":
        return f"1X2_{s.lower()}"
    if m == "Over/Under":
        return s
    if m == "BTTS":
        return "BTTS"
    if m == "Double Chance":
        # "DC 1X" -> "Double Chance 1X". Ja veio em forma longa: passa reto.
        if s.lower().startswith("dc "):
            return f"Double Chance {s[3:].strip()}"
        return s if s.lower().startswith("double chance") else None
    if m == "Corners":
        # "Corners Over 9.5" -> "Escanteios Over 9.5".
        if s.lower().startswith("corners "):
            return f"Escanteios {s[len('Corners '):].strip()}"
        return s if s.lower().startswith("escanteios") else f"Escanteios {s}"
    if m == "Cards":
        # "Over 3.5" -> "Cartoes Over 3.5". Mesmo tratamento que
        # `prediction_ledger.rotulo_para_avaliador` da ao avaliador.
        if s.lower().startswith(("cart", "card")):
            return s
        return f"Cartoes {s}"
    return None


def _aquecer_correcoes_por_liga(ligas) -> int:
    """Uma consulta por LIGA, antes do laco, em vez de uma por PICK dentro dele.

    `calibrar_legado` chama `poisson_matrix._get_league_deflation(liga)`, que
    chama `lambda_calculator.get_lambda_corrections(liga)` -- uma consulta ao
    banco por chamada. Com 5.484 picks isso seriam 1.237 consultas (uma por
    pick da familia Over/Under, o unico ramo do legado que consulta).

    O QUE ISTO COMPRA, MEDIDO -- e a resposta e menos do que parece, entao
    fica escrito aqui e no relatorio em vez de virar folclore:

        configuracao                          sem aquecer   aquecendo
        LAMBDA_CORRECTIONS_TTL_S=300 (padrao)      20            20
        LAMBDA_CORRECTIONS_TTL_S=0 (desligado)  1.237         1.257

    Quem transforma 1.237 em 20 e o cache por liga do #231-a, nao este
    aquecimento: no padrao, a PRIMEIRA chamada de cada liga ja popula o
    cache e as demais sao acerto. E com o cache DESLIGADO o aquecimento so
    somaria 20 consultas inuteis -- por isso ele nao roda nesse caso.

    Fica no codigo porque torna a invariante EXPLICITA e testavel ("uma
    consulta por liga, nunca uma por pick"): sem ela, um dia em que o cache
    do #231-a mude de forma, a regressao volta a 1.237 sem sintoma. Com ela,
    o teste que conta consultas falha.

    Devolve quantas ligas foram aquecidas.
    """
    from backend.modeling.lambda_calculator import _ttl_correcoes, get_lambda_corrections
    if _ttl_correcoes() <= 0:
        # Cache desligado pelo operador (#231-a). Aquecer aqui so somaria
        # consultas -- e reimplementar o cache que ele mandou desligar seria
        # exatamente o tipo de comportamento invisivel que a chave existe
        # para evitar.
        return 0
    aquecidas = 0
    for liga in sorted({l for l in ligas if l}):
        try:
            get_lambda_corrections(liga)
            aquecidas += 1
        except Exception as e:                               # noqa: BLE001
            logger.warning("[calibragem] correcoes de '%s' nao aquecidas: %s",
                           liga, e)
    return aquecidas


@contextmanager
def _trace_do_legado_silenciado():
    """Cala o GOLS-TRACE/CALIB-TRACE durante a reconstrucao de `p_legado`.

    `calibrar_legado` emite uma linha INFO por chamada, no logger
    `sportsbankzu.ev_classification`. Reconstruir 5.000 picks por ciclo
    despejaria 5.000 linhas com o prefixo que o `REGRAS_ATIVAS` documenta
    para grep de PRODUCAO -- e nenhuma delas corresponde a um pick
    publicado. O rastro deixaria de servir para o que existe.

    Escopo minimo e reversivel: o nivel volta ao que era no `finally`.
    """
    log_legado = logging.getLogger("sportsbankzu.ev_classification")
    anterior = log_legado.level
    log_legado.setLevel(logging.WARNING)
    try:
        yield
    finally:
        log_legado.setLevel(anterior)


def escolher_ultima_geracao(linhas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Uma linha por (match_id, market, selection): a ultima ANTES do kickoff.

    O ledger e append-only com varias geracoes por jogo. A que vale e a que o
    operador viu por ultimo, e ela tem de ser anterior ao apito — geracao
    posterior ao kickoff nao e prognostico, e o defeito do #200.
    """
    melhor: Dict[tuple, Dict[str, Any]] = {}
    for ln in linhas:
        kickoff = ln.get("kickoff_utc")
        publicado = ln.get("published_at")
        if kickoff is not None and publicado is not None and publicado >= kickoff:
            continue
        chave = (ln.get("match_id"), ln.get("market"), ln.get("selection"))
        atual = melhor.get(chave)
        if atual is None or (publicado is not None
                             and atual.get("published_at") is not None
                             and publicado > atual["published_at"]):
            melhor[chave] = ln
    return list(melhor.values())


def carregar_amostra(desde: Optional[str] = None) -> List[Pick]:
    """Picks publicados PRE-JOGO com desfecho, prontos para o estimador."""
    sql = """
        SELECT l.match_id, l.league_id, l.market, l.selection,
               l.raw_prob, l.published_at, l.kickoff_utc, l.book_odd,
               o.outcome
          FROM prediction_ledger l
          JOIN ledger_outcomes o
            ON o.match_id  = l.match_id
           AND o.market    = l.market
           AND o.selection = l.selection
         WHERE l.raw_prob IS NOT NULL
           AND o.outcome IS NOT NULL
    """
    params: list = []
    if desde:
        sql += " AND l.published_at >= %s"
        params.append(desde)

    with _conexao() as c, c.cursor() as cur:
        cur.execute(sql, params)
        brutas = [
            {"match_id": r[0], "league_id": r[1] or "", "market": r[2],
             "selection": r[3], "raw_prob": float(r[4]), "published_at": r[5],
             "kickoff_utc": r[6],
             "book_odd": float(r[7]) if r[7] is not None else None,
             "outcome": r[8]}
            for r in cur.fetchall()
        ]

    # Primeira passada: familia e rotulo do legado, SEM tocar o legado ainda.
    # A separacao existe para extrair as ligas distintas antes do laco caro e
    # aquecer o cache de correcoes uma vez por liga (ver
    # `_aquecer_correcoes_por_liga`).
    preparadas = []
    sem_familia = sem_rotulo = 0
    for ln in escolher_ultima_geracao(brutas):
        familia = classificar_familia(ln["market"], ln["selection"])
        if familia is None:
            sem_familia += 1
            continue
        rotulo = rotulo_do_legado(ln["market"], ln["selection"])
        if rotulo is None:
            sem_rotulo += 1
            continue
        preparadas.append((ln, familia, rotulo))

    _aquecer_correcoes_por_liga(ln["league_id"] for ln, _, _ in preparadas)

    saida: List[Pick] = []
    with _trace_do_legado_silenciado():
        for ln, familia, rotulo in preparadas:
            p_legado = base_da_composicao(ln["raw_prob"], rotulo,
                                          ln["league_id"], REGIME_DA_AMOSTRA)
            saida.append(Pick(ln["match_id"], familia, ln["league_id"],
                              ln["raw_prob"], int(bool(int(ln["outcome"]))),
                              ln["book_odd"], ln["selection"],
                              ln["published_at"], p_legado))
    if sem_familia:
        logger.warning("[calibragem] %d picks sem familia reconhecida", sem_familia)
    if sem_rotulo:
        logger.warning(
            "[calibragem] %d picks com familia reconhecida mas SEM rotulo do "
            "legado -- descartados. Um `market` novo entrou no ledger e nao "
            "esta em `rotulo_do_legado`; sem o rotulo certo o `p_legado` sai "
            "da banda errada e treinar sobre ele e pior que descartar.",
            sem_rotulo)
    return saida


STATUS_VALIDOS = {
    "vigente", "adotada", "encurtada", "rejeitada", "abaixo_do_piso",
    "inalterada", "revertida", "congelada",
}


def montar_linha_auditoria(familia: str, liga: str, versao: int,
                           resultado: dict, n_jogos: int, origem: str,
                           brier, limiares: Optional[dict] = None) -> Dict[str, Any]:
    """Uma linha por celula, em TODO ciclo — inclusive quando nada mudou.

    `limiares`, quando presente, carrega as quatro chaves `safe_ev`,
    `neutro_ev`, `safe_edge`, `neutro_edge` na mesma linha da curva: curva e
    limiar mudam juntos, na mesma versao — separa-los recria a convivencia
    de dois regimes que este trabalho existe para acabar.
    """
    status = resultado["status"]
    if status not in STATUS_VALIDOS:
        raise ValueError(f"status desconhecido: {status!r}")
    limiares = limiares or {}
    return {
        "familia": familia, "liga": liga, "versao": versao,
        "a": resultado["a"], "b": resultado["b"],
        "n_jogos": n_jogos, "brier_validacao": brier, "origem": origem,
        "status": status,
        "fator_encurtamento": resultado.get("fator_encurtamento"),
        "motivo": resultado.get("motivo", ""),
        "safe_ev": limiares.get("safe_ev"),
        "neutro_ev": limiares.get("neutro_ev"),
        "safe_edge": limiares.get("safe_edge"),
        "neutro_edge": limiares.get("neutro_edge"),
    }


def gravar_ciclo(linhas: List[Dict[str, Any]]) -> int:
    """Grava as linhas do ciclo e promove `adotada`/`encurtada`/`revertida`
    a `vigente`.

    `revertida` entra no conjunto de promocao: sem isso a versao ruim
    continuava `vigente` e continuava publicando, e a reversao virava
    so uma linha de log. O `(a, b)` que essa linha carrega e
    responsabilidade de quem monta `linhas` (o ciclo) -- aqui so promove o
    que recebe, sem reinterpretar.
    """
    if not linhas:
        return 0
    sql = """
        INSERT INTO calibragem_versoes
            (familia, liga, versao, a, b, n_jogos, brier_validacao,
             origem, status, fator_encurtamento, motivo,
             safe_ev, neutro_ev, safe_edge, neutro_edge)
        VALUES (%(familia)s, %(liga)s, %(versao)s, %(a)s, %(b)s, %(n_jogos)s,
                %(brier_validacao)s, %(origem)s, %(status)s,
                %(fator_encurtamento)s, %(motivo)s,
                %(safe_ev)s, %(neutro_ev)s, %(safe_edge)s, %(neutro_edge)s)
    """
    promove = """
        UPDATE calibragem_versoes SET status = 'substituida'
         WHERE familia = %s AND liga = %s AND status = 'vigente'
    """
    with _conexao() as c, c.cursor() as cur:
        for ln in linhas:
            if ln["status"] in ("adotada", "encurtada", "revertida"):
                cur.execute(promove, (ln["familia"], ln["liga"]))
                cur.execute(sql, dict(ln, status="vigente"))
                cur.execute(sql, ln)
            else:
                cur.execute(sql, ln)
    logger.info("[calibragem] ciclo gravou %d linhas de auditoria", len(linhas))
    return len(linhas)


# A leitura de `vigente` e UMA so, e traz a curva E os limiares (#249). Duas
# consultas seriam duas conexoes por container frio no caminho de `/fixtures`,
# que ja namora o teto de 60s da Lambda — e, pior, curva e limiar poderiam vir
# de instantes diferentes, que e exatamente a convivencia de dois regimes que
# o #244 mediu. A ordem das quatro colunas vem de `limiares.CAMPOS`, entao a
# lista nao existe duas vezes.
SQL_VIGENTES = """
    SELECT familia, liga, versao, a, b, criada_em, {campos}
      FROM calibragem_versoes
     WHERE status = 'vigente'
""".format(campos=", ".join(CAMPOS_LIMIAR))


def carregar_vigentes() -> Dict[tuple, Dict[str, Any]]:
    """As celulas vigentes, COM `criada_em` e COM os limiares re-derivados.

    `criada_em` nao e enfeite de auditoria: e o inicio da janela de reversao
    (#248, I1). Os jogos que uma versao pode julgar sao os que ela serviu, e
    isso e exatamente `published_at > criada_em`.

    `limiares` carrega so os campos NAO NULOS entre `safe_ev`, `neutro_ev`,
    `safe_edge` e `neutro_edge` — a linha de uma celula sem re-derivacao
    (familia sem pick com odd, por exemplo) grava os quatro como NULL, e
    NULL nao pode virar 0,0 no caminho de decisao.
    """
    with _conexao() as c, c.cursor() as cur:
        cur.execute(SQL_VIGENTES)
        saida = {}
        for r in cur.fetchall():
            limiares = {campo: float(valor)
                        for campo, valor in zip(CAMPOS_LIMIAR, r[6:])
                        if valor is not None}
            saida[(r[0], r[1])] = {"versao": r[2], "a": float(r[3]),
                                   "b": float(r[4]), "criada_em": r[5],
                                   "limiares": limiares}
        return saida


def limiares_por_familia(vigentes: Dict[tuple, Dict[str, Any]]) -> Dict[str, dict]:
    """Os quatro limiares por FAMILIA, a partir das celulas vigentes.

    `DEFAULT_THRESHOLDS` nao tem granularidade de liga, e a re-derivacao
    tambem nao: `ciclo.executar` calcula um jogo de limiares por familia e
    grava o MESMO em toda linha daquela familia. A celula canonica e
    portanto `(familia, "")` — a celula-familia.

    Fallback deliberado: se a celula-familia nao esta vigente (congelada num
    ciclo anterior, por exemplo) mas alguma celula de liga da mesma familia
    esta, os limiares saem da linha vigente mais recente da familia. Todas
    carregam o mesmo valor por construcao; deixar a familia sem limiar
    enquanto a curva de uma liga dela ja se moveu seria publicar volume
    maior com o limiar velho — o defeito que a re-derivacao existe para
    impedir.
    """
    saida: Dict[str, dict] = {}
    reservas: Dict[str, tuple] = {}
    for (familia, liga), cel in vigentes.items():
        limiares = cel.get("limiares") or {}
        if not limiares:
            continue
        if not liga:
            saida[familia] = dict(limiares)
            continue
        anterior = reservas.get(familia)
        criada_em = cel.get("criada_em")
        if anterior is None or _mais_recente(criada_em, anterior[0]):
            reservas[familia] = (criada_em, dict(limiares))
    for familia, (_criada_em, limiares) in reservas.items():
        if familia in saida:
            continue
        logger.warning(
            "[calibragem] familia '%s' sem celula-familia vigente; limiares "
            "servidos da linha de liga mais recente", familia)
        saida[familia] = limiares
    return saida


def _mais_recente(candidata, atual) -> bool:
    """`candidata > atual`, tolerante a `None` e a fusos incomparaveis."""
    if atual is None:
        return True
    if candidata is None:
        return False
    try:
        return candidata > atual
    except TypeError:                                        # noqa: BLE001
        return False


def carregar_anterior(familia: str, liga: str) -> Optional[Dict[str, Any]]:
    """A ultima versao 'substituida' da celula — a que estava vigente antes
    da atual.

    Sem isso, `avaliar_reversao` seria chamada com o MESMO dict como
    `vigente` e `anterior`: os dois Briers ficariam sempre identicos, a acao
    seria sempre `manter`, e a reversao nunca dispararia — a patologia que
    esta tarefa existe para impedir. `None` quando nao ha anterior, o caso
    normal nos primeiros ciclos.
    """
    with _conexao() as c, c.cursor() as cur:
        cur.execute("""
            SELECT versao, a, b FROM calibragem_versoes
             WHERE familia = %s AND liga = %s AND status = 'substituida'
             ORDER BY versao DESC LIMIT 1
        """, (familia, liga))
        linha = cur.fetchone()
        if linha is None:
            return None
        return {"versao": linha[0], "a": float(linha[1]), "b": float(linha[2])}


def carregar_parametros_para_curva() -> Dict[tuple, tuple]:
    """Formato que `curva.aplicar_versao` consome."""
    return {ch: (v["versao"], v["a"], v["b"])
            for ch, v in carregar_vigentes().items()}


# Status que representam a DECISAO de um ciclo sobre a celula. `vigente` e
# `substituida` sao escrituracao (a copia promovida e a que ela substituiu),
# nao decisao, e por isso ficam de fora de `ultimo_status_de_ciclo`.
STATUS_DE_DECISAO = ("adotada", "encurtada", "revertida", "congelada",
                     "rejeitada", "abaixo_do_piso", "inalterada")


def ultimo_status_de_ciclo(familia: str, liga: str) -> Optional[str]:
    """A ultima DECISAO tomada sobre a celula. `None` se nunca houve uma.

    Existe para o congelamento ser pegajoso (#248, I2). `avaliar_reversao`
    devolvia `congelar` depois de duas reversoes seguidas, o ciclo gravava a
    linha, e no ciclo seguinte ninguem lia esse status de volta: a celula
    voltava a adotar normalmente. A "revisao humana" prometida pela spec
    (secao 5.3) era um `logger.error` e mais nada.

    COMO DESTRAVAR uma celula congelada — e uma acao humana, deliberada, e
    fica no historico como qualquer outra linha:

        INSERT INTO calibragem_versoes
            (familia, liga, versao, a, b, n_jogos, origem, status, motivo)
        SELECT familia, liga, versao, a, b, 0, origem, 'inalterada',
               'destravada manualmente por <quem>: <por que>'
          FROM calibragem_versoes
         WHERE familia = '<familia>' AND liga = '<liga>'
         ORDER BY id DESC LIMIT 1;

    Qualquer status de decisao que nao seja `congelada` destrava — o INSERT
    acima usa `inalterada` porque e o que descreve a verdade: nada mudou,
    so a trava saiu.
    """
    with _conexao() as c, c.cursor() as cur:
        cur.execute(
            """
            SELECT status FROM calibragem_versoes
             WHERE familia = %s AND liga = %s AND status = ANY(%s)
             ORDER BY id DESC LIMIT 1
            """,
            (familia, liga, list(STATUS_DE_DECISAO)),
        )
        linha = cur.fetchone()
        return linha[0] if linha else None


def contar_reversoes_seguidas(familia: str, liga: str) -> int:
    """Quantas reversoes seguidas a celula acumulou, da mais recente para tras.

    Duas reversoes seguidas congelam a celula (spec 5.3), entao o que conta
    como "seguida" decide quando alguem e chamado para olhar. A regra, para
    TODOS os status que podem aparecer no historico — antes so `inalterada`
    tinha sido decidida em voz alta, e `congelada`/`rejeitada` estavam fora
    da contagem por efeito colateral da clausula `IN`, sem ninguem ter
    escolhido isso:

      revertida              conta +1 e a varredura segue para tras.
      adotada / encurtada    ZERAM. Uma adocao bem-sucedida encerra a
                             sequencia — e o unico evento que encerra.
      inalterada             IGNORADA: um ciclo sem dado novo nao e uma
                             tentativa, entao nao conta nem zera. Tres
                             reversoes com uma pausa no meio SAO tres
                             fracassos.
      congelada              IGNORADA. Alem do mesmo motivo, `congelada` e
                             CONSEQUENCIA de duas reversoes: se zerasse, o
                             congelamento se desfaria sozinho no ciclo
                             seguinte, e o congelamento pegajoso (#248, I2)
                             deixaria de existir.
      rejeitada              IGNORADA: a proposta foi barrada (b <= 0) e
      abaixo_do_piso         nunca chegou a publicar. Nao ha o que fracassar.

    O `LIMIT 5` e o alcance: sequencia mais longa que isso ja congelou muito
    antes.
    """
    with _conexao() as c, c.cursor() as cur:
        cur.execute("""
            SELECT status FROM calibragem_versoes
             WHERE familia = %s AND liga = %s
               AND status IN ('revertida', 'adotada', 'encurtada')
             ORDER BY id DESC LIMIT 5
        """, (familia, liga))
        seguidas = 0
        for (st,) in cur.fetchall():
            if st == "revertida":
                seguidas += 1
            else:
                break
        return seguidas


def carregar_semente_backfill(caminho: str) -> List[Pick]:
    """Le o artefato do backfill (#227) e devolve Picks no mesmo formato.

    O arquivo e um JSON com uma lista de picks reconstruidos. Ausente ou
    ilegivel devolve lista vazia — a semente e opcional por desenho, e o
    ciclo continua sem ela.

    Classificacao de familia usa `classificar_familia(market, selection)`,
    nao `familia_do_mercado` direto no rotulo concatenado: e a mesma
    correcao da rodada 1 (ver docstring de `classificar_familia`) — resolver
    primeiro por `market` isolado evita que "Corners Over 7.5" perca para
    "over " e va parar em Over/Under.
    """
    import json
    if not os.path.exists(caminho):
        logger.info("[calibragem] semente ausente em %s", caminho)
        return []
    try:
        dados = json.loads(open(caminho, encoding="utf-8").read())
    except Exception as e:                                   # noqa: BLE001
        logger.warning("[calibragem] semente ilegivel: %s", e)
        return []

    preparadas = []
    for d in dados:
        market = d.get("market", "")
        selection = d.get("selection", "")
        familia = classificar_familia(market, selection)
        if familia is None:
            continue
        rotulo = rotulo_do_legado(market, selection)
        if rotulo is None:
            continue
        raw, y = d.get("raw_prob"), d.get("outcome")
        if raw is None or y is None:
            continue
        preparadas.append((d, familia, rotulo, float(raw), int(bool(int(y))),
                           selection))

    # A semente alimenta `ajustar_hierarquico` igual ao ledger, entao ela
    # precisa do MESMO regressor: `p_legado`. Sem isto a semente entraria com
    # `p_legado=None` e `curva.entrada_da_curva` levantaria -- de proposito,
    # e melhor do que a semente aprender sobre outra curva que a amostra.
    _aquecer_correcoes_por_liga(d.get("league_id") or ""
                                for d, _, _, _, _, _ in preparadas)

    saida: List[Pick] = []
    with _trace_do_legado_silenciado():
        for d, familia, rotulo, raw, y, selection in preparadas:
            liga = d.get("league_id") or ""
            p_legado = base_da_composicao(raw, rotulo, liga, REGIME_DA_AMOSTRA)
            saida.append(Pick(d.get("match_id", ""), familia, liga, raw, y,
                              None, selection, None, p_legado))
    return saida
