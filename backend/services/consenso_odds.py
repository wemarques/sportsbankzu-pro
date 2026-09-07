# -*- coding: utf-8 -*-
"""#232 - preco justo de CONSENSO entre casas (item 2 do passo 4 do #230).

Regra #230: "EV passa a ser distancia entre odd oferecida e preco justo
(entre casas, #120), nunca prob x odd da mesma casa". Com a ancora do #231 a
probabilidade publicada e o de-vig do par da FootyStats; multiplicar essa
probabilidade pela odd da mesma fonte e desfazer o de-vig — EV <= 0 por
construcao. O preco justo independente vem daqui: a resposta inteira do
/odds da API-Football (todas as casas), que o enriquecimento #120 ja busca e
de que so aproveitava a primeira casa da prioridade.

Por casa: o MESMO parser do `extract_best_odds` (`_parse_bets_into`, #187 —
familia inteira de uma unica bet, escada coerente), num dict novo. Por
selecao: de-vig Shin (#219) do par daquela casa (trio para 1X2, soma de duas
pernas para DC). Consenso = MEDIANA das probabilidades justas entre casas
(robusta a uma casa com linha velha), com n_casas, odd mediana e odd maxima.

Chaves de saida = nomes REAIS do `odds` do record (`over25`, `bttsYes`,
`cornersOver95`, `cards_over_3.5`, `home`, `dc_1x`), para a mesma
`chave_da_selecao(market, selection)` servir a ancora e ao EV.
"""
from __future__ import annotations

import logging
import re
import statistics
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("sportsbankzu.consenso")

MIN_CASAS_CONSENSO = 3      # abaixo disso nao e consenso, e uma casa com eco

_LINHAS_GOLS = ("05", "15", "25", "35", "45", "55")
_LINHAS_ESC = ("45", "55", "65", "75", "85", "95", "105", "115", "125")
_LINHAS_CART = ("15", "25", "35", "45", "55", "65")


def _pares_af() -> List[Tuple[str, str, str, str]]:
    """(chave_record_A, chave_record_B, chave_af_A, chave_af_B) de cada par 2 pernas."""
    pares = []
    for l in _LINHAS_GOLS:
        pares.append((f"over{l}", f"under{l}", f"over_{l}", f"under_{l}"))
    pares.append(("bttsYes", "bttsNo", "btts_yes", "btts_no"))
    for l in _LINHAS_ESC:
        pares.append((f"cornersOver{l}", f"cornersUnder{l}", f"corners_over_{l}", f"corners_under_{l}"))
    for l in _LINHAS_CART:
        ponto = f"{l[0]}.{l[1]}"
        pares.append((f"cards_over_{ponto}", f"cards_under_{ponto}", f"cards_over_{l}", f"cards_under_{l}"))
    return pares


_PARES = _pares_af()
_DC = {"dc_1x": (0, 1), "dc_12": (0, 2), "dc_x2": (1, 2)}
_1X2 = ("home", "draw", "away")


def _odd(v: Any) -> Optional[float]:
    try:
        f = float(v or 0)
    except (TypeError, ValueError):
        return None
    return f if f > 1.0 else None


def _justas_de_uma_casa(flat: Dict[str, Any]) -> Dict[str, Tuple[float, float]]:
    """{chave_record: (prob_justa, odd_oferecida)} para o que esta casa cota em par."""
    from backend.services.devig import devig
    out: Dict[str, Tuple[float, float]] = {}
    for ra, rb, aa, ab in _PARES:
        oa, ob = _odd(flat.get(aa)), _odd(flat.get(ab))
        if oa is None or ob is None:
            continue
        j = devig([oa, ob])
        if j and 0.0 < j[0] < 1.0 and 0.0 < j[1] < 1.0:
            out[ra] = (j[0], oa)
            out[rb] = (j[1], ob)
    trio = [_odd(flat.get(k)) for k in _1X2]
    if all(t is not None for t in trio):
        j = devig(trio)                                  # type: ignore[arg-type]
        if j and len(j) == 3 and all(0.0 < x < 1.0 for x in j):
            for i, k in enumerate(_1X2):
                out[k] = (j[i], trio[i])                 # type: ignore[index]
            for k, (i, m) in _DC.items():
                od = _odd(flat.get(k))
                if od is not None:
                    out[k] = (j[i] + j[m], od)
    return out


def consenso_por_selecao(af_odds: Optional[List[Dict[str, Any]]]) -> Dict[str, Dict[str, Any]]:
    """Consenso entre casas a partir da resposta crua do /odds da API-Football.

    Devolve {chave_record: {"p_justa", "n_casas", "odd_mediana", "odd_max",
    "casa_max"}}. Uma casa entra uma vez (paginacao repete casas). Sem
    resposta ou sem par em casa nenhuma -> {}.
    """
    if not af_odds:
        return {}
    from backend.services.api_football_client import _parse_bets_into

    vistas = set()
    por_chave: Dict[str, List[Tuple[float, float, str]]] = {}
    for entrada in af_odds:
        for casa in (entrada or {}).get("bookmakers", []) or []:
            nome = str(casa.get("name") or "").strip()
            if not nome or nome.lower() in vistas:
                continue
            vistas.add(nome.lower())
            flat: Dict[str, Any] = {}
            try:
                _parse_bets_into(nome, casa.get("bets", []) or [], flat)
            except Exception as e:                          # noqa: BLE001
                logger.debug("[#232] casa %s ilegivel: %s", nome, e)
                continue
            for chave, (p, od) in _justas_de_uma_casa(flat).items():
                por_chave.setdefault(chave, []).append((p, od, nome))

    saida: Dict[str, Dict[str, Any]] = {}
    for chave, itens in por_chave.items():
        probs = [p for p, _, _ in itens]
        odds = [o for _, o, _ in itens]
        i_max = max(range(len(itens)), key=lambda i: itens[i][1])
        saida[chave] = {
            "p_justa": round(statistics.median(probs), 6),
            "n_casas": len(itens),
            "odd_mediana": round(statistics.median(odds), 3),
            "odd_max": round(itens[i_max][1], 3),
            "casa_max": itens[i_max][2],
        }
    return saida


# ── a mesma chave para ancora e EV ───────────────────────────────────────
_RE_LINHA = re.compile(r"(\d+\.5)")


def chave_da_selecao(market: str, selection: str) -> Optional[str]:
    """(market_type, selection) do MarketOutput -> chave do `odds` do record.

    Espelha `prediction_ledger.par_de_odds` (mesmos nomes, #230). Sem chave
    conhecida -> None.
    """
    m = (market or "").strip()
    s = (selection or "").strip()
    sl = s.lower()
    mm = _RE_LINHA.search(s)
    linha = mm.group(1) if mm else None
    sfx = linha.replace(".", "") if linha else None
    if m == "Over/Under" and sfx:
        return f"{'over' if sl.startswith('over') else 'under'}{sfx}"
    if m == "BTTS":
        return "bttsYes" if "yes" in sl else "bttsNo"
    if m == "Corners" and sfx:
        return f"corners{'Over' if 'over' in sl else 'Under'}{sfx}"
    if m == "Cards" and linha:
        return f"cards_{'over' if 'over' in sl else 'under'}_{linha}"
    if m == "1X2" and sl in _1X2:
        return sl
    if m == "Double Chance":
        k = "dc_" + sl.replace("dc", "").strip().replace(" ", "")
        return k if k in _DC else None
    return None


def ev_contra_consenso(book_odd: Optional[float], consenso: Optional[Dict[str, Any]],
                       min_casas: int = MIN_CASAS_CONSENSO) -> Dict[str, Any]:
    """EV = p_justa(consenso) x odd_oferecida - 1, ou o motivo de nao haver EV.

    Devolve {"ev", "edge", "referencia"}; `referencia` sempre existe e diz a
    fonte (consenso, n_casas, p_justa, odd_mediana, odd_max) ou o motivo
    (`sem_odd`, `sem_consenso`, `poucas_casas`).
    """
    od = _odd(book_odd)
    if od is None:
        return {"ev": None, "edge": None, "referencia": {"fonte": None, "motivo": "sem_odd"}}
    if not consenso or consenso.get("p_justa") is None:
        return {"ev": None, "edge": None, "referencia": {"fonte": None, "motivo": "sem_consenso"}}
    n = int(consenso.get("n_casas") or 0)
    if n < min_casas:
        return {"ev": None, "edge": None,
                "referencia": {"fonte": None, "motivo": "poucas_casas", "n_casas": n}}
    p = float(consenso["p_justa"])
    return {
        "ev": round(p * od - 1.0, 4),
        "edge": round(p - 1.0 / od, 4),
        "referencia": {
            "fonte": "consenso", "n_casas": n, "p_justa": p,
            "odd_mediana": consenso.get("odd_mediana"), "odd_max": consenso.get("odd_max"),
        },
    }
