"""Test #183 — enrichment of complement matches via get_match_details."""
import os
from unittest.mock import patch


def _basic_record(match_id=8469775):
    return {
        "id": f"brasileirao-serie-b-todays-{match_id}",
        "footystatsId": match_id,
        "leagueId": "brasileirao-serie-b",
        "homeTeam": {"name": "Ceará"},
        "awayTeam": {"name": "Atlético GO"},
        "datetime": "2026-05-09T22:00:00Z",
        "odds": {"home": 1.93, "draw": 3.0, "away": 3.9},
        "stats": {"homeWinProb": 46.8, "drawProb": 30.1, "awayWinProb": 23.1},
        # No mercados[], no lambda, no detailed stats
    }


def test_enrich_returns_none_when_details_fail():
    """If get_match_details fails (success=False), return None."""
    from backend.routes.fixtures import _enrich_complement_record

    with patch("backend.routes.fixtures.footstats.get_match_details") as mock:
        mock.return_value = {"success": False, "error": "rate_limit"}
        result = _enrich_complement_record(
            _basic_record(), "brasileirao-serie-b", None, None, None, 1234, "today",
        )
        assert result is None


def test_enrich_returns_none_when_no_match_id():
    """No footystatsId in basic record → can't enrich."""
    from backend.routes.fixtures import _enrich_complement_record

    rec = _basic_record()
    rec.pop("footystatsId")
    result = _enrich_complement_record(
        rec, "brasileirao-serie-b", None, None, None, 1234, "today",
    )
    assert result is None


def test_enrich_handles_exception_gracefully():
    """Exception in get_match_details → None, no crash."""
    from backend.routes.fixtures import _enrich_complement_record

    with patch("backend.routes.fixtures.footstats.get_match_details") as mock:
        mock.side_effect = Exception("network error")
        result = _enrich_complement_record(
            _basic_record(), "brasileirao-serie-b", None, None, None, 1234, "today",
        )
        assert result is None


def test_enrich_returns_none_when_mercados_empty():
    """#183 success criterion: rich record without mercados[] is NOT a success."""
    from backend.routes.fixtures import _enrich_complement_record

    with patch("backend.routes.fixtures.footstats.get_match_details") as m_det, \
         patch("backend.routes.fixtures.DataMapper.matches_to_df") as m_map, \
         patch("backend.routes.fixtures.build_records_from_matches") as m_build:
        m_det.return_value = {"success": True, "data": {"id": 8469775}}
        # Non-empty df so we don't short-circuit on emptiness
        import pandas as pd
        m_map.return_value = pd.DataFrame([{"id": 8469775, "date_gmt": "2026-05-09 22:00:00"}])
        # Pipeline returns a record but with no mercados — must reject.
        m_build.return_value = [{"id": "x", "homeTeam": {"name": "A"}, "awayTeam": {"name": "B"}, "mercados": []}]
        result = _enrich_complement_record(
            _basic_record(), "brasileirao-serie-b", None, None, None, 1234, "today",
        )
        assert result is None


def test_enrich_returns_record_when_mercados_present():
    """Happy path: rich record with mercados[] → returned + dataSource tag."""
    from backend.routes.fixtures import _enrich_complement_record

    with patch("backend.routes.fixtures.footstats.get_match_details") as m_det, \
         patch("backend.routes.fixtures.DataMapper.matches_to_df") as m_map, \
         patch("backend.routes.fixtures.build_records_from_matches") as m_build:
        m_det.return_value = {"success": True, "data": {"id": 8469775}}
        import pandas as pd
        m_map.return_value = pd.DataFrame([{"id": 8469775, "date_gmt": "2026-05-09 22:00:00"}])
        m_build.return_value = [{
            "id": "x",
            "homeTeam": {"name": "A"},
            "awayTeam": {"name": "B"},
            "mercados": [{"name": "Over 2.5", "ev": 0.05}],
        }]
        result = _enrich_complement_record(
            _basic_record(), "brasileirao-serie-b", None, None, None, 1234, "today",
        )
        assert result is not None
        assert result.get("mercados")
        assert "FootyStats API (Tempo Real - via #183)" in result.get("dataSource", "")


def test_feature_flag_default_false():
    """ENABLE_MATCH_DETAILS_ENRICHMENT_183 must default to FALSE (rollout safety)."""
    os.environ.pop("ENABLE_MATCH_DETAILS_ENRICHMENT_183", None)
    import importlib, backend.routes.fixtures as fx
    importlib.reload(fx)
    assert fx.ENABLE_MATCH_DETAILS_ENRICHMENT_183 is False


def test_feature_flag_enabled_when_true():
    """Setting flag=true enables enrichment."""
    os.environ["ENABLE_MATCH_DETAILS_ENRICHMENT_183"] = "true"
    try:
        import importlib, backend.routes.fixtures as fx
        importlib.reload(fx)
        assert fx.ENABLE_MATCH_DETAILS_ENRICHMENT_183 is True
    finally:
        os.environ.pop("ENABLE_MATCH_DETAILS_ENRICHMENT_183", None)
        import importlib, backend.routes.fixtures as fx
        importlib.reload(fx)
