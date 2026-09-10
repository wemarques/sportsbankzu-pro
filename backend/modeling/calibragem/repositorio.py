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

from backend.modeling.calibragem.curva import familia_do_mercado

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

    saida: List[Pick] = []
    sem_familia = 0
    for ln in escolher_ultima_geracao(brutas):
        familia = classificar_familia(ln["market"], ln["selection"])
        if familia is None:
            sem_familia += 1
            continue
        saida.append(Pick(ln["match_id"], familia, ln["league_id"],
                          ln["raw_prob"], int(bool(int(ln["outcome"]))),
                          ln["book_odd"], ln["selection"],
                          ln["published_at"]))
    if sem_familia:
        logger.warning("[calibragem] %d picks sem familia reconhecida", sem_familia)
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


def carregar_vigentes() -> Dict[tuple, Dict[str, Any]]:
    """As celulas vigentes, COM `criada_em`.

    `criada_em` nao e enfeite de auditoria: e o inicio da janela de reversao
    (#248, I1). Os jogos que uma versao pode julgar sao os que ela serviu, e
    isso e exatamente `published_at > criada_em`.
    """
    with _conexao() as c, c.cursor() as cur:
        cur.execute("""
            SELECT familia, liga, versao, a, b, criada_em
              FROM calibragem_versoes
             WHERE status = 'vigente'
        """)
        return {(r[0], r[1]): {"versao": r[2], "a": float(r[3]),
                               "b": float(r[4]), "criada_em": r[5]}
                for r in cur.fetchall()}


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

    saida: List[Pick] = []
    for d in dados:
        market = d.get("market", "")
        selection = d.get("selection", "")
        familia = classificar_familia(market, selection)
        if familia is None:
            continue
        raw, y = d.get("raw_prob"), d.get("outcome")
        if raw is None or y is None:
            continue
        saida.append(Pick(d.get("match_id", ""), familia,
                          d.get("league_id") or "", float(raw),
                          int(bool(int(y))), None, selection))
    return saida
