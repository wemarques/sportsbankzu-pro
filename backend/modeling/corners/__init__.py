"""
Corner Betting Framework v2 — Governed Market Family

Bidirectional motor: projects expected_total_corners first, then prices
both Over and Under across the full ladder of lines.

Market Family: corners
Lines: 4.5 through 12.5 (Over and Under for each)

Three candidate models:
1. Negative Binomial (primary baseline — captures overdispersion)
2. Poisson (secondary baseline / benchmark)
3. ML Regression (supervised candidate — GradientBoosting)

Operational States: RESTRICTED → NEUTRAL → ACTIVE_GUARDED → ACTIVE
Initial deployment: SHADOW/PILOT mode — no automatic promotion.
"""

MARKET_FAMILY = "corners"

# Full ladder of lines — v2 expanded from v1's [8.5, 9.5, 10.5, 11.5]
CORNER_LINES = [4.5, 5.5, 6.5, 7.5, 8.5, 9.5, 10.5, 11.5, 12.5]

# Legacy-compatible subset (used by existing odds sources)
CORNER_LINES_LEGACY = [8.5, 9.5, 10.5, 11.5]

CORNER_MARKET_KEYS = [f"corners_over_{str(line).replace('.', '_')}" for line in CORNER_LINES]

MODEL_CANDIDATES = ["negative_binomial", "poisson", "ml_regression"]

# Data quality tiers
DATA_QUALITY_TIERS = ["HIGH", "MEDIUM", "LOW", "INSUFFICIENT"]

# v2 version tag
ENGINE_VERSION = "2.0.0"
