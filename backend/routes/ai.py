from fastapi import APIRouter, Body
from pydantic import BaseModel
from backend.ai.context_analyzer import ContextAnalyzer
from backend.ai.report_generator import ReportGenerator

router = APIRouter(prefix="/ai", tags=["ai"])
analyzer = ContextAnalyzer(model="mistral-medium-latest")
reporter = ReportGenerator(model="mistral-medium-latest")

class AnalyzeContextRequest(BaseModel):
    home_team: str
    away_team: str
    news_summary: str | None = None

class GenerateReportRequest(BaseModel):
    home_team: str
    away_team: str
    stats: dict
    market: str
    classification: str
    probability: float

@router.post("/analyze-context")
def analyze_context(payload: AnalyzeContextRequest = Body(...)):
    r = analyzer.analyze_match_context(payload.home_team, payload.away_team, payload.news_summary)
    return {"analysis": r}

@router.post("/generate-report")
def generate_report(payload: GenerateReportRequest = Body(...)):
    txt = reporter.generate_match_report(payload.home_team, payload.away_team, payload.stats, payload.market, payload.classification, payload.probability)
    return {"report": txt}
