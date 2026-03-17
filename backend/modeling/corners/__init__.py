"""
Corner Betting Framework — Governed Market Family

Provides dedicated modeling, benchmarking, validation, and artifact generation
for the corners market family, independent from goal-based markets (1X2/O-U/BTTS).

Market Family: corners
Lines: corners_over_8_5, corners_over_9_5, corners_over_10_5, corners_over_11_5

Architecture prepared for future expansion:
- corners_under_x
- team_corners_over_x
- team_corners_under_x

Three candidate models:
1. Negative Binomial (primary baseline)
2. Poisson (secondary baseline / benchmark)
3. ML Regression (supervised candidate)

Operational States: RESTRICTED → NEUTRAL → ACTIVE_GUARDED → ACTIVE
Initial deployment: SHADOW/PILOT mode — no automatic promotion.
"""

MARKET_FAMILY = "corners"

CORNER_LINES = [8.5, 9.5, 10.5, 11.5]

CORNER_MARKET_KEYS = [f"corners_over_{str(line).replace('.', '_')}" for line in CORNER_LINES]

MODEL_CANDIDATES = ["negative_binomial", "poisson", "ml_regression"]
