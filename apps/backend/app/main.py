from fastapi import FastAPI

from app.api.audit import router as audit_router
from app.api.auth import router as auth_router
from app.api.clients import router as clients_router
from app.api.dashboard import router as dashboard_router
from app.api.google_ads import router as google_ads_router
from app.api.health import router as health_router
from app.api.meta_ads import router as meta_ads_router
from app.core.config import load_settings

app = FastAPI(
    title="MCC AI Platform API",
    version="0.3.0",
    description="Backend skeleton with Sprint 1 (auth/RBAC/audit) and Sprint 2 (Google Ads sync/dashboard) and Sprint 3 (Meta Ads + unified dashboard).",
)

# Core
app.include_router(health_router)

# Sprint 1
app.include_router(auth_router)
app.include_router(clients_router)
app.include_router(audit_router)

# Sprint 2
app.include_router(google_ads_router)
app.include_router(meta_ads_router)
app.include_router(dashboard_router)


@app.get("/", tags=["root"])
def root() -> dict[str, str]:
    settings = load_settings()
    return {
        "service": "mcc-ai-platform",
        "environment": settings.app_env,
        "message": "Backend skeleton is running.",
    }
