"""Audit status endpoint — returns recent audit results and corrections."""

import logging
from typing import Optional

from fastapi import APIRouter, Query

from backend.audit import (
    APP_VERSION,
    get_active_corrections,
    get_recent_audit_results,
    get_recent_corrections,
)

logger = logging.getLogger("sportsbankzu.routes.audit_status")

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("/status")
async def audit_status(
    days: int = Query(7, ge=1, le=90, description="Number of days to look back"),
):
    """Return recent audit results, corrections, and summary."""
    try:
        audits = get_recent_audit_results(days=days)
    except Exception as e:
        logger.warning(f"Failed to fetch audit results: {e}")
        audits = []

    try:
        corrections = get_recent_corrections(days=days)
    except Exception as e:
        logger.warning(f"Failed to fetch corrections: {e}")
        corrections = []

    try:
        active = get_active_corrections()
    except Exception as e:
        logger.warning(f"Failed to fetch active corrections: {e}")
        active = {}

    # Extract latest batch audit from cron
    last_batch = next(
        (a for a in audits if a.get("match_id", "").startswith("cron_batch")),
        None,
    )

    # Count corrections auto-applied by cron
    applied_by_cron = [c for c in corrections if c.get("applied_by") == "cron_auto"]

    return {
        "version": APP_VERSION,
        "last_batch_audit": last_batch,
        "recent_audits": audits,
        "recent_corrections": corrections,
        "active_corrections": active,
        "summary": {
            "total_audits": len(audits),
            "total_corrections_applied": len(applied_by_cron),
            "has_recent_activity": bool(audits),
        },
    }
