from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.audit import router as audit_router
from app.api.insights import router as insights_router
from app.api.ai import router as ai_router
from app.api.agency_clients_google_ads import router as agency_clients_google_ads_router
from app.api.auth import router as auth_router
from app.api.clients import router as clients_router
from app.api.creative import router as creative_router
from app.api.company import router as company_router
from app.api.dashboard import router as dashboard_router
from app.api.exports import router as exports_router
from app.api.google_ads import router as google_ads_router
from app.api.google_accounts import router as google_accounts_router
from app.api.health import router as health_router
from app.api.meta_ads import router as meta_ads_router
from app.api.pinterest_ads import router as pinterest_ads_router
from app.api.snapchat_ads import router as snapchat_ads_router
from app.api.storage import router as storage_router
from app.api.team import router as team_router
from app.api.tiktok_ads import router as tiktok_ads_router
from app.api.user_profile import router as user_profile_router
from app.api.rules import router as rules_router
from app.core.config import load_settings
from app.services.client_registry import client_registry_service
from app.services.company_settings import company_settings_service
from app.services.team_members import team_members_service
from app.services.user_profile import user_profile_service

settings = load_settings()

app = FastAPI(
    title="MCC AI Platform API",
    version="0.7.1",
    description="Backend skeleton with Sprint 1 (auth/RBAC/audit) and Sprint 2 (Google Ads sync/dashboard) and Sprint 3 (Meta Ads + unified dashboard) and Sprint 4 (rules engine automation) and Sprint 5 (AI assistant + weekly insights) and Sprint 6 (BigQuery export + hardening).",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_origin_regex=settings.cors_origin_regex,
)

# Core
app.include_router(health_router)

# Sprint 1
app.include_router(auth_router)
app.include_router(clients_router)
app.include_router(agency_clients_google_ads_router)
app.include_router(audit_router)

# Sprint 2
app.include_router(google_ads_router)
app.include_router(google_accounts_router)
app.include_router(meta_ads_router)
app.include_router(tiktok_ads_router)
app.include_router(pinterest_ads_router)
app.include_router(snapchat_ads_router)
app.include_router(dashboard_router)

# Sprint 4
app.include_router(rules_router)

# Sprint 5
app.include_router(ai_router)
app.include_router(insights_router)

# Sprint 6
app.include_router(exports_router)

# Sprint 7
app.include_router(creative_router)
app.include_router(company_router)
app.include_router(user_profile_router)
app.include_router(team_router)
app.include_router(storage_router)


@app.get("/", tags=["root"])
def root() -> dict[str, str]:
    return {
        "service": "mcc-ai-platform",
        "environment": settings.app_env,
        "message": "Backend skeleton is running.",
    }


@app.on_event("startup")
def initialize_client_registry_schema() -> None:
    client_registry_service.initialize_schema()
    user_profile_service.initialize_schema()
    team_members_service.initialize_schema()
    company_settings_service.initialize_schema()
