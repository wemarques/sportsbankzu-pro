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

EV: com a probabilidade vinda do mercado, `prob x odd` da mesma casa e por
construcao <= 0 (e o de-vig ao contrario). O EV fica None ate o item 2
redefini-lo como distancia entre a odd oferecida e o preco justo entre casas.
A classificacao (#028/#042) NAO e tocada aqui — item 3.

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
    liga = league_id or getattr(bundle, "league_id", None)

    for m in getattr(bundle, "markets", []) or []:
        try:
            _trocar_uma(m, odds, liga, prob_mercado_do_pick, contagem)
        except Exception as e:                               # noqa: BLE001
            logger.warning("[#231] ancora falhou em %s %s: %s",
                           getattr(m, "market_type", "?"), getattr(m, "selection", "?"), e)
    logger.info("[#231] PROB_SOURCE=mercado jogo=%s liga=%s fontes=%s",
                getattr(bundle, "match_id", "?"), liga, contagem)
    return contagem


def _trocar_uma(m, odds, liga, prob_mercado_do_pick, contagem) -> None:
    market = getattr(m, "market_type", "") or ""
    selection = getattr(m, "selection", "") or ""
    modelo = m.calibrated_probability if m.calibrated_probability is not None else m.raw_probability
    m.model_probability = modelo

    ancora = prob_mercado_do_pick(market, selection, odds)
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
    # ver docstring do modulo: prob x odd da mesma casa nao e EV. Item 2.
    m.ev = None
    m.edge = None
