from backend.ai.context_analyzer import ContextAnalyzer
from backend.ai.report_generator import ReportGenerator

def test_context_analyzer_stub():
    a = ContextAnalyzer()
    res = a.analyze_match_context("A", "B", "Sem notícias")
    assert "confidence_adjustment" in res

def test_report_generator_stub():
    g = ReportGenerator()
    txt = g.generate_match_report("A", "B", {"lambda_home": 1.1, "lambda_away": 0.9}, "Over 2.5", "SAFE", 65)
    assert isinstance(txt, str) and len(txt) > 0
