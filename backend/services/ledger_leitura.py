# -*- coding: utf-8 -*-
"""#255 — leitura do ledger para `/ledger/dia` e `/ledger/agregado` (Fase 1
da reformulacao do frontend, spec §6.3).

Fonte unica: `prediction_ledger x ledger_outcomes`, so geracao pre-apito
(#252). NUNCA le `audit_results` — proibicao 13 / Regra #244 do CLAUDE.md
tambem valem para a tela que o usuario ve, nao so para calibracao.

Reaproveita, sem reimplementar (proibicao 5): `filtrar_amostra` (#252,
`backend/services/amostra_ledger.py` — movido da Task 1 deste plano),
`escolher_ultima_geracao` e `classificar_familia`
(`backend/modeling/calibragem/repositorio.py`, #248), e `_brier`/`MIN_N`
(`backend/services/brier_service.py`, #109/#079).

Contrato de saida (Etapa 2-bis, CLAUDE.md): este modulo e leitura pura — nao
grava nada, nao existe consumidor externo alem das rotas HTTP deste mesmo
plano (`backend/routes/ledger.py`, Task 3) e do frontend novo que ainda nao
existe (fase 4). `stake` nunca e gravado no ledger
(`prediction_ledger.linhas_do_bundle` nao passa `stake=` a `montar_linha`) —
por isso `retorno` sai `null` com `motivo`, nunca um numero inventado.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from backend.modeling.calibragem.repositorio import (
    classificar_familia, escolher_ultima_geracao,
)
from backend.services.amostra_ledger import filtrar_amostra
from backend.services.brier_service import MIN_N, _brier

_FAMILIAS = ("Over/Under", "BTTS", "Corners", "Cards", "1X2", "Double Chance")
_PICKS_CONTADOS = ("SAFE", "NEUTRO_QUALIFICADO")     # o talao, spec §4.2 estado `vale`
_INICIO_TEMPORADA = "2026-09-03"                     # primeiro pick do ledger, spec §6.3
_FOLGA_PUBLICACAO_DIAS = 3   # published_at pode anteceder o kickoff em ate 3 dias


def _conn():
    import psycopg2
    dsn = (os.environ.get("DATABASE_URL") or "").strip()
    if not dsn:
        raise RuntimeError(
            "DATABASE_URL nao esta definida — sem ela o psycopg2 tentaria "
            "localhost:5432, que nao e o banco (mesma guarda de #230-a)."
        )
    return psycopg2.connect(dsn, connect_timeout=5)


# #255: NO_BET nunca aparece (spec §4.2) — cortado na propria consulta, nao
# em Python, para ser estruturalmente impossivel de vazar numa rota nova.
_SQL_JANELA = """
    SELECT l.match_id, l.league_id, l.market, l.selection,
           l.published_prob, l.book_odd, l.classification,
           l.published_at, l.kickoff_utc,
           o.outcome, o.detail
      FROM prediction_ledger l
      LEFT JOIN ledger_outcomes o
        ON o.match_id  = l.match_id
       AND o.market    = l.market
       AND o.selection = l.selection
     WHERE l.published_at >= %s AND l.published_at < %s
       AND l.published_prob IS NOT NULL
       AND l.classification IN ('SAFE', 'NEUTRO_QUALIFICADO', 'NEUTRO')
"""


def _buscar_janela(inicio: datetime, fim: datetime) -> List[Dict[str, Any]]:
    """Uma consulta por chamada de `dia`/`agregado`. `filtrar_amostra` aplica
    #252 (pos-kickoff sai); o corte #252-a e no-op aqui porque so age sobre
    `calibrated_prob` — `published_prob` e o que o operador viu de verdade,
    contaminado ou nao pelo bug da camada #248 (ver Task 2 do plano #255).

    O `WHERE classification IN (...)` do SQL ja tira NO_BET na origem; o
    filtro em Python abaixo REPETE essa regra de proposito (defesa em
    profundidade, nao redundancia morta): um teste com dublê de cursor nao
    interpreta o texto do SQL (so devolve linhas fixas), e uma consulta
    futura que esqueca a clausula nao pode deixar NO_BET vazar — spec §4.2,
    "NO_BET nunca"."""
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(_SQL_JANELA, (inicio, fim))
        brutas = [
            {"match_id": r[0], "league_id": r[1] or "", "market": r[2],
             "selection": r[3],
             "published_prob": float(r[4]) if r[4] is not None else None,
             "book_odd": float(r[5]) if r[5] is not None else None,
             "classification": r[6], "published_at": r[7], "kickoff_utc": r[8],
             "outcome": r[9], "detail": r[10]}
            for r in cur.fetchall()
            if r[6] in ("SAFE", "NEUTRO_QUALIFICADO", "NEUTRO")
        ]
        cur.close()
    finally:
        conn.close()
    mantidas, _ = filtrar_amostra(brutas, "published_prob")
    return escolher_ultima_geracao(mantidas)


def _fair_odd(published_prob: Optional[float]) -> Optional[float]:
    """Nao ha coluna `fair_odd` no ledger (so `book_odd`) — deriva-se aqui,
    igual ao que `MarketOutput.compute_display` faz no momento da publicacao
    (`backend/models/market_output.py:147`)."""
    if published_prob is None or published_prob <= 0:
        return None
    return round(1.0 / published_prob, 2)


def _detalhe_textual(market: str, detail: Optional[Dict[str, Any]]) -> Optional[str]:
    """`detail` e o `actual_result` bruto do cron (`backend/cron_handler.py:198-206`):
    `home_goals`, `away_goals`, `total_goals`, `btts`, `result_1x2`,
    `total_corners`, `total_cards`. Aqui vira o texto por familia que a spec
    pede (§6.3): "8 escanteios", "3 gols". `None` quando falta a chave ou o
    desfecho ainda nao existe."""
    if not isinstance(detail, dict):
        return None
    m = (market or "").strip()
    if m == "Corners":
        v = detail.get("total_corners")
        return f"{int(v)} escanteios" if v is not None else None
    if m == "Cards":
        v = detail.get("total_cards")
        return f"{int(v)} cartões" if v is not None else None
    if m == "Over/Under":
        v = detail.get("total_goals")
        return f"{int(v)} gols" if v is not None else None
    if m == "BTTS":
        v = detail.get("btts")
        if v is None:
            return None
        return "ambos marcaram" if v else "só um marcou (ou nenhum)"
    if m in ("1X2", "Double Chance"):
        hg, ag = detail.get("home_goals"), detail.get("away_goals")
        if hg is not None and ag is not None:
            return f"{int(hg)}-{int(ag)}"
        return None
    return None


def _pick_json(l: Dict[str, Any]) -> Dict[str, Any]:
    familia = classificar_familia(l["market"], l["selection"])
    return {
        "match_id": l["match_id"], "league_id": l["league_id"],
        "kickoff_utc": l["kickoff_utc"].isoformat() if l["kickoff_utc"] else None,
        "familia": familia, "market": l["market"], "selection": l["selection"],
        "published_prob": l["published_prob"],
        "fair_odd": _fair_odd(l["published_prob"]),
        "book_odd": l["book_odd"],
        "classification": l["classification"],
        "outcome": l["outcome"],
        "detail": _detalhe_textual(l["market"], l["detail"]),
    }


def _resumo(linhas: List[Dict[str, Any]]) -> Dict[str, int]:
    contados = [l for l in linhas if l["classification"] in _PICKS_CONTADOS]
    resolvidos = [l for l in contados if l["outcome"] is not None]
    return {
        "picks": len(contados),
        "acertos": sum(1 for l in resolvidos if l["outcome"]),
        "jogos": len({l["match_id"] for l in resolvidos}),
    }


def dia(data: str) -> Dict[str, Any]:
    """Um dia: os picks cujo KICKOFF cai no dia `data` (UTC), mais os
    acumulados de 7 e 30 dias terminando neste dia (inclusive), por familia.

    Decisao de implementacao (a spec §6.3 nao fixa o limite exato de
    "semana"/"mes", so define `temporada` = desde 2026-09-03): semana = 7
    dias terminando em `data` (inclusive), mes = 30 dias — mesmos tamanhos
    de `/ledger/agregado?periodo=7d|30d`, para as duas rotas contarem do
    mesmo jeito (spec §7: "os numeros do ResumoDoDia de /ontem == os do
    agregado de /desempenho para o mesmo periodo").
    """
    try:
        dia_dt = datetime.strptime(data, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError as e:
        raise ValueError(f"data invalida: {data!r} (esperado YYYY-MM-DD)") from e

    fim_dia = dia_dt + timedelta(days=1)
    # Uma unica consulta cobrindo a maior janela necessaria (mes = 30 dias)
    # mais a folga de publicacao.
    linhas = _buscar_janela(
        dia_dt - timedelta(days=29 + _FOLGA_PUBLICACAO_DIAS), fim_dia,
    )

    def _na_janela(desde: datetime) -> List[Dict[str, Any]]:
        return [l for l in linhas
                if l.get("kickoff_utc") is not None
                and desde <= l["kickoff_utc"] < fim_dia]

    do_dia = _na_janela(dia_dt)
    picks_json = [_pick_json(l) for l in do_dia]

    def _acumulado(desde: datetime) -> Dict[str, Any]:
        na_janela = _na_janela(desde)
        return {
            fam: _resumo([l for l in na_janela
                         if classificar_familia(l["market"], l["selection"]) == fam])
            for fam in _FAMILIAS
        }

    return {
        "data": data,
        "picks": picks_json,
        "resumo": _resumo(do_dia),
        "semana": _acumulado(dia_dt - timedelta(days=6)),
        "mes": _acumulado(dia_dt - timedelta(days=29)),
    }


def _janela_periodo(periodo: str, hoje: Optional[datetime] = None
                    ) -> Tuple[datetime, datetime]:
    hoje = hoje or datetime.now(timezone.utc)
    fim = hoje.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    if periodo == "7d":
        return fim - timedelta(days=7), fim
    if periodo == "30d":
        return fim - timedelta(days=30), fim
    if periodo == "temporada":
        inicio = datetime.strptime(_INICIO_TEMPORADA, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return inicio, fim
    raise ValueError(f"periodo invalido: {periodo!r} (esperado 7d|30d|temporada)")


def _segmento(linhas: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Picks/acertos/jogos + Brier com o piso MIN_N=20 em JOGOS (#079)."""
    r = _resumo(linhas)
    resolvidos = [l for l in linhas
                  if l["classification"] in _PICKS_CONTADOS and l["outcome"] is not None]
    brier = None
    if r["jogos"] >= MIN_N:
        brier = round(_brier(
            [l["published_prob"] for l in resolvidos],
            [l["outcome"] for l in resolvidos],
        ), 4)
    return {**r, "brier": brier}


def _buckets_calibracao(resolvidos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """10 faixas fixas [0,0.1) .. [0.9,1.0]. Soma de `n` == len(resolvidos)."""
    faixas = [(i / 10, (i + 1) / 10) for i in range(10)]
    out = []
    for lo, hi in faixas:
        cesta = [l for l in resolvidos
                 if lo <= l["published_prob"] < hi
                 or (hi == 1.0 and l["published_prob"] == 1.0)]
        if not cesta:
            out.append({"prob_media": None, "freq_real": None, "n": 0})
            continue
        prob_media = sum(l["published_prob"] for l in cesta) / len(cesta)
        freq_real = sum(l["outcome"] for l in cesta) / len(cesta)
        out.append({"prob_media": round(prob_media, 4),
                    "freq_real": round(freq_real, 4), "n": len(cesta)})
    return out


def agregado(periodo: str, familia: Optional[str] = None,
            liga: Optional[str] = None, hoje: Optional[datetime] = None
            ) -> Dict[str, Any]:
    """`periodo`: 7d|30d|temporada. `familia`/`liga` filtram o conjunto
    inteiro (acerto, brier, buckets, por_familia, por_liga)."""
    inicio, fim = _janela_periodo(periodo, hoje)
    linhas = _buscar_janela(inicio - timedelta(days=_FOLGA_PUBLICACAO_DIAS), fim)
    na_janela = [l for l in linhas
                 if l.get("kickoff_utc") is not None and inicio <= l["kickoff_utc"] < fim]

    contados = na_janela
    if liga:
        contados = [l for l in contados if l["league_id"] == liga]
    if familia:
        contados = [l for l in contados
                   if classificar_familia(l["market"], l["selection"]) == familia]

    resumo_geral = _segmento(contados)
    resolvidos = [l for l in contados
                  if l["classification"] in _PICKS_CONTADOS and l["outcome"] is not None]

    por_familia = {
        fam: _segmento([l for l in contados
                       if classificar_familia(l["market"], l["selection"]) == fam])
        for fam in _FAMILIAS
    }
    por_liga = {
        lg: _segmento([l for l in contados if l["league_id"] == lg])
        for lg in sorted({l["league_id"] for l in contados if l["league_id"]})
    }

    buckets = _buckets_calibracao(resolvidos) if resumo_geral["jogos"] >= MIN_N else None

    return {
        "periodo": periodo, "familia": familia, "liga": liga,
        "acerto": {"picks": resumo_geral["picks"], "acertos": resumo_geral["acertos"],
                  "jogos": resumo_geral["jogos"]},
        # #255: stake nunca e gravado no ledger — ver Global Constraints do plano.
        "retorno": {"valor": None, "pct_banca": None,
                   "motivo": "stake_nao_gravado_no_ledger"},
        "brier": resumo_geral["brier"],
        "amostra_curta": resumo_geral["jogos"] < MIN_N,
        "por_familia": por_familia,
        "por_liga": por_liga,
        "buckets": buckets,
    }
