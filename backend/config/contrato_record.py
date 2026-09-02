# -*- coding: utf-8 -*-
"""#223 - contrato das chaves do record.

O defeito que este modulo existe para tornar impossivel
-------------------------------------------------------
`dict.get("X")` devolve `None` em silencio. E isso, e so isso, que permite
olhar o consumidor, ver a chave sendo lida, e concluir que ela chega — sem
nunca inspecionar quem a escreve. Todos os defeitos desta semana sao a mesma
instancia, em duas direcoes:

    le sem que alguem escreva ...... #221 (`league_stats`), #216 (4a coluna),
                                     #218 (6 das 10 entradas do ledger)
    escreve sem que alguem leia .... #217 (`no_bet`), #189-f (odds de escanteios)

O #222 proibiu concluir sem prova. Proibicao e prosa: nao impede ninguem. Este
modulo transforma a proibicao em falha de teste.

Como funciona
-------------
1. Varre os CONSUMIDORES DO RECORD (lista fechada abaixo) por `.get("chave")`
   sobre os portadores `match_data`/`record`/`stats`/`league_stats`.
2. Monta records de referencia de verdade, chamando `build_records_from_matches`
   em varios cenarios, e coleta a UNIAO das chaves que existem de fato.
3. Toda chave lida e nunca escrita BLOQUEIA, a menos que esteja declarada em
   `OPCIONAIS` com o motivo pelo qual pode faltar.

A lista de consumidores e fechada de proposito. `mistral_analysis.py` e
`ai_analysis.py` leem `stats`/`match_data` com OUTRA forma — um dicionario de
contexto montado so para eles —, entao varre-los aqui produziria dezenas de
falsos positivos e o contrato viraria ruido. Eles merecem contrato proprio;
misturar os dois nao ajudaria nenhum.
"""
from __future__ import annotations

import os
import re
import time
from typing import Any, Dict, List, Set, Tuple

_RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Modulos que consomem O RECORD montado pelo build_records_from_matches.
CONSUMIDORES: Tuple[str, ...] = (
    "backend/services/ev_classification.py",
    "backend/services/market_service.py",
    "backend/services/prediction_ledger.py",
    "backend/services/bankroll_engine.py",
    "backend/services/correlation_matrix.py",
    "backend/services/comparador_ancora.py",
    "backend/services/auditor_premissas.py",
)

# `match_data` e `record` sao o mesmo objeto; o contrato os trata como um so.
_PORTADORES = ("match_data", "record", "stats", "league_stats")
_NORMALIZA = {"match_data": "record", "record": "record"}

# Chave lida que pode legitimamente faltar, com o motivo. Sem motivo escrito,
# nao entra: a lista existe para registrar decisao, nao para calar o teste.
OPCIONAIS: Dict[str, str] = {
    "refereeAvgCards": "#189-f: so existe quando o lookup de arbitro acha o nome",
}


def _fonte(caminho: str) -> str:
    try:
        with open(os.path.join(_RAIZ, caminho), encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


# `x.get("A", x.get("B", ""))` — B e um nome LEGADO, lido so quando A falta.
# Cobrar B como se fosse leitura primaria produziria falso positivo: o elo que
# importa e o A. O contrato precisa distinguir os dois, senao vira ruido e
# alguem desliga o teste — que e como um gate morre.
_PAD_FALLBACK = re.compile(
    r"\b(?:" + "|".join(_PORTADORES) + r")\.get\(\s*[\"'][a-zA-Z_][\w]*[\"']\s*,\s*"
    r"(?:" + "|".join(_PORTADORES) + r")\.get\(\s*[\"']([a-zA-Z_][\w]*)[\"']"
)


def chaves_de_fallback() -> Set[str]:
    """Nomes lidos apenas como segundo argumento de um get encadeado."""
    out: Set[str] = set()
    for caminho in CONSUMIDORES:
        out |= set(_PAD_FALLBACK.findall(_fonte(caminho)))
    return out


def chaves_lidas() -> Dict[str, Set[str]]:
    """Chaves que os consumidores do record leem, por portador.

    Exclui os nomes legados usados so como fallback encadeado.
    """
    pad = re.compile(
        r"\b(" + "|".join(_PORTADORES) + r")\.get\(\s*[\"']([a-zA-Z_][\w]*)[\"']"
    )
    fallbacks = chaves_de_fallback()
    out: Dict[str, Set[str]] = {"record": set(), "stats": set(), "league_stats": set()}
    for caminho in CONSUMIDORES:
        for var, chave in pad.findall(_fonte(caminho)):
            if chave in fallbacks:
                continue
            out[_NORMALIZA.get(var, var)].add(chave)
    return out


def _cenarios():
    """Records de referencia REAIS, em cenarios que exercitam ramos diferentes."""
    import pandas as pd
    from backend.services.fixtures_service import build_records_from_matches

    ts = int(time.time()) + 3600
    liga = {
        "average_goals_per_match": 2.65, "average_corners_per_match": 10.2,
        "average_cards_per_match": 4.9, "average_fouls_per_match": 22.0,
        "average_shots_per_match": 24.0,
    }
    combos = (
        ({"matches_completed": 25}, "incomplete"),   # liga madura, jogo por vir
        ({"matches_completed": 3}, "incomplete"),    # inicio de temporada
        ({}, "complete"),                            # sem contagem, jogo encerrado
    )
    for extra, status in combos:
        yield build_records_from_matches(
            league_id="championship",
            matches=pd.DataFrame([{"timestamp": ts}]), teams=None,
            league_df=pd.DataFrame([{**liga, **extra}]),
            _rows_override=[{
                "id": 1, "home_team_name": "Casa FC", "away_team_name": "Fora FC",
                "date_unix": ts, "timestamp": ts, "status": status,
            }],
            date_filter="today",
        )[0]


def chaves_escritas() -> Dict[str, Set[str]]:
    """Uniao das chaves que o record MONTADO realmente tem."""
    out: Dict[str, Set[str]] = {"record": set(), "stats": set(), "league_stats": set()}
    for r in _cenarios():
        out["record"] |= set(r)
        out["stats"] |= set(r.get("stats") or {})
        out["league_stats"] |= set(r.get("league_stats") or {})
    return out


def verificar() -> Dict[str, List[str]]:
    """Confronta leitura e escrita. `bloqueia` nao pode ir para producao."""
    lidas, escritas = chaves_lidas(), chaves_escritas()
    bloqueia: List[str] = []
    avisa: List[str] = []
    for portador in ("record", "stats", "league_stats"):
        for chave in sorted(lidas[portador] - escritas[portador]):
            if chave in OPCIONAIS:
                continue
            bloqueia.append(
                f"{portador}.get(\"{chave}\") — lida por um consumidor do record "
                f"e NUNCA escrita em nenhum cenario. Ou o produtor nao publica a "
                f"chave, ou o nome esta errado. Declare em OPCIONAIS com o motivo "
                f"se a ausencia for legitima."
            )
    for chave, motivo in OPCIONAIS.items():
        presente = any(chave in escritas[p] for p in escritas)
        lida = any(chave in lidas[p] for p in lidas)
        if not lida:
            avisa.append(f"{chave}: declarada OPCIONAL e nenhum consumidor a le mais — remova da lista.")
        elif presente:
            avisa.append(f"{chave}: declarada OPCIONAL e presente em todos os cenarios — promova para obrigatoria.")
    return {"bloqueia": bloqueia, "avisa": avisa}


def resumo() -> Dict[str, int]:
    lidas, escritas = chaves_lidas(), chaves_escritas()
    return {
        "lidas": sum(len(v) for v in lidas.values()),
        "escritas": sum(len(v) for v in escritas.values()),
        "opcionais_declaradas": len(OPCIONAIS),
        "bloqueia": len(verificar()["bloqueia"]),
    }
