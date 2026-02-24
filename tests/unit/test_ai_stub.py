from backend.ai.context_analyzer import ContextAnalyzer
from backend.ai.report_generator import ReportGenerator
from backend.ai.cache_manager import CacheManager

def test_context_analyzer_stub():
    a = ContextAnalyzer()
    res = a.analyze_match_context("A", "B", "Sem notícias")
    assert "confidence_adjustment" in res

def test_report_generator_stub():
    g = ReportGenerator()
    txt = g.generate_match_report("A", "B", {"lambda_home": 1.1, "lambda_away": 0.9}, "Over 2.5", "SAFE", 65)
    assert isinstance(txt, str) and len(txt) > 0


def test_cache_manager_none_team_names(tmp_path):
    """Regression test: CacheManager must not crash when home/away is None."""
    db = str(tmp_path / "test_cache.db")
    cm = CacheManager(db_path=db, ttl_hours=1)
    # Should not raise AttributeError: 'NoneType' object has no attribute 'lower'
    key = cm._generate_key("audit", None, None)
    assert isinstance(key, str) and len(key) == 32  # MD5 hex digest
    # Should also work with empty strings
    key2 = cm._generate_key("audit", "", "")
    assert key == key2  # None and "" produce same key
    # get/set should not crash with None
    assert cm.get("audit", None, None) is None
    cm.set("audit", None, None, {"test": True})
    result = cm.get("audit", None, None)
    assert result == {"test": True}
