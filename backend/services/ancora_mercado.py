# -*- coding: utf-8 -*-
"""#231 - fonte da probabilidade publicada: modelo ou mercado (flag PROB_SOURCE).

Passo 4 da regra #230, item 1. Decisao de produto (Welligton, 2026-09-03):
ancorar a probabilidade publicada no mercado de-vigado (#219) e usar o modelo
como ajuste minimo ou nenhum. Este modulo e a TROCA, atras de uma flag que
nasce desligada e SO pode ser ligada depois do gate da regra #230 (n >= 300
jogos no ledger, Brier do mercado < Brier da publicada com IC excluindo zero)
e dos itens 2 e 3 do passo 4 (EV contra preco justo, classificacao em valor +
confianca na ancora).

O que muda com `PROB_SOURCE=mercado`, por selecao do bundle:

  ancora de-vigada existe (devig / devig3, #230)  -> publicada = prob_mercado
                                                     prob_source = 'mercado'
  sem par, mas taxa-base da liga no mercado       -> publicada = taxa-base
                                                     prob_source = 'taxa_base'
  sem preco em fonte nenhuma e sem taxa-base      -> publicada = modelo
                                                     prob_source = 'modelo_sem_referencia'

Em todos os casos o valor do modelo fica em `model_probability`, e e ele que
o ledger continua gravando em `calibrated_prob` (a publicada vai para
`published_prob`). Sem isso, ligar a flag apagaria a propria medicao que
autoriza a flag.

`implicita` (1/odd de uma perna so) NAO serve de ancora: carrega a margem
inteira da casa (5-7 pp, #230-e). Quem nao tem par cai para a taxa-base.

EV (#232, item 2): `prob x odd` da mesma fonte e por construcao <= 0 (e o
de-vig ao contrario). Com a flag ligada o EV de TODA selecao passa a ser
p_justa(consenso entre casas, `match_data["odds_consenso"]`) x odd oferecida
- 1, ou None com o motivo em `ev_referencia`. A classificacao (#028/#042)
NAO e tocada aqui — item 3.

Com a flag desligada (padrao) nada neste modulo roda e o payload e identico
ao anterior, byte a byte (teste test_231_prob_source.py).
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("sportsbankzu.ancora")

FLAG = "PROB_SOURCE"
FONTES_VALIDAS = ("modelo", "mercado")

# Metodos da ancora que servem de probabilidade publicada. `implicita` fica
# de fora de proposito (margem inteira dentro) — mesma regra do comparador
# (`_METODOS_JUSTOS` em scripts/comparar_com_mercado.py).
METODOS_JUSTOS = ("devig", "devig3")

# Artefato de taxas-base por (liga, mercado, selecao), gerado a partir do
# backfill (#227) por `scripts/gerar_taxas_base.py`. Nao vive no repo: vem
# da chave da FootyStats, na maquina do Welligton.
_ARTEFATO_PADRAO = Path(__file__).resolve().parents[1] / "config" / "taxas_base.json"
MIN_N_TAXA_BASE = 30          # mesma regra do comparador (#230-d)

_cache_taxas: Optional[Dict[str, Any]] = None
_cache_caminho: Optional[str] = None


def fonte_configurada() -> str:
    """Le a flag. Valor desconhecido = 'modelo', com aviso (nunca falha)."""
    valor = (os.getenv(FLAG, "modelo") or "modelo").strip().lower() or "modelo"
    if valor not in FONTES_VALIDAS:
        logger.warning("[#231] %s=%r desconhecido; usando 'modelo'", FLAG, valor)
        return "modelo"
    return valor


def ancora_ligada() -> bool:
    return fonte_configurada() == "mercado"


# ── taxa-base ────────────────────────────────────────────────────────────
def _caminho_artefato() -> str:
    return (os.getenv("TAXAS_BASE_PATH") or "").strip() or str(_ARTEFATO_PADRAO)


def carregar_taxas_base(caminho: Optional[str] = None) -> Dict[str, Any]:
    """Carrega o artefato uma vez. Ausente ou invalido -> {} (sem taxa-base)."""
    global _cache_taxas, _cache_caminho
    caminho = caminho or _caminho_artefato()
    if _cache_taxas is not None and _cache_caminho == caminho:
        return _cache_taxas
    dados: Dict[str, Any] = {}
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            bruto = json.load(f)
        if isinstance(bruto, dict) and isinstance(bruto.get("celulas"), dict):
            dados = bruto
        else:
            logger.warning("[#231] artefato de taxas-base sem 'celulas': %s", caminho)
    except FileNotFoundError:
        logger.info("[#231] sem artefato de taxas-base em %s", caminho)
    except Exception as e:                                   # noqa: BLE001
        logger.warning("[#231] artefato de taxas-base ilegivel (%s): %s", caminho, e)
    _cache_taxas, _cache_caminho = dados, caminho
    return dados


def limpar_cache_taxas() -> None:
    global _cache_taxas, _cache_caminho
    _cache_taxas, _cache_caminho = None, None


def chave_celula(market: str, selection: str) -> str:
    return f"{(market or '').strip()}|{(selection or '').strip()}"


def taxa_base(league_id: Optional[str], market: str, selection: str,
              taxas: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """Taxa-base da celula, com a mesma hierarquia do comparador (#230-d):
    (liga, mercado, selecao) com n >= MIN_N_TAXA_BASE, senao (*, mercado,
    selecao), senao None. Devolve {'taxa', 'n', 'nivel'}."""
    taxas = carregar_taxas_base() if taxas is None else taxas
    celulas = taxas.get("celulas") if isinstance(taxas, dict) else None
    if not celulas:
        return None
    minimo = int(taxas.get("min_n") or MIN_N_TAXA_BASE)
    chave = chave_celula(market, selection)
    for nivel in ((league_id or "").strip(), "*"):
        if not nivel:
            continue
        cel = (celulas.get(nivel) or {}).get(chave)
        if not isinstance(cel, dict):
            continue
        try:
            n, taxa = int(cel.get("n") or 0), float(cel.get("taxa"))
        except (TypeError, ValueError):
            continue
        if n >= minimo and 0.0 < taxa < 1.0:
            return {"taxa": taxa, "n": n, "nivel": nivel}
    return None


# ── a troca ──────────────────────────────────────────────────────────────
def aplicar_ancora(bundle, match_data: Optional[Dict[str, Any]] = None,
                   league_id: Optional[str] = None) -> Dict[str, int]:
    """Troca a probabilidade publicada de cada selecao do bundle, no lugar.

    So faz algo com `PROB_SOURCE=mercado`. Devolve a contagem por fonte
    (para o log e para o teste). Nunca levanta: falha aberta por selecao.
    """
    contagem = {"mercado": 0, "taxa_base": 0, "modelo_sem_referencia": 0}
    if not ancora_ligada():
        return contagem
    from backend.services.prediction_ledger import prob_mercado_do_pick

    match_data = match_data or {}
    odds = (match_data.get("odds") or {}) if isinstance(match_data, dict) else {}
    consenso = (match_data.get("odds_consenso") or {}) if isinstance(match_data, dict) else {}
    liga = league_id or getattr(bundle, "league_id", None)

    for m in getattr(bundle, "markets", []) or []:
        try:
            _trocar_uma(m, odds, liga, prob_mercado_do_pick, contagem)
            _ev_uma(m, consenso)
            _classificar_uma(m, liga)
        except Exception as e:                               # noqa: BLE001
            logger.warning("[#231] ancora falhou em %s %s: %s",
                           getattr(m, "market_type", "?"), getattr(m, "selection", "?"), e)
    # #233: a elegibilidade para multiplas segue a classificacao nova
    try:
        from backend.models.market_output import MarketClassification as _MC
        bundle.eligible_for_multiples = any(
            m.classification in (_MC.SAFE, _MC.NEUTRO_QUALIFICADO) and m.odds_available
            for m in getattr(bundle, "markets", []) or []
        )
    except Exception as e:                                   # noqa: BLE001
        logger.debug("[#233] elegibilidade nao recalculada: %s", e)
    logger.info("[#231] PROB_SOURCE=mercado jogo=%s liga=%s fontes=%s",
                getattr(bundle, "match_id", "?"), liga, contagem)
    return contagem


def _trocar_uma(m, odds, liga, prob_mercado_do_pick, contagem) -> None:
    market = getattr(m, "market_type", "") or ""
    selection = getattr(m, "selection", "") or ""
    modelo = m.calibrated_probability if m.calibrated_probability is not None else m.raw_probability
    m.model_probability = modelo

    ancora = prob_mercado_do_pick(market, selection, odds)
    m.ancora_referencia = {                                  # #233
        "metodo": ancora.get("mercado_metodo"), "margem_pp": ancora.get("margem_pp"),
        "frescor": ancora.get("frescor"), "odd_par": ancora.get("odd_par"),
    }
    nova: Optional[float] = None
    fonte = "modelo_sem_referencia"
    if ancora.get("mercado_metodo") in METODOS_JUSTOS and ancora.get("prob_mercado"):
        nova, fonte = float(ancora["prob_mercado"]), "mercado"
    else:
        tb = taxa_base(liga, market, selection)
        if tb is not None:
            nova, fonte = tb["taxa"], "taxa_base"

    m.prob_source = fonte
    contagem[fonte] += 1
    if nova is None:
        return                      # modelo fica, rotulado como sem referencia
    m.calibrated_probability = round(nova, 6)
    m.compute_display()


def _ev_uma(m, consenso_do_jogo: Dict[str, Any]) -> None:
    """#232 - EV contra o preco justo de consenso entre casas.

    Vale para TODA selecao com a flag ligada, seja qual for a fonte da
    probabilidade publicada: a odd oferecida e comparada com o consenso da
    API-Football, nunca com a probabilidade que saiu da mesma fonte da odd.
    Sem consenso (>= MIN_CASAS_CONSENSO casas) nao ha EV, e o motivo fica em
    `ev_referencia`.
    """
    from backend.services.consenso_odds import chave_da_selecao, ev_contra_consenso
    chave = chave_da_selecao(getattr(m, "market_type", "") or "", getattr(m, "selection", "") or "")
    cons = consenso_do_jogo.get(chave) if chave else None
    r = ev_contra_consenso(m.book_odd, cons)
    m.ev, m.edge, m.ev_referencia = r["ev"], r["edge"], r["referencia"]


# ── #233 - classificacao em valor + confianca na ancora ──────────────────
def _classificar_uma(m, league_id: Optional[str]) -> None:
    """Refaz SAFE / NEUTRO_QUALIFICADO / NEUTRO / NO_BET com a fonte trocada.

    Dois eixos, nenhum numero novo:
      valor     — `ev`/`edge` contra o consenso entre casas (#232), com os
                  MESMOS limiares por mercado e liga de `classify_market`
                  (safe_ev/safe_edge/neutro_ev, NEUTRO_QUALIFICADO_THRESHOLDS,
                  EV_FLOOR #165, MAX_CREDIBLE_EV #116) e o circuit breaker de
                  SAFE por liga (#043/#052) com shadow mode (#129c);
      confianca — de onde veio a probabilidade publicada e em que estado:
                  `mercado` com frescor ok (#219) e a unica fonte que pode
                  chegar a SAFE/NQ; `mercado` com odd velha, `taxa_base` e
                  `modelo_sem_referencia` param em NEUTRO, rotulados.
    A probabilidade comparada com safe_prob/neutro_prob e a PUBLICADA (a que
    o usuario ve), nao a raw do modelo como no #106 — com a fonte trocada a
    raw do modelo nao e mais a confianca do que se publica.
    """
    from backend.models.market_output import MarketClassification as MC, ReasonCode as RC
    from backend.services import ev_classification as EVC

    th = EVC._get_thresholds(EVC._market_category(m.market_type), league_id=league_id)
    p = m.calibrated_probability or 0.0
    q = m.data_quality_score or 0.0
    fonte = m.prob_source
    frescor_ok = fonte == "mercado" and (m.ancora_referencia or {}).get("frescor") == "ok"
    codes = []

    # confianca na ancora
    if fonte == "mercado":
        codes.append(RC.ANCHOR_MARKET if frescor_ok else RC.ANCHOR_STALE)
    elif fonte == "taxa_base":
        codes.append(RC.BASE_RATE_ONLY)
    else:
        codes.append(RC.MODEL_ONLY)
    if q < th.get("min_quality", 0.3):
        codes.append(RC.LOW_DATA_QUALITY)
    if not m.odds_available:
        codes.append(RC.NO_ODDS_AVAILABLE)

    # valor
    ev, edge = m.ev, m.edge
    if ev is not None and ev > EVC.MAX_CREDIBLE_EV:            # #116: linha velha na casa
        codes.append(RC.SUSPICIOUS_EV)
        m.ev, m.edge = None, None
        ev, edge = None, None
    if ev is None:
        if m.odds_available:
            codes.append(RC.NO_VALUE_REFERENCE)
    elif ev < 0:
        codes.append(RC.NEGATIVE_EV)
    elif ev >= th.get("safe_ev", 0.05):
        codes.append(RC.POSITIVE_EV)
    if edge is not None:
        if edge < th.get("neutro_edge", 0.01):
            codes.append(RC.INSUFFICIENT_EDGE)
        elif edge >= th.get("safe_edge", 0.04):
            codes.append(RC.STRONG_EDGE)
    if p >= th.get("safe_prob", 0.60):
        codes.append(RC.HIGH_CALIBRATED_PROB)

    cls = MC.NO_BET
    prob_neutro = p >= th.get("neutro_prob", 0.50) and q >= th.get("min_quality", 0.3) * 0.8
    prob_safe = p >= th.get("safe_prob", 0.60) and q >= th.get("min_quality", 0.3)
    if ev is None:
        # sem medida de valor: no maximo informativo, e so com probabilidade
        if prob_neutro:
            cls = MC.NEUTRO
    elif ev < 0:
        cls = MC.NO_BET
    elif ev < EVC.EV_FLOOR:                                     # #165
        cls = MC.NO_BET
        codes.append(RC.EV_FLOOR_DROP)
    else:
        if prob_safe and frescor_ok and edge is not None \
                and ev >= th.get("safe_ev", 0.05) and edge >= th.get("safe_edge", 0.04):
            cls = MC.SAFE
        elif prob_neutro and ev >= th.get("neutro_ev", 0.0):
            cls = MC.NEUTRO
            if frescor_ok and RC.SUSPICIOUS_EV not in codes \
                    and EVC._is_neutro_qualificado(m, p):
                cls = MC.NEUTRO_QUALIFICADO

    # so a ancora de mercado fresca sustenta SAFE/NQ
    if cls in (MC.SAFE, MC.NEUTRO_QUALIFICADO) and not frescor_ok:
        cls = MC.NEUTRO

    # circuit breaker de SAFE por liga (#043/#052) + shadow (#129c)
    if cls == MC.SAFE and not EVC._is_safe_enabled(league_id):
        if EVC.SAFE_SHADOW_MODE:
            EVC._shadow_logger.info(
                f"SHADOW_SAFE|{m.display_label}|league={league_id}|fonte={fonte}|"
                f"pub={m.calibrated_probability}|modelo={m.model_probability}|odd={m.book_odd}|ev={m.ev}"
            )
            m.source_flags = list(m.source_flags or []) + ["shadow_safe"]
        cls = MC.NEUTRO_QUALIFICADO
        codes.append(RC.SAFE_CIRCUIT_BREAKER)

    m.classification = cls
    m.reason_codes = codes

