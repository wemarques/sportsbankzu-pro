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
    r"Dupla\s+chance|DC\s*(?:1X|12|X2)",
]

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
    for pat in _MARKET_PATTERNS:
        for m in re.finditer(pat, text, re.IGNORECASE):
            mentioned.add(m.group())

    for mention in mentioned:
        if not _market_in_approved(mention, approved_markets):
            violations.append(
                f"Mercado fora da lista aprovada: '{mention.strip()}' "
                f"(aprovados: {sorted(approved_markets)})"
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
