"""
Corner Artifacts Generation

Generates dedicated artifacts for the corners market family:
- corner_models_summary.json
- corner_validation_report.json
- corner_line_metrics.json
- corner_calibration.json
- corner_baseline_comparison.json
- corner_promotion_decisions.json
- corner_model_registry.json
- corner_training_metadata.json

Each artifact contains per-league, per-line data with:
- model_version, data_cutoff, sample_size
- champion_model, fallback_model
- expected_total_corners_method
- brier, logloss, ece, roi_theoretical
- drift_status, operational_status
- beats_baseline_* flags
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.modeling.corners import CORNER_LINES, MODEL_CANDIDATES
from backend.modeling.corners.operational_states import CornerOperationalState
from backend.utils.caminhos import raiz_de_dados  # #226

logger = logging.getLogger("sportsbankzu.corners.artifacts")

_ARTIFACTS_DIR = raiz_de_dados() / ".corner_artifacts"  # #226
_MODEL_VERSION = "1.0.0"


def _ensure_dir():
    _ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)


def _base_entry(league_id: str, line: float) -> Dict[str, Any]:
    """Base fields for every artifact entry."""
    return {
        "league_id": league_id,
        "line": line,
        "model_version": _MODEL_VERSION,
        "data_cutoff": datetime.utcnow().isoformat(),
        "generated_at": datetime.utcnow().isoformat(),
    }


def generate_models_summary(
    training_results: Dict[str, List[Dict[str, Any]]],
) -> Dict[str, Any]:
    """Generate corner_models_summary.json.

    Summarizes training output for all models across all leagues.
    """
    _ensure_dir()
    summary = {
        "generated_at": datetime.utcnow().isoformat(),
        "model_version": _MODEL_VERSION,
        "leagues": {},
    }

    for league_id, model_results in training_results.items():
        league_summary = {}
        for result in model_results:
            model_name = result.get("model", "unknown")
            league_summary[model_name] = {
                "status": result.get("status"),
                "sample_size": result.get("sample_size", 0),
                "avg_brier": result.get("avg_brier"),
                "parameters": {
                    k: v for k, v in result.items()
                    if k in ("mu", "alpha", "lambda", "avg_mae", "avg_rmse")
                },
            }
        summary["leagues"][league_id] = league_summary

    path = _ARTIFACTS_DIR / "corner_models_summary.json"
    with open(path, "w") as f:
        json.dump(summary, f, indent=2)

    logger.info(f"Generated corner_models_summary.json: {len(summary['leagues'])} leagues")
    return summary


def generate_validation_report(
    comparisons: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """Generate corner_validation_report.json.

    Formal comparison between all candidate models per league.
    """
    _ensure_dir()
    report = {
        "generated_at": datetime.utcnow().isoformat(),
        "model_version": _MODEL_VERSION,
        "leagues": comparisons,
    }

    path = _ARTIFACTS_DIR / "corner_validation_report.json"
    with open(path, "w") as f:
        json.dump(report, f, indent=2, default=str)

    logger.info(f"Generated corner_validation_report.json: {len(comparisons)} leagues")
    return report


def generate_line_metrics(
    all_metrics: Dict[str, Dict[str, Dict[str, Any]]],
) -> Dict[str, Any]:
    """Generate corner_line_metrics.json.

    Per-league, per-line metrics for champion model.
    """
    _ensure_dir()
    report = {
        "generated_at": datetime.utcnow().isoformat(),
        "model_version": _MODEL_VERSION,
        "entries": [],
    }

    for league_id, line_data in all_metrics.items():
        for line_key, metrics in line_data.items():
            line_val = float(line_key.replace("over_", ""))
            entry = _base_entry(league_id, line_val)
            entry.update({
                "champion_model": metrics.get("champion_model"),
                "fallback_model": metrics.get("fallback_model"),
                "expected_total_corners_method": metrics.get("expected_total_corners_method", "distribution"),
                "brier": metrics.get("brier"),
                "logloss": metrics.get("logloss"),
                "ece": metrics.get("ece"),
                "roi_theoretical": metrics.get("roi_theoretical"),
                "sample_size": metrics.get("sample_size"),
                "drift_status": "ok" if metrics.get("drift", 0) < 0.10 else "elevated",
                "drift": metrics.get("drift"),
                "operational_status": metrics.get("operational_status", "RESTRICTED"),
                "beats_baseline_league": metrics.get("beats_baseline_league", False),
                "beats_baseline_team": metrics.get("beats_baseline_team", False),
                "beats_poisson": metrics.get("beats_poisson", False),
                "beats_negative_binomial": metrics.get("beats_negative_binomial", False),
                "beats_ml_regression": metrics.get("beats_ml_regression", False),
            })
            report["entries"].append(entry)

    path = _ARTIFACTS_DIR / "corner_line_metrics.json"
    with open(path, "w") as f:
        json.dump(report, f, indent=2)

    logger.info(f"Generated corner_line_metrics.json: {len(report['entries'])} entries")
    return report


def generate_calibration(
    calibration_data: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """Generate corner_calibration.json."""
    _ensure_dir()
    report = {
        "generated_at": datetime.utcnow().isoformat(),
        "model_version": _MODEL_VERSION,
        "leagues": calibration_data,
    }

    path = _ARTIFACTS_DIR / "corner_calibration.json"
    with open(path, "w") as f:
        json.dump(report, f, indent=2)

    return report


def generate_baseline_comparison(
    comparisons: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """Generate corner_baseline_comparison.json."""
    _ensure_dir()
    report = {
        "generated_at": datetime.utcnow().isoformat(),
        "model_version": _MODEL_VERSION,
        "leagues": comparisons,
    }

    path = _ARTIFACTS_DIR / "corner_baseline_comparison.json"
    with open(path, "w") as f:
        json.dump(report, f, indent=2, default=str)

    return report


def generate_promotion_decisions(
    decisions: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """Generate corner_promotion_decisions.json."""
    _ensure_dir()
    report = {
        "generated_at": datetime.utcnow().isoformat(),
        "model_version": _MODEL_VERSION,
        "leagues": {},
    }

    for league_id, league_data in decisions.items():
        lines = league_data.get("lines", {})
        league_entries = {}
        for line_key, state_data in lines.items():
            state = state_data.get("operational_state")
            if hasattr(state, "value"):
                state = state.value
            league_entries[line_key] = {
                "operational_state": state,
                "evidence_score": state_data.get("evidence_score", {}),
                "hard_blockers": state_data.get("hard_blockers", []),
                "reasoning": state_data.get("reasoning", ""),
                "force_shadow": state_data.get("force_shadow", True),
            }
        report["leagues"][league_id] = {
            "lines": league_entries,
            "state_distribution": league_data.get("state_distribution", {}),
            "any_active": league_data.get("any_active", False),
        }

    path = _ARTIFACTS_DIR / "corner_promotion_decisions.json"
    with open(path, "w") as f:
        json.dump(report, f, indent=2)

    logger.info(f"Generated corner_promotion_decisions.json: {len(report['leagues'])} leagues")
    return report


def generate_model_registry(
    champion_selections: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """Generate corner_model_registry.json."""
    _ensure_dir()
    registry = {
        "generated_at": datetime.utcnow().isoformat(),
        "model_version": _MODEL_VERSION,
        "leagues": {},
    }

    for league_id, selection_data in champion_selections.items():
        league_registry = {
            "dominant_champion": selection_data.get("dominant_champion"),
            "champion_distribution": selection_data.get("champion_distribution", {}),
            "lines": {},
        }
        for line_key, sel in selection_data.get("line_selections", {}).items():
            league_registry["lines"][line_key] = {
                "champion_model": sel.get("champion_model"),
                "fallback_model": sel.get("fallback_model"),
                "champion_score": sel.get("champion_score"),
                "selection_method": sel.get("selection_method"),
            }
        registry["leagues"][league_id] = league_registry

    path = _ARTIFACTS_DIR / "corner_model_registry.json"
    with open(path, "w") as f:
        json.dump(registry, f, indent=2)

    return registry


def generate_training_metadata(
    training_details: Dict[str, Any],
) -> Dict[str, Any]:
    """Generate corner_training_metadata.json."""
    _ensure_dir()
    metadata = {
        "generated_at": datetime.utcnow().isoformat(),
        "model_version": _MODEL_VERSION,
        **training_details,
    }

    path = _ARTIFACTS_DIR / "corner_training_metadata.json"
    with open(path, "w") as f:
        json.dump(metadata, f, indent=2, default=str)

    return metadata


def load_artifact(name: str) -> Optional[Dict[str, Any]]:
    """Load a corner artifact by name.

    Args:
        name: Artifact filename without .json extension
              (e.g. "corner_model_registry")

    Returns:
        Parsed JSON dict or None if not found.
    """
    path = _ARTIFACTS_DIR / f"{name}.json"
    if not path.exists():
        return None
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load corner artifact {name}: {e}")
        return None


def get_league_line_status(
    league_id: str,
    line: float,
) -> Optional[Dict[str, Any]]:
    """Get the current operational status for a specific league/line.

    Reads from corner_promotion_decisions.json artifact.
    """
    decisions = load_artifact("corner_promotion_decisions")
    if not decisions:
        return None

    league_data = decisions.get("leagues", {}).get(league_id)
    if not league_data:
        return None

    line_key = f"over_{line}"
    return league_data.get("lines", {}).get(line_key)


def get_league_champion(
    league_id: str,
    line: float,
) -> Optional[Dict[str, str]]:
    """Get champion and fallback model for a specific league/line.

    Reads from corner_model_registry.json artifact.
    """
    registry = load_artifact("corner_model_registry")
    if not registry:
        return None

    league_data = registry.get("leagues", {}).get(league_id)
    if not league_data:
        return None

    line_key = f"over_{line}"
    line_data = league_data.get("lines", {}).get(line_key)
    if not line_data:
        return None

    return {
        "champion_model": line_data.get("champion_model"),
        "fallback_model": line_data.get("fallback_model"),
    }
