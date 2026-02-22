from mangum import Mangum

from backend.main import app

_mangum_handler = Mangum(app)


def handler(event, context):
    """
    Unified Lambda entry point.
    Routes EventBridge scheduled events to cron_handler,
    and HTTP requests (API Gateway) to Mangum/FastAPI.
    """
    source = event.get("source", "")
    if source in ("eventbridge", "aws.events") or event.get("action") == "batch_audit":
        from backend.cron_handler import cron_handler
        return cron_handler(event, context)
    return _mangum_handler(event, context)
