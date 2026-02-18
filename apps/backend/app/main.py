from fastapi import FastAPI

from app.api.audit import router as audit_router
from app.api.auth import router as auth_router
from app.api.clients import router as clients_router
from app.api.health import router as health_router
from app.core.config import load_settings

app = FastAPI(
    title="MCC AI Platform API",
    version="0.2.0",
    description="Phase 0/1 backend skeleton for the MCC multi-platform AI product.",
)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(clients_router)
app.include_router(audit_router)


@app.get("/", tags=["root"])
def root() -> dict[str, str]:
    settings = load_settings()
    return {
        "service": "mcc-ai-platform",
        "environment": settings.app_env,
        "message": "Backend skeleton is running.",
    }
