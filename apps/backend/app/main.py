from fastapi import FastAPI

from app.api.health import router as health_router
from app.core.config import load_settings

settings = load_settings()

app = FastAPI(
    title="MCC AI Platform API",
    version="0.1.0",
    description="Phase 0 backend skeleton for the MCC multi-platform AI product.",
)

app.include_router(health_router)


@app.get("/", tags=["root"])
def root() -> dict[str, str]:
    return {
        "service": "mcc-ai-platform",
        "environment": settings.app_env,
        "message": "Backend skeleton is running.",
    }
