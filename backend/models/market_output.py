"""
Unified Market Output Contract (Layer 1 — Data Governance)

Every market prediction flows through this contract before reaching the UI.
This ensures consistent fields regardless of the source market type.
"""

from enum import Enum
from typing import List, Optional
from pydantic import AliasChoices, BaseModel, Field


class MarketClassification(str, Enum):
    SAFE = "SAFE"
    NEUTRO_QUALIFICADO = "NEUTRO_QUALIFICADO"
    NEUTRO = "NEUTRO"
    NO_BET = "NO_BET"


class ReasonCode(str, Enum):
    LOW_DATA_QUALITY = "LOW_DATA_QUALITY"
    NO_ODDS_AVAILABLE = "NO_ODDS_AVAILABLE"
    NEGATIVE_EV = "NEGATIVE_EV"
    INSUFFICIENT_EDGE = "INSUFFICIENT_EDGE"
    EARLY_SEASON_FALLBACK = "EARLY_SEASON_FALLBACK"
    HIGH_MARKET_CORRELATION = "HIGH_MARKET_CORRELATION"
    LINEUP_UNCERTAINTY = "LINEUP_UNCERTAINTY"
    HIGH_PREDICTION_RISK = "HIGH_PREDICTION_RISK"
    REGIME_BLOCKED = "REGIME_BLOCKED"
    POSITIVE_EV = "POSITIVE_EV"
    STRONG_EDGE = "STRONG_EDGE"
    HIGH_CALIBRATED_PROB = "HIGH_CALIBRATED_PROB"
    ODDS_TOO_LOW = "ODDS_TOO_LOW"
    STABLE_MARKET = "STABLE_MARKET"
    VOLATILE_MARKET = "VOLATILE_MARKET"
    COVERAGE_INSUFFICIENT = "COVERAGE_INSUFFICIENT"
    SUSPICIOUS_EV = "SUSPICIOUS_EV"
    SAFE_CIRCUIT_BREAKER = "SAFE_CIRCUIT_BREAKER"
    BORDERLINE_LINE_MARGIN = "BORDERLINE_LINE_MARGIN"  # #120
    DIRECTION_AGAINST_PROJFT = "DIRECTION_AGAINST_PROJFT"  # #123
    DIRECTION_NATURAL_MATCH = "DIRECTION_NATURAL_MATCH"  # #126


class MarketOutput(BaseModel):
    """Unified output contract for any market prediction."""
    market_type: str = Field(..., description="e.g. '1X2', 'Over/Under', 'BTTS', 'Double Chance', 'Corners'")
    selection: str = Field(..., description="e.g. 'Home', 'Over 2.5', 'BTTS Yes', 'DC 1X', 'Corners Over 9.5'")

    # Probabilities
    raw_probability: Optional[float] = Field(None, description="Raw model probability (0-1)")
    calibrated_probability: Optional[float] = Field(None, description="Calibrated probability (0-1)")

    # Odds
    fair_odd: Optional[float] = Field(None, description="1 / calibrated_probability")
    book_odd: Optional[float] = Field(None, description="Real bookmaker odd, if available")

    # EV
    ev: Optional[float] = Field(None, description="Expected value = (prob * odd) - 1, only when book_odd available")
    edge: Optional[float] = Field(None, description="prob - implied_prob, only when book_odd available")

    # Classification
    classification: MarketClassification = MarketClassification.NO_BET
    reason_codes: List[ReasonCode] = []

    # Quality & availability
    data_quality_score: float = Field(0.0, description="0-1 quality score for the underlying data")
    odds_available: bool = Field(False, description="Whether real book odds were found")
    source_flags: List[str] = Field(default_factory=list, description="e.g. ['footystats', 'api_football']")

    # Display helpers
    display_label: str = ""
    prob_min_pct: int = 0
    prob_max_pct: int = 0

    # Corner governance (populated for marketFamily=corners)
    corner_governance: Optional[dict] = Field(
        None,
        exclude=True,
        validation_alias=AliasChoices("corner_governance", "_corner_governance"),
    )

    def compute_display(self) -> None:
        """Compute display helpers from probabilities."""
        prob = self.calibrated_probability or self.raw_probability
        if prob and prob > 0:
            self.prob_max_pct = int(prob * 100)
            self.prob_min_pct = max(0, self.prob_max_pct - 2)
            self.fair_odd = round(1.0 / prob, 2)

    def compute_ev(self) -> None:
        """Compute EV and edge from calibrated probability and book odd."""
        prob = self.calibrated_probability or self.raw_probability
        if prob and prob > 0 and self.book_odd and self.book_odd > 1.0:
            self.odds_available = True
            implied = 1.0 / self.book_odd
            self.ev = round(prob * self.book_odd - 1.0, 4)
            self.edge = round(prob - implied, 4)
        else:
            self.ev = None
            self.edge = None

    def to_legacy_mercado(self) -> dict:
        """Convert to legacy mercado dict for backward compatibility."""
        result = {
            "mercado": self.display_label or self.selection,
            "status": self._legacy_status(),
            "prob_min": self.prob_min_pct,
            "prob_max": self.prob_max_pct,
            "odd_minima": self.book_odd or self.fair_odd,
            # New fields
            "classification": self.classification.value,
            "reason_codes": [rc.value for rc in self.reason_codes],
            "data_quality_score": round(self.data_quality_score, 2),
            "odds_available": self.odds_available,
            "ev": round(self.ev, 4) if self.ev is not None else None,
            "edge": round(self.edge, 4) if self.edge is not None else None,
            "fair_odd": self.fair_odd,
            "book_odd": self.book_odd,
            "calibrated_probability": round(self.calibrated_probability, 4) if self.calibrated_probability else None,
            "raw_probability": round(self.raw_probability, 4) if self.raw_probability else None,
        }
        # Add corner governance metadata if available
        if self.corner_governance:
            result["corner_governance"] = self.corner_governance
        return result

    def _legacy_status(self) -> str:
        """Map classification to legacy status for backward compat."""
        mapping = {
            MarketClassification.SAFE: "SAFE",
            MarketClassification.NEUTRO_QUALIFICADO: "NEUTRO",
            MarketClassification.NEUTRO: "NEUTRO",
            MarketClassification.NO_BET: "NO_BET",
        }
        return mapping.get(self.classification, "NO_BET")


class MatchMarketBundle(BaseModel):
    """All market outputs for a single match."""
    match_id: str
    home_team: str
    away_team: str
    league_id: str
    data_quality_score: float = 0.0
    markets: List[MarketOutput] = []
    eligible_for_multiples: bool = False
    reason_codes: List[ReasonCode] = []
