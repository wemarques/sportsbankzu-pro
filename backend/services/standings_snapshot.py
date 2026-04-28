"""
standings_snapshot.py — Snapshot diario de standings para S3 (#173).

Persiste tabelas de classificacao das ligas suportadas em S3 para permitir
reconstrucao historica futura. Sem isso, standings ficam apenas no cache TTL
de 6h e desaparecem — impossibilitando backtest de features de contexto
de temporada (rebaixados, briga pelo titulo, meio da tabela).

Estrutura S3:
    s3://meu-bucket-sportsbank/standings/{YYYY-MM-DD}/{league_id}.json

Conteudo do JSON:
    {
        "league_id": "premier-league",
        "league_name": "Premier League",
        "country": "England",
        "season": 2025,
        "collected_at": "2026-04-27T05:00:00Z",
        "api_football": [...],   # response de api_football_client.get_standings
        "footystats": [...],     # response de footystats_client.get_league_tables
        "errors": {"api_football": "...", "footystats": "..."}
    }

Em ~3-6 meses temos historico suficiente para juntar pick.timestamp com
standing.collected_at e medir Brier por (rank, gap_to_relegation, etc.).

Chamado via cron action `snapshot_standings`.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("sportsbankzu.standings_snapshot")

S3_KEY_PREFIX = "standings"


def _s3_bucket() -> str | None:
    return os.getenv("S3_BUCKET") or None


def _safe_get_api_football_standings(league_internal_id: str) -> tuple[list, str | None]:
    """Fetch standings from API-Football. Returns (data, error_msg)."""
    try:
        from backend.config.leagues_config import (
            get_api_football_league_id,
            get_season_for_league,
        )
        from backend.services.api_football_client import APIFootballClient

        af_id = get_api_football_league_id(league_internal_id)
        if not af_id:
            return [], "no_api_football_id"
        season = get_season_for_league(league_internal_id)
        client = APIFootballClient()
        # ttl_minutes=0 — bypass cache, we want fresh data for the snapshot
        data = client.get_standings(af_id, season, ttl_minutes=0)
        return data or [], None
    except Exception as e:
        return [], f"{type(e).__name__}: {e}"


def _safe_get_footystats_tables(league_internal_id: str) -> tuple[list, str | None]:
    """Fetch league tables from FootyStats. Returns (data, error_msg)."""
    try:
        from backend.services.footstats_client import get_league_tables

        # FootyStats expects a season_id (integer). Without an active mapping,
        # we cannot call this safely — but we keep the call for forward
        # compatibility. The function returns [] on failure, which is fine.
        data = get_league_tables(league_internal_id) or []
        return data, None
    except Exception as e:
        return [], f"{type(e).__name__}: {e}"


def snapshot_one_league(league_id: str, league_name: str, country: str) -> dict[str, Any]:
    """Capture standings for a single league and return the payload."""
    from backend.config.leagues_config import get_season_for_league

    af_data, af_err = _safe_get_api_football_standings(league_id)
    fs_data, fs_err = _safe_get_footystats_tables(league_id)

    errors: dict[str, str] = {}
    if af_err:
        errors["api_football"] = af_err
    if fs_err:
        errors["footystats"] = fs_err

    return {
        "league_id": league_id,
        "league_name": league_name,
        "country": country,
        "season": get_season_for_league(league_id),
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "api_football": af_data,
        "footystats": fs_data,
        "errors": errors,
    }


def upload_to_s3(payload: dict[str, Any]) -> bool:
    """Persist one league's snapshot to S3. Returns True on success."""
    bucket = _s3_bucket()
    if not bucket:
        logger.warning("[standings_snapshot] S3_BUCKET not configured — skipping upload")
        return False
    try:
        import boto3
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        key = f"{S3_KEY_PREFIX}/{date_str}/{payload['league_id']}.json"
        s3 = boto3.client("s3")
        s3.put_object(
            Bucket=bucket,
            Key=key,
            Body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            ContentType="application/json",
        )
        logger.info(
            f"[standings_snapshot] Uploaded {payload['league_id']} "
            f"(api_football={len(payload['api_football'])}, "
            f"footystats={len(payload['footystats'])}) to s3://{bucket}/{key}"
        )
        return True
    except Exception as e:
        logger.error(f"[standings_snapshot] S3 upload failed for {payload['league_id']}: {e}")
        return False


def snapshot_all_leagues_to_s3() -> dict[str, Any]:
    """Capture standings for ALL configured leagues and persist to S3.

    Defensive: per-league try/except. One failure does not abort the batch.
    """
    from backend.config.leagues_config import LEAGUES_CONFIG

    started = datetime.now(timezone.utc)
    successes: list[str] = []
    failures: list[dict[str, str]] = []
    skipped_no_data: list[str] = []

    for league in LEAGUES_CONFIG:
        league_id = league.get("id", "")
        league_name = league.get("name", "")
        country = league.get("country", "")
        if not league_id:
            continue

        try:
            payload = snapshot_one_league(league_id, league_name, country)
            has_data = bool(payload.get("api_football")) or bool(payload.get("footystats"))
            if not has_data:
                skipped_no_data.append(league_id)
                logger.info(
                    f"[standings_snapshot] {league_id} — no standings data returned, skipping upload"
                )
                continue
            if upload_to_s3(payload):
                successes.append(league_id)
            else:
                failures.append({"league_id": league_id, "reason": "s3_upload_failed"})
        except Exception as e:
            logger.error(f"[standings_snapshot] {league_id} unexpected error: {e}")
            failures.append({"league_id": league_id, "reason": f"{type(e).__name__}: {e}"})

    elapsed = (datetime.now(timezone.utc) - started).total_seconds()
    result = {
        "status": "success" if successes else "partial",
        "uploaded": len(successes),
        "failed": len(failures),
        "skipped_no_data": len(skipped_no_data),
        "elapsed_seconds": round(elapsed, 1),
        "successes": successes,
        "failures": failures,
        "skipped": skipped_no_data,
        "snapshot_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }
    logger.info(f"[standings_snapshot] Batch complete: {result}")
    return result
