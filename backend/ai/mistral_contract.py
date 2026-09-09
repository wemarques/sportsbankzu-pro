"""Mistral input/output contract — #181.

Reinforces regra #082 (Mistral exclusivamente narrativa) by validating the
narrative text against the system's approved picks list and detecting
forbidden behaviors (computing EV, suggesting markets outside the list).

Diagnostic context (do not delete):
- Bug observed 2026-05-04 (Sporting CP x Vitoria Guimaraes): Mistral text
  mentioned "Under 3.5 odd 1.67 prob 70% EV +16.9%" while display showed
  "Under 3.5 odd 1.70 prob 56-58%". Gap ~13pp = exact deflation amount
  for the 50-60% band per regra #105.
- Root cause: prompt at mistral_analysis.py:208-216 receives raw probs
  (homeWinProb / over25Prob / bttsProb), pre-deflation; display reads
  deflated values from mercados[].prob_max in the same record.
- Camada 6 (_validate_recommendation_vs_pipeline) only inspects
  recomendacao_principal (single string) and only checks Over/Under
  direction conflicts — does NOT inspect resumo_analitico / key_points
  where the offending narrative actually lives. Hence this contract
  validates the FULL TEXT.

This module deliberately omits retry logic at Mistral call sites — fix
#181 ships observability first; retry/fallback policy is a follow-up
once we have data on actual violation frequency.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional
import logging
import re

logger = logging.getLogger("sportsbankzu.mistral.contract")


@dataclass(frozen=True)
class ApprovedPick:
    """A pick already classified by the pipeline. Mistral may only narrate these.

    `prob_deflated_pct`/`odd`/`ev_pct` MUST match the values shown to the
    operator on the dashboard. Passing raw probabilities here defeats the
    purpose of the contract.
    """
    market: str               # canonical label, e.g. "Under 3.5 gols"
    classification: str       # SAFE / NEUTRO_QUALIFICADO / NEUTRO / VIAVEL
    prob_deflated_pct: float  # deflated (post #105), what user sees
    odd: float                # book_odd shown to user
    ev_pct: float             # already computed by ev_classification

    def short_label(self) -> str:
        return (
            f"{self.classification} | {self.market} | "
            f"{self.prob_deflated_pct:.1f}% | odd {self.odd:.2f} | EV {self.ev_pct:+.1f}%"
        )


# ---- Output validation ------------------------------------------------------

# Markets that may legitimately appear in narrative text. Used to detect when
# Mistral suggests something OUTSIDE the approved list.
_MARKET_PATTERNS = [
    r"Over\s+\d+\.?\d*\s+gols?",
    r"Under\s+\d+\.?\d*\s+gols?",
    r"BTTS\s*[—–-]?\s*(?:SIM|N[AAÃ]O)",
    r"Escanteios?\s+(?:Over|Under)\s+\d+\.?\d*",
    r"Cart[ãa]o?(?:es|oes)?\s+(?:Over|Under)\s+\d+\.?\d*",
    r"Dupla\s+chance(?:\s*(?:1X|12|X2))?|DC\s*(?:1X|12|X2)",
    # Variante em inglês observada em produção (KRC Genk 2026-08-28):
    # "Double Chance 1X (odd 1.14)" passou sem detecção pelo padrão "DC".
    r"Double\s+Chance(?:\s*(?:1X|12|X2))?",
    r"\b1X2\b(?:\s*(?:Home|Away|Casa|Fora))?",
    # #238-a: mencao NUA de linha, sem a familia colada. Observado em producao
    # (Toronto x Nashville, 2026-09-09): "over 2.5 em 57.5% dos jogos" e
    # "over 8.5 em 67.9%" — nenhum dos dois casava, porque o padrao de gols
    # exige "gols" logo apos o numero e o de escanteios exige "Escanteios"
    # logo antes. Duas mencoes de mercado num paragrafo, zero violacoes.
    # `_market_in_approved` compara por substring nos dois sentidos, entao
    # "over 8.5" continua casando com "Escanteios Over 8.5" aprovado — este
    # padrao so ACRESCENTA deteccao, nunca remove.
    r"\b(?:Over|Under)\s+\d+\.?\d*\b",
]

# #238-a — probabilidade citada ao lado de um mercado.
#
# O contrato do #181 diz que a narrativa so pode citar a probabilidade
# DEFLACIONADA. Ate aqui nada verificava isso: `validate_output` olhava QUAIS
# mercados apareciam, nunca COM QUE NUMERO. No caso que motivou esta camada, o
# prompt entrega `- Prob Over 2.5: 57.5% (raw)` — rotulado como raw, no meio das
# estatisticas — e o texto saiu com "over 2.5 em 57.5% dos jogos". Deflacionada,
# essa linha vale ~52%.
#
# Regra: um percentual ate 40 caracteres depois de uma mencao de mercado e
# tratado como probabilidade DAQUELE mercado e tem de bater com a publicada
# (tolerancia de 1 ponto, para absorver o arredondamento do card). Percentual
# solto no texto ("clean sheet de 48%") nao e tocado — nao esta colado a
# mercado nenhum.
_JANELA_PROB = 40
_PERCENTUAL = re.compile(r"(\d+[\.,]?\d*)\s*%")
_TOLERANCIA_PP = 1.0

# Pattern for "Mistral computed EV" — narrative must NEVER assert EV.
# System computes EV; narrative narrates context.
_EV_COMPUTATION_PATTERN = re.compile(r"EV\s*[+\-]?\s*\d+[\.,]?\d*\s*%", re.IGNORECASE)


def _market_in_approved(mention: str, approved_markets: set[str]) -> bool:
    """Fuzzy-match a market mention against the approved set."""
    mention_norm = mention.strip().lower()
    if not mention_norm:
        return True  # empty mentions never count as violations
    for am in approved_markets:
        am_norm = am.strip().lower()
        if not am_norm:
            continue
        # Substring match in either direction handles minor variations
        # ("Under 3.5" vs "Under 3.5 gols").
        if am_norm in mention_norm or mention_norm in am_norm:
            return True
    return False


def validate_output(text: str, approved: List[ApprovedPick]) -> dict:
    """Inspect the FULL Mistral narrative for contract violations.

    Concatenate `resumo_analitico + key_points` into a single string and
    pass here. Returns `{ok, violations}`.

    Violations are reported but not auto-fixed — caller decides whether
    to log, retry, or fallback. #181 ships log-only by default.
    """
    violations: list[str] = []
    if not text:
        return {"ok": True, "violations": violations}

    approved_markets = {p.market for p in approved}
    mentioned: set[str] = set()
    ocorrencias: list[tuple[str, int]] = []          # #238-a: (mencao, fim)
    for pat in _MARKET_PATTERNS:
        for m in re.finditer(pat, text, re.IGNORECASE):
            mentioned.add(m.group())
            ocorrencias.append((m.group(), m.end()))

    for mention in mentioned:
        if not _market_in_approved(mention, approved_markets):
            violations.append(
                f"Mercado fora da lista aprovada: '{mention.strip()}' "
                f"(aprovados: {sorted(approved_markets)})"
            )

    # #238-a — o numero citado ao lado do mercado tem de ser o PUBLICADO.
    publicadas = {
        round(float(p.prob_deflated_pct), 1)
        for p in approved
        if p.prob_deflated_pct is not None
    }
    ja_reportado: set[tuple[str, str]] = set()
    for mencao, fim in ocorrencias:
        m = _PERCENTUAL.search(text[fim:fim + _JANELA_PROB])
        if not m:
            continue
        try:
            citada = float(m.group(1).replace(",", "."))
        except ValueError:
            continue
        if any(abs(citada - p) <= _TOLERANCIA_PP for p in publicadas):
            continue
        chave = (mencao.strip().lower(), m.group(1))
        if chave in ja_reportado:
            continue
        ja_reportado.add(chave)
        violations.append(
            f"Probabilidade citada nao e a publicada: '{mencao.strip()}' com "
            f"{citada}% (publicadas: {sorted(publicadas) or 'nenhuma'}) — "
            f"a narrativa so pode citar a probabilidade deflacionada (#181)"
        )

    if _EV_COMPUTATION_PATTERN.search(text):
        violations.append(
            "Mistral computou EV no texto narrativo — proibido (regra #146); "
            "system computa EV, narrativa narra contexto."
        )

    return {"ok": len(violations) == 0, "violations": violations}


def log_violations(violations: list[str], match_label: Optional[str] = None) -> None:
    """Log violations through the standard logger so they show up on CloudWatch."""
    if not violations:
        return
    prefix = f"[Mistral #181 violation] match={match_label or '?'}"
    for v in violations:
        logger.warning(f"{prefix}: {v}")


def aligned_recommendation(approved: List[ApprovedPick]) -> str:
    """Recomendação determinística construída a partir dos picks aprovados.

    Usada como substituição quando a recomendacao_principal do Mistral
    viola o contrato (cita mercado fora da lista aprovada, i.e. rejeitado
    pela tabela de EV deflacionado). Consome exatamente os mesmos valores
    exibidos na tabela de mercados — nunca contradiz o display.
    """
    if not approved:
        return (
            "Sem recomendação — nenhum mercado com EV positivo após deflação "
            "para este jogo. Consulte a tabela de mercados analisados."
        )
    top = max(approved, key=lambda p: p.ev_pct)
    return (
        f"Recomendação alinhada ao pipeline: {top.market} "
        f"({top.prob_deflated_pct:.0f}%, odd {top.odd:.2f}, EV {top.ev_pct:+.1f}%) — "
        f"mercado com maior EV após deflação entre os aprovados pelo sistema."
    )


def fallback_narrative(approved: List[ApprovedPick]) -> str:
    """Neutral narrative used when (future) retry logic gives up.

    Currently NOT auto-invoked by analyze_match — kept here for the
    follow-up fix that wires retry+fallback once violation frequency
    is measured.
    """
    if not approved:
        return "Sem picks aprovados pelo sistema para este jogo."
    top = approved[0]
    return (
        f"O sistema identificou {len(approved)} oportunidade(s) neste jogo. "
        f"Pick principal: {top.market} ({top.prob_deflated_pct:.0f}%, "
        f"odd {top.odd:.2f}, EV {top.ev_pct:+.1f}%). "
        f"Análise narrativa detalhada temporariamente indisponível."
    )
