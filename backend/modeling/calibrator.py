"""Isotonic Regression calibrator for probability predictions.

Gap 5 — closes the feedback loop by learning a monotone mapping from raw
predicted probabilities to observed hit rates.  The calibrator is trained
on historical audit_results and applied *before* market selection so that
threshold comparisons operate on calibrated probabilities.

Fallback strategy (bin volume):
  - league has ≥50 records  → per-league model
  - regime  has ≥30 records → per-regime model
  - otherwise               → passthrough (raw prob returned as-is)
"""

import json
import logging
import os
import pickle
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MIN_SAMPLES_LEAGUE = 50
MIN_SAMPLES_REGIME = 30
BRIER_IMPROVEMENT_THRESHOLD = 0.0   # accept if calibrated Brier ≤ raw Brier
N_SPLITS = 5                        # TimeSeriesSplit folds

# Markets we calibrate (keys match audit_results.market column)
CALIBRATED_MARKETS = [
    "BTTS",
    "Over 2.5",
    "Over 3.5",
    "Over 4.5",
    "Under 1.5",
    "Under 3.5",
    "Under 4.5",
    "Double Chance 1X",
    "1X2_home",
    "1X2_draw",
    "1X2_away",
    "Escanteios Over 4.5",
    "Escanteios Over 5.5",
    "Escanteios Over 6.5",
    "Escanteios Over 7.5",
    "Escanteios Over 8.5",
    "Escanteios Over 9.5",
    "Escanteios Over 10.5",
    "Escanteios Over 11.5",
    "Escanteios Over 12.5",
    "Escanteios Under 4.5",
    "Escanteios Under 5.5",
    "Escanteios Under 6.5",
    "Escanteios Under 7.5",
    "Escanteios Under 8.5",
    "Escanteios Under 9.5",
    "Escanteios Under 10.5",
    "Escanteios Under 11.5",
    "Escanteios Under 12.5",
    # #189-e: cartões entram no loop de aprendizado. Era a família com mais
    # volume (ex.: 59% dos picks do Brasileirão A) e a ÚNICA fora do
    # CALIBRATED_MARKETS — o retrain diário nunca a tocava.
    "Cartoes Over 1.5",
    "Cartoes Over 2.5",
    "Cartoes Over 3.5",
    "Cartoes Over 4.5",
    "Cartoes Over 5.5",
    "Cartoes Under 2.5",
    "Cartoes Under 3.5",
    "Cartoes Under 4.5",
    "Cartoes Under 5.5",
    "Cartoes Under 6.5",
]

# ─── #189-e: Calibração hierárquica FAMÍLIA → LIGA ───
# As células (mercado × liga) quase nunca atingem MIN_SAMPLES_LEAGUE=50
# (~200 picks/liga espalhados por 12-17 mercados) — o retrain girava em
# falso e caía em passthrough. A hierarquia poola por família de mercado:
#   mercado|liga → família|liga → família|global → passthrough
# A liga só desvia do global quando acumula evidência própria.

_FAMILY_PREFIX = "family"


def _market_family_label(market: str) -> str:
    """Classifica um rótulo de mercado do audit_results em família."""
    ml = (market or "").lower()
    if "escanteio" in ml or "corner" in ml:
        return "escanteios"
    if "cart" in ml or "card" in ml:
        return "cartoes"
    if "btts" in ml or "ambas" in ml:
        return "btts"
    if "over" in ml or "under" in ml:
        return "gols"
    if "1x2" in ml or "double" in ml or "dupla" in ml or "dc" in ml:
        return "x1x2_dc"
    return "outros"


def _family_markets(family: str) -> list:
    """Mercados do CALIBRATED_MARKETS pertencentes à família."""
    return [m for m in CALIBRATED_MARKETS if _market_family_label(m) == family]

# Approximate season-start months per league (Aug for most European, Feb for SA)
_SEASON_STARTS: Dict[str, int] = {
    # European — August
    "premier-league": 8, "championship": 8, "la-liga": 8, "serie-a": 8,
    "bundesliga": 8, "ligue-1": 8, "eredivisie": 8, "primeira-liga": 8,
    "super-lig": 8, "jupiler-pro-league": 8, "scottish-premiership": 8,
    "serie-b": 8, "2-bundesliga": 8,
    "league-one": 8,
    # South American — February
    "brasileirao": 4, "serie-b-brazil": 4, "copa-libertadores": 2,
    "copa-sudamericana": 2, "liga-profesional": 2,
}

# Directory for persisted calibrator models
_MODELS_DIR = Path(os.getenv("DATA_ROOT", ".")) / ".calibrators"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _season_start_date(league_id: str) -> datetime:
    """Return the start of the *current* season for a league."""
    month = _SEASON_STARTS.get(league_id, 8)
    now = datetime.utcnow()
    year = now.year if now.month >= month else now.year - 1
    return datetime(year, month, 1)


def _load_training_data(
    market: str,
    league_id: str = "",
    regime: str = "",
) -> Tuple[np.ndarray, np.ndarray]:
    """Load (predicted_prob, outcome) pairs from audit_results.

    Returns arrays of shape (N,) each, where predicted_prob ∈ [0,1] and
    outcome ∈ {0, 1}.
    """
    from backend.audit import init_db

    conn = init_db()
    season_start = _season_start_date(league_id) if league_id else datetime.utcnow() - timedelta(days=180)

    if league_id:
        rows = conn.execute(
            "SELECT predicted_probs, actual_result FROM audit_results "
            "WHERE market = ? AND league = ? AND timestamp >= ? "
            "ORDER BY timestamp ASC",
            (market, league_id, season_start.isoformat()),
        ).fetchall()
    elif regime:
        # Fallback: by regime (stored in context JSON)
        rows = conn.execute(
            "SELECT predicted_probs, actual_result FROM audit_results "
            "WHERE market = ? AND timestamp >= ? "
            "ORDER BY timestamp ASC",
            (market, season_start.isoformat()),
        ).fetchall()
        # Filter by regime in context
        filtered = []
        for r in rows:
            try:
                ctx = json.loads(r[2]) if len(r) > 2 else {}
                if ctx.get("regime") == regime:
                    filtered.append(r)
            except Exception:
                pass
        rows = filtered if filtered else rows  # if no regime info, use all
    else:
        rows = conn.execute(
            "SELECT predicted_probs, actual_result FROM audit_results "
            "WHERE market = ? AND timestamp >= ? "
            "ORDER BY timestamp ASC",
            (market, (datetime.utcnow() - timedelta(days=180)).isoformat()),
        ).fetchall()

    conn.close()

    probs = []
    outcomes = []
    for row in rows:
        try:
            pred = json.loads(row[0]) if isinstance(row[0], str) else row[0]
            # predicted_probs can be a single float or a dict; extract the main prob
            if isinstance(pred, dict):
                p = float(pred.get("prob", pred.get("predicted", 0)))
            else:
                p = float(pred)
            # Normalise to 0-1
            if p > 1.0:
                p /= 100.0
            outcome = 1 if str(row[1]).strip().lower() in ("1", "true", "yes", "hit", "win") else 0
            probs.append(p)
            outcomes.append(outcome)
        except Exception:
            continue

    return np.array(probs, dtype=np.float64), np.array(outcomes, dtype=np.int32)


def _brier_score(probs: np.ndarray, outcomes: np.ndarray) -> float:
    """Mean Brier score = mean((p - o)^2)."""
    return float(np.mean((probs - outcomes) ** 2))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def train_calibrator(
    market: str,
    league_id: str = "",
    regime: str = "",
) -> Optional[dict]:
    """Train an IsotonicRegression calibrator for a (market, league|regime) pair.

    Returns a summary dict or None if insufficient data / no improvement.
    """
    from sklearn.isotonic import IsotonicRegression
    from sklearn.model_selection import TimeSeriesSplit

    # Determine granularity
    X, y = _load_training_data(market, league_id=league_id)
    label = f"{market}|{league_id}" if league_id else f"{market}|regime={regime}"

    if league_id and len(X) < MIN_SAMPLES_LEAGUE:
        # Fallback to regime level
        logger.info(f"[Calibrator] {label}: only {len(X)} samples, falling back to regime")
        if regime:
            X, y = _load_training_data(market, regime=regime)
            label = f"{market}|regime={regime}"
        else:
            X, y = _load_training_data(market)
            label = f"{market}|global"

    if len(X) < MIN_SAMPLES_REGIME:
        logger.info(f"[Calibrator] {label}: only {len(X)} samples — passthrough")
        return None

    # Time-series cross-validation
    tscv = TimeSeriesSplit(n_splits=min(N_SPLITS, max(2, len(X) // 20)))
    brier_raw_all = []
    brier_cal_all = []

    for train_idx, test_idx in tscv.split(X):
        X_train, X_test = X[train_idx], X[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]

        iso = IsotonicRegression(y_min=0, y_max=1, out_of_bounds="clip")
        iso.fit(X_train, y_train)

        cal_test = iso.predict(X_test)
        brier_raw_all.append(_brier_score(X_test, y_test))
        brier_cal_all.append(_brier_score(cal_test, y_test))

    brier_raw = float(np.mean(brier_raw_all))
    brier_cal = float(np.mean(brier_cal_all))

    # Accept only if calibrated Brier is not worse
    if brier_cal > brier_raw + BRIER_IMPROVEMENT_THRESHOLD:
        logger.info(
            f"[Calibrator] {label}: rejected — raw Brier={brier_raw:.4f}, "
            f"calibrated={brier_cal:.4f}"
        )
        return {
            "label": label,
            "accepted": False,
            "brier_raw": round(brier_raw, 4),
            "brier_calibrated": round(brier_cal, 4),
            "n_samples": len(X),
        }

    # Retrain on full data and persist
    iso_final = IsotonicRegression(y_min=0, y_max=1, out_of_bounds="clip")
    iso_final.fit(X, y)

    _MODELS_DIR.mkdir(parents=True, exist_ok=True)
    key = _model_key(market, league_id, regime)
    model_path = _MODELS_DIR / f"{key}.pkl"
    with open(model_path, "wb") as f:
        pickle.dump(iso_final, f)

    logger.info(
        f"[Calibrator] {label}: accepted — raw Brier={brier_raw:.4f}, "
        f"calibrated={brier_cal:.4f}, n={len(X)}"
    )
    return {
        "label": label,
        "accepted": True,
        "brier_raw": round(brier_raw, 4),
        "brier_calibrated": round(brier_cal, 4),
        "n_samples": len(X),
        "model_path": str(model_path),
    }


def calibrate_prob(
    prob: float,
    market: str,
    league_id: str = "",
    regime: str = "",
) -> float:
    """Calibrate a single probability using a persisted Isotonic model.

    #189-e — cadeia hierárquica de fallback:
        mercado|liga → mercado|regime → mercado|global
        → família|liga → família|global → passthrough
    Expects prob in 0-1 scale; returns 0-1 scale.
    """
    family = _market_family_label(market)
    fam_market = f"{_FAMILY_PREFIX} {family}"
    # Try league-specific model first, then family pools (#189-e)
    for key in [
        _model_key(market, league_id, ""),
        _model_key(market, "", regime),
        _model_key(market, "", ""),
        _model_key(fam_market, league_id, ""),
        _model_key(fam_market, "", ""),
    ]:
        model_path = _MODELS_DIR / f"{key}.pkl"
        if model_path.exists():
            try:
                with open(model_path, "rb") as f:
                    iso = pickle.load(f)
                result = float(iso.predict(np.array([prob]))[0])
                return max(0.0, min(1.0, result))
            except Exception as e:
                logger.debug(f"[Calibrator] Failed to load {model_path}: {e}")
                continue

    # No model available — passthrough
    return prob


def calibrate_match_stats(
    stats: dict,
    league_id: str = "",
    regime: str = "",
) -> dict:
    """Calibrate corner display probabilities in a match stats dict (0-100 scale).

    Modifies stats in-place and returns it.

    #187: restricted to corners. Goals O/U, BTTS and 1X2 display fields are no
    longer isotonic-mutated here — the acceptance contract requires them to be
    exactly derivable from the payload lambdas (over+under=100, monotonicity)
    or, for 1X2, to be the labeled market mirror (#028/#064). Per-league
    isotonic calibration of PICKS is untouched: it runs inside
    ev_classification via calibrate_prob (#106).
    """
    _mapping = {
        "cornerOver85Prob": "Escanteios Over 8.5",
        "cornerOver95Prob": "Escanteios Over 9.5",
        "cornerOver105Prob": "Escanteios Over 10.5",
        "cornerOver115Prob": "Escanteios Over 11.5",
    }

    for stat_key, market in _mapping.items():
        raw = stats.get(stat_key)
        if raw is None:
            continue
        raw_01 = float(raw) / 100.0 if float(raw) > 1.0 else float(raw)
        cal_01 = calibrate_prob(raw_01, market, league_id, regime)
        stats[stat_key] = round(cal_01 * 100.0, 1)

    return stats


def train_family_calibrator(family: str, league_id: str = "") -> Optional[dict]:
    """#189-e: treina um calibrador POOL por família de mercado.

    Junta as amostras de todos os mercados da família (numa liga, ou
    global quando league_id="") — células gordas que atingem o mínimo
    de amostras mesmo onde as células mercado×liga morriam de fome.
    Mesmo protocolo do train_calibrator: TimeSeriesSplit + aceita só se
    o Brier calibrado não piora.
    """
    from sklearn.isotonic import IsotonicRegression
    from sklearn.model_selection import TimeSeriesSplit

    markets = _family_markets(family)
    if not markets:
        return None

    xs, ys = [], []
    for m in markets:
        X_m, y_m = _load_training_data(m, league_id=league_id)
        if len(X_m):
            xs.append(X_m)
            ys.append(y_m)
    if not xs:
        return None
    X = np.concatenate(xs)
    y = np.concatenate(ys)

    label = f"{_FAMILY_PREFIX} {family}|{league_id or 'global'}"
    min_needed = MIN_SAMPLES_LEAGUE if league_id else MIN_SAMPLES_REGIME
    if len(X) < min_needed:
        logger.info(f"[Calibrator] {label}: only {len(X)} samples — skipped")
        return None

    tscv = TimeSeriesSplit(n_splits=min(N_SPLITS, max(2, len(X) // 20)))
    brier_raw_all, brier_cal_all = [], []
    for train_idx, test_idx in tscv.split(X):
        iso = IsotonicRegression(y_min=0, y_max=1, out_of_bounds="clip")
        iso.fit(X[train_idx], y[train_idx])
        cal_test = iso.predict(X[test_idx])
        brier_raw_all.append(_brier_score(X[test_idx], y[test_idx]))
        brier_cal_all.append(_brier_score(cal_test, y[test_idx]))

    brier_raw = float(np.mean(brier_raw_all))
    brier_cal = float(np.mean(brier_cal_all))
    if brier_cal > brier_raw + BRIER_IMPROVEMENT_THRESHOLD:
        logger.info(
            f"[Calibrator] {label}: rejected — raw Brier={brier_raw:.4f}, "
            f"calibrated={brier_cal:.4f}"
        )
        return {"label": label, "accepted": False, "brier_raw": round(brier_raw, 4),
                "brier_calibrated": round(brier_cal, 4), "n_samples": len(X)}

    iso_final = IsotonicRegression(y_min=0, y_max=1, out_of_bounds="clip")
    iso_final.fit(X, y)
    _MODELS_DIR.mkdir(parents=True, exist_ok=True)
    key = _model_key(f"{_FAMILY_PREFIX} {family}", league_id, "")
    model_path = _MODELS_DIR / f"{key}.pkl"
    with open(model_path, "wb") as f:
        pickle.dump(iso_final, f)
    logger.info(
        f"[Calibrator] {label}: accepted — raw Brier={brier_raw:.4f}, "
        f"calibrated={brier_cal:.4f}, n={len(X)}"
    )
    return {"label": label, "accepted": True, "brier_raw": round(brier_raw, 4),
            "brier_calibrated": round(brier_cal, 4), "n_samples": len(X),
            "model_path": str(model_path)}


def retrain_all_calibrators() -> list:
    """Retrain calibrators for all markets and leagues with enough data.

    Called by cron_handler (retrain_calibrators action).
    Returns a list of summary dicts.
    """
    from backend.audit import init_db

    results = []

    conn = init_db()
    # Get distinct (market, league) pairs with enough data
    rows = conn.execute(
        "SELECT market, league, COUNT(*) as cnt "
        "FROM audit_results "
        "GROUP BY market, league "
        "HAVING cnt >= ?",
        (MIN_SAMPLES_REGIME,),
    ).fetchall()
    conn.close()

    for row in rows:
        market, league, cnt = row[0], row[1], row[2]
        try:
            result = train_calibrator(market, league_id=league)
            if result:
                results.append(result)
        except Exception as e:
            logger.warning(f"[Calibrator] Error training {market}|{league}: {e}")
            results.append({"label": f"{market}|{league}", "error": str(e)})

    # #189-e: treina os pools por família — global e por liga observada.
    families = ["gols", "btts", "escanteios", "cartoes", "x1x2_dc"]
    leagues_seen = sorted({row[1] for row in rows if row[1]})
    for fam in families:
        try:
            r = train_family_calibrator(fam)  # global
            if r:
                results.append(r)
        except Exception as e:
            results.append({"label": f"{_FAMILY_PREFIX} {fam}|global", "error": str(e)})
        for lg in leagues_seen:
            try:
                r = train_family_calibrator(fam, league_id=lg)
                if r:
                    results.append(r)
            except Exception as e:
                results.append({"label": f"{_FAMILY_PREFIX} {fam}|{lg}", "error": str(e)})

    # #189-e: telemetria do retrain — falha de aprendizado vira número, não silêncio.
    accepted = sum(1 for r in results if r.get("accepted"))
    rejected = sum(1 for r in results if r.get("accepted") is False)
    errors = sum(1 for r in results if "error" in r)
    logger.info(
        f"[Calibrator] retrain_all completed: {len(results)} processed | "
        f"accepted={accepted} rejected={rejected} errors={errors}"
    )
    return results


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _model_key(market: str, league_id: str, regime: str) -> str:
    """Generate a filesystem-safe key for a calibrator model."""
    parts = [market.replace(" ", "_").replace("/", "_")]
    if league_id:
        parts.append(league_id)
    elif regime:
        parts.append(f"regime_{regime}")
    else:
        parts.append("global")
    return "__".join(parts).lower()
