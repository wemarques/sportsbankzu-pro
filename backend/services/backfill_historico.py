# -*- coding: utf-8 -*-
"""#227 - reconstroi picks passados a partir do historico, com escanteios dentro.

O #220 mede inclinacao de calibracao e precisa de observacoes; o ledger (#218)
esta desligado e, mesmo ligado, so acumula daqui para a frente. Este modulo
produz as observacoes que ja existem: para cada partida finalizada, reconstroi
o estado dos times **ate a rodada anterior**, roda os motores de verdade e
compara a probabilidade com o desfecho real.

Escanteios entram no escopo por medicao, nao por opiniao: o #226-b contou, em
605 finalizadas da championship, contagem em 100% (`totalCornerCount`,
`team_a_corners`, `team_b_corners`) e a escada `odds_corners_*` em 100%. A
exclusao anterior vinha de uma rota que media `home_team_corner_count` — um
apelido que o `data_mapper` **cria**, inexistente na linha crua.

## O que este instrumento mede, e o que nao mede

Mede: se um modelo desta familia, alimentado por este dado, separa o que
acontece do que nao acontece. E a pergunta do #220.

**Nao** mede "a probabilidade exata que publicamos naquele dia". O pipeline de
producao come `stats` de time vindos dos endpoints da FootyStats no momento da
consulta, e nao existe versao historica deles. Aqui o estado pre-jogo e
reconstruido das proprias partidas anteriores. Sao modelos da mesma familia
alimentados por caminhos diferentes — e dizer o contrario seria vender
retrospectiva como registro.

## Vazamento temporal

A regra e uma: o estado usado para prever a partida N e montado **antes** de a
partida N entrar no rastreador. E o mesmo padrao do `CornerStatsTracker`
(`build features BEFORE updating tracker`). Ha teste que quebra se a ordem
inverter.
"""
from __future__ import annotations

import logging
import math
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from backend.services.math_service import poisson_cdf
from backend.utils.valores import primeiro_valido

logger = logging.getLogger("sportsbankzu.backfill")

# Minimo de partidas previas por time para reconstruir estado. Abaixo disto a
# media e ruido e o pick reconstruido nao representa nada.
MIN_JOGOS_PREVIOS = 5

# Linhas de gols com odd historica na linha de partida. As demais entram so com
# probabilidade — o #225-a mediu que a FootyStats publica over25/over35, nao a
# escada inteira.
_ODD_GOLS = {2.5: "odds_ft_over25", 3.5: "odds_ft_over35"}
_LINHAS_GOLS = [0.5, 1.5, 2.5, 3.5, 4.5]
_LINHAS_ESCANTEIOS = [7.5, 8.5, 9.5, 10.5, 11.5]
_LINHAS_CARTOES = [2.5, 3.5, 4.5, 5.5]


# #227-a - a probabilidade do MERCADO, para servir de referencia.
#
# Sem uma referencia, "inclinacao zero" nao distingue tres coisas: o modelo nao
# tem resolucao, o desfecho e imprevisivel neste n, ou o instrumento esta
# quebrado. A casa de apostas tem resolucao — se ela tambem der zero nos MESMOS
# picks, o problema nao esta no modelo.
#
# Par over/under quando existe: de-vig de verdade (#219). So a perna over:
# `1/odd`, que carrega a margem e e marcada como tal.
_PAR_ODD = {
    "odds_ft_over25": "odds_ft_under25",
    "odds_ft_over35": "odds_ft_under35",
    "odds_btts_yes": "odds_btts_no",
    "odds_corners_over_75": "odds_corners_under_75",
    "odds_corners_over_85": "odds_corners_under_85",
    "odds_corners_over_95": "odds_corners_under_95",
    "odds_corners_over_105": "odds_corners_under_105",
    "odds_corners_over_115": "odds_corners_under_115",
}


def prob_do_mercado(odds: Dict[str, Any], chave: str) -> Tuple[Optional[float], str]:
    """(probabilidade, metodo). `None` quando nao ha preco utilizavel."""
    over = odds.get(chave)
    if not over or over <= 1.0:
        return None, "sem_odd"
    under = odds.get(_PAR_ODD.get(chave, ""))
    if under and under > 1.0:
        try:
            from backend.services.devig import prob_justa
            p = prob_justa([over, under], 0)
            if p is not None and 0.0 < p < 1.0:
                return p, "devig"
        except Exception:
            pass
    return 1.0 / over, "implicita"


# ── leitura da linha crua ────────────────────────────────────────────────
def _num(valor: Any) -> Optional[float]:
    """Float quando der, `None` quando nao.

    `-1` e o "sem dado" da FootyStats e vira `None`. `0` sobrevive: zero gol,
    zero escanteio e zero cartao sao resultados, e trata-los como ausencia e
    exatamente o erro de #201/#208/#217/#225-b.
    """
    if valor is None or valor == "":
        return None
    try:
        n = float(valor)
    except (TypeError, ValueError):
        return None
    return None if n == -1 else n


def extrair_partida(linha: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Normaliza a linha crua. `None` quando o desfecho essencial falta.

    Nomes conforme medido no #226-b — nao conforme o `data_mapper` os renomeia
    depois.
    """
    if str(linha.get("status", "")).lower() not in {"complete", "finished", "ft"}:
        return None

    gols_casa = _num(linha.get("homeGoalCount"))
    gols_fora = _num(linha.get("awayGoalCount"))
    if gols_casa is None or gols_fora is None:
        return None

    casa = primeiro_valido(linha.get("homeTeam"), linha.get("home_name"))
    fora = primeiro_valido(linha.get("awayTeam"), linha.get("away_name"))
    if not casa or not fora:
        return None

    esc_casa = _num(linha.get("team_a_corners"))
    esc_fora = _num(linha.get("team_b_corners"))
    esc_total = _num(linha.get("totalCornerCount"))
    if esc_total is None and esc_casa is not None and esc_fora is not None:
        esc_total = esc_casa + esc_fora

    cart_casa = _num(linha.get("team_a_yellow_cards"))
    cart_fora = _num(linha.get("team_b_yellow_cards"))
    cart_total = None if cart_casa is None or cart_fora is None else cart_casa + cart_fora

    return {
        "match_id": primeiro_valido(linha.get("id"), linha.get("match_id")),
        "date_unix": _num(linha.get("date_unix")) or 0.0,
        "casa": casa, "fora": fora,
        "gols_casa": gols_casa, "gols_fora": gols_fora,
        "escanteios_casa": esc_casa, "escanteios_fora": esc_fora,
        "escanteios_total": esc_total,
        "cartoes_casa": cart_casa, "cartoes_fora": cart_fora,
        "cartoes_total": cart_total,
        "chutes_casa": _num(linha.get("team_a_shots")),
        "chutes_fora": _num(linha.get("team_b_shots")),
        "posse_casa": _num(linha.get("team_a_possession")),
        "posse_fora": _num(linha.get("team_b_possession")),
        "xg_casa": _num(linha.get("team_a_xg")),
        "xg_fora": _num(linha.get("team_b_xg")),
        "odds": {k: _num(v) for k, v in linha.items() if str(k).startswith("odds_")},
    }


# ── estado pre-jogo ──────────────────────────────────────────────────────
class RastreadorHistorico:
    """O que cada time fez ATE a partida anterior. Nunca inclui a atual."""

    def __init__(self) -> None:
        self._por_time: Dict[str, List[Dict[str, Any]]] = {}

    def registrar(self, partida: Dict[str, Any]) -> None:
        for time, lado in ((partida["casa"], "casa"), (partida["fora"], "fora")):
            oposto = "fora" if lado == "casa" else "casa"
            self._por_time.setdefault(time, []).append({
                "em_casa": lado == "casa",
                "gols_pro": partida[f"gols_{lado}"],
                "gols_contra": partida[f"gols_{oposto}"],
                "escanteios_pro": partida[f"escanteios_{lado}"],
                "escanteios_contra": partida[f"escanteios_{oposto}"],
                "cartoes_pro": partida[f"cartoes_{lado}"],
                "chutes_pro": partida[f"chutes_{lado}"],
                "posse_pro": partida[f"posse_{lado}"],
                "xg_pro": partida[f"xg_{lado}"],
            })

    def jogos(self, time: str, em_casa: Optional[bool] = None) -> int:
        return len(self._recorte(time, em_casa))

    def _recorte(self, time: str, em_casa: Optional[bool]) -> List[Dict[str, Any]]:
        hist = self._por_time.get(time, [])
        if em_casa is None:
            return hist
        return [j for j in hist if j["em_casa"] is em_casa]

    def media(self, time: str, campo: str, em_casa: Optional[bool] = None,
              ultimos: Optional[int] = None) -> Optional[float]:
        """Media do campo, `None` quando nao ha nenhum valor — nunca 0 por falta.

        Uma media de zero observacoes nao e zero, e devolver 0 aqui plantaria
        no motor exatamente a "informacao de ausencia" que o #208 removeu.
        """
        vals = [j[campo] for j in self._recorte(time, em_casa) if j[campo] is not None]
        if ultimos:
            vals = vals[-ultimos:]
        return sum(vals) / len(vals) if vals else None

    def ultimos_gols(self, time: str, n: int = 8) -> List[float]:
        return [j["gols_pro"] for j in self._por_time.get(time, [])[-n:]
                if j["gols_pro"] is not None]


def estado_do_time(rast: RastreadorHistorico, time: str, em_casa: bool) -> Dict[str, Any]:
    """Dicionario com as chaves que os motores REALMENTE leem.

    Auditado contra `lambda_calculator.calcular_lambda_dinamico`,
    `corners_engine.estimate_corners_lambda` e `cards_engine.predict_cards` —
    nao contra o que seria natural nomear.
    """
    lado = "home" if em_casa else "away"
    m = rast.media
    return {
        # lambda_calculator
        f"goals_scored_avg_{lado}": m(time, "gols_pro", em_casa),
        "goals_scored_avg_overall": m(time, "gols_pro"),
        "goals_scored_avg_last_5": m(time, "gols_pro", ultimos=5),
        f"goals_conceded_avg_{lado}": m(time, "gols_contra", em_casa),
        "goals_conceded_avg_overall": m(time, "gols_contra"),
        f"games_played_{lado}": rast.jogos(time, em_casa),
        "games_played": rast.jogos(time),
        # corners_engine
        f"corners{'AVG_home' if em_casa else 'AVG_away'}": m(time, "escanteios_pro", em_casa),
        "cornersAVG_overall": m(time, "escanteios_pro"),
        f"{lado}CornersAgainstPerMatch": m(time, "escanteios_contra", em_casa),
        f"cornersAgainstAVG_{lado}": m(time, "escanteios_contra"),
        "corners_recorded_matches_num": rast.jogos(time),
        # cards_engine
        f"cardsAVG_{lado}": m(time, "cartoes_pro", em_casa),
        "cardsAVG_overall": m(time, "cartoes_pro"),
        f"matchesPlayed_{lado}": rast.jogos(time, em_casa),
        "matchesPlayed_overall": rast.jogos(time),
        # contexto
        f"shotsAVG_{lado}": m(time, "chutes_pro", em_casa),
        f"possessionAVG_{lado}": m(time, "posse_pro", em_casa),
        f"xgAVG_{lado}": m(time, "xg_pro", em_casa),
    }


def estado_da_liga(partidas: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Medias da liga sobre as partidas JA vistas. Vazio devolve dicionario vazio.

    Devolver medias inventadas para uma liga sem historico seria dar ao motor um
    numero com cara de medicao.
    """
    if not partidas:
        return {}

    def med(f: Callable[[Dict[str, Any]], Optional[float]]) -> Optional[float]:
        vals = [v for v in (f(p) for p in partidas) if v is not None]
        return sum(vals) / len(vals) if vals else None

    return {
        "average_goals_per_match": med(lambda p: p["gols_casa"] + p["gols_fora"]),
        "avg_goals_scored_by_home_teams": med(lambda p: p["gols_casa"]),
        "avg_goals_scored_by_away_teams": med(lambda p: p["gols_fora"]),
        "average_corners_per_match": med(lambda p: p["escanteios_total"]),
        "cornersAVG_overall": med(lambda p: p["escanteios_total"]),
        "average_cards_per_match": med(lambda p: p["cartoes_total"]),
        "leagueAvgCards": med(lambda p: p["cartoes_total"]),
        "matches_completed": len(partidas),
    }


# ── mercados ─────────────────────────────────────────────────────────────
def _p_over(linha: float, lam: float) -> float:
    return max(0.0, min(1.0, 1.0 - poisson_cdf(int(linha), lam)))


def _picks_gols(estado, partida, league_id) -> List[Dict[str, Any]]:
    from backend.modeling.lambda_calculator import calcular_lambda_jogo

    casa, fora, liga, rast, nome_casa, nome_fora = estado
    lam_casa, lam_fora = calcular_lambda_jogo(
        casa, fora, liga, "NORMAL", league_id,
        recent_goals_home=rast.ultimos_gols(nome_casa),
        recent_goals_away=rast.ultimos_gols(nome_fora),
    )
    total = partida["gols_casa"] + partida["gols_fora"]
    saida = []
    for linha in _LINHAS_GOLS:
        saida.append({
            "market": f"Over {linha} gols",
            "prob": _p_over(linha, lam_casa + lam_fora),
            "outcome": int(total > linha),
            "chave_odd": _ODD_GOLS.get(linha),
            "lambda": round(lam_casa + lam_fora, 4),
        })
    # BTTS: Poisson independente dos dois lambdas exibidos (#187)
    p_btts = (1 - math.exp(-lam_casa)) * (1 - math.exp(-lam_fora))
    saida.append({
        "market": "BTTS Yes",
        "prob": max(0.0, min(1.0, p_btts)),
        "outcome": int(partida["gols_casa"] > 0 and partida["gols_fora"] > 0),
        "chave_odd": "odds_btts_yes",
        "lambda": round(lam_casa + lam_fora, 4),
    })
    return saida


def _picks_escanteios(estado, partida, league_id) -> List[Dict[str, Any]]:
    from backend.modeling.corners_engine import estimate_corners_lambda

    if partida["escanteios_total"] is None:
        return []                      # sem desfecho nao ha o que medir
    casa, fora, liga, _rast, _nc, _nf = estado
    lam = estimate_corners_lambda(casa, fora, liga)
    if not lam or lam <= 0:
        return []
    return [{
        "market": f"Escanteios Over {linha}",
        "prob": _p_over(linha, lam),
        "outcome": int(partida["escanteios_total"] > linha),
        "chave_odd": f"odds_corners_over_{str(linha).replace('.', '')}",
        "lambda": round(lam, 4),
    } for linha in _LINHAS_ESCANTEIOS]


def _picks_cartoes(estado, partida, league_id) -> List[Dict[str, Any]]:
    from backend.modeling.cards_engine import predict_cards

    if partida["cartoes_total"] is None:
        return []
    casa, fora, liga, _rast, _nc, _nf = estado
    resultado = predict_cards(casa, fora, league_id, liga)
    lam = resultado.get("cards_lambda")
    if not lam or lam <= 0:
        return []
    return [{
        "market": f"Cartoes Over {linha}",
        "prob": _p_over(linha, lam),
        "outcome": int(partida["cartoes_total"] > linha),
        "chave_odd": None,             # a linha de partida nao traz odd de cartao
        "lambda": round(lam, 4),
    } for linha in _LINHAS_CARTOES]


MERCADOS: Tuple[Tuple[str, Callable], ...] = (
    ("gols", _picks_gols),
    ("escanteios", _picks_escanteios),
    ("cartoes", _picks_cartoes),
)


# ── reconstrucao ─────────────────────────────────────────────────────────
def reconstruir(
    linhas: Iterable[Dict[str, Any]],
    league_id: str,
    min_jogos: int = MIN_JOGOS_PREVIOS,
    familias: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    """Percorre a temporada em ordem e devolve picks com desfecho.

    Returns:
        {"picks": [...], "resumo": {...}} — cada pick no formato que o
        `scripts/medir_inclinacao.py` consome (`prob`, `outcome`, `match_id`,
        `league_id`, `market`), mais `odd`/`ev` quando havia preco.
    """
    escolhidas = set(familias) if familias else {n for n, _ in MERCADOS}
    partidas = [p for p in (extrair_partida(l) for l in linhas) if p]
    partidas.sort(key=lambda p: p["date_unix"])

    rast = RastreadorHistorico()
    vistas: List[Dict[str, Any]] = []
    picks: List[Dict[str, Any]] = []
    pulados_por_amostra = 0

    for partida in partidas:
        casa, fora = partida["casa"], partida["fora"]
        if rast.jogos(casa) < min_jogos or rast.jogos(fora) < min_jogos:
            pulados_por_amostra += 1
            rast.registrar(partida)      # entra no historico sem virar pick
            vistas.append(partida)
            continue

        # ESTADO ANTES: montado com `rast`/`vistas` ainda sem esta partida.
        estado = (
            estado_do_time(rast, casa, em_casa=True),
            estado_do_time(rast, fora, em_casa=False),
            estado_da_liga(vistas),
            rast, casa, fora,
        )

        for nome, construir in MERCADOS:
            if nome not in escolhidas:
                continue
            try:
                brutos = construir(estado, partida, league_id)
            except Exception as e:                       # falha aberta, por familia
                logger.warning("[#227] %s falhou em %s: %s", nome, partida["match_id"], e)
                continue
            for p in brutos:
                chave_odd = p.pop("chave_odd") or ""
                odd = partida["odds"].get(chave_odd, None)
                odd = odd if odd and odd > 1.0 else None
                p_mercado, metodo = prob_do_mercado(partida["odds"], chave_odd)
                picks.append({
                    "match_id": partida["match_id"],
                    "league_id": league_id,
                    "date_unix": partida["date_unix"],
                    "familia": nome,
                    "market": p["market"],
                    "prob": round(p["prob"], 6),
                    "outcome": p["outcome"],
                    "lambda": p["lambda"],
                    "odd": odd,
                    "ev": round(p["prob"] * odd - 1.0, 6) if odd else None,
                    "prob_mercado": round(p_mercado, 6) if p_mercado else None,
                    "mercado_metodo": metodo,
                })

        rast.registrar(partida)
        vistas.append(partida)

    com_odd = sum(1 for p in picks if p["odd"] is not None)
    resumo = {
        "league_id": league_id,
        "partidas_finalizadas": len(partidas),
        "partidas_usadas": len(partidas) - pulados_por_amostra,
        "puladas_por_amostra": pulados_por_amostra,
        "min_jogos_previos": min_jogos,
        "picks": len(picks),
        "picks_com_odd": com_odd,
        "picks_com_ev": com_odd,
        "por_familia": {
            n: sum(1 for p in picks if p["familia"] == n) for n, _ in MERCADOS
        },
        "prob_mercado": {
            m: sum(1 for p in picks if p["mercado_metodo"] == m)
            for m in ("devig", "implicita", "sem_odd")
        },
    }
    return {"picks": picks, "resumo": resumo}
