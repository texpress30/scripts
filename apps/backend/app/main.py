import logging
import time

try:
    import psycopg
except ImportError:
    psycopg = None

logger = logging.getLogger(__name__)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.audit import router as audit_router
from app.api.insights import router as insights_router
from app.api.ai import router as ai_router
from app.api.agency_clients_google_ads import router as agency_clients_google_ads_router
from app.api.auth import router as auth_router
from app.api.clients import router as clients_router
from app.api.campaigns import router as campaigns_router
from app.api.creative import router as creative_router
from app.api.company import router as company_router
from app.api.dashboard import router as dashboard_router
from app.api.email_notifications import router as email_notifications_router
from app.api.email_templates import router as email_templates_router
from app.api.exports import router as exports_router
from app.api.google_ads import router as google_ads_router
from app.api.google_accounts import router as google_accounts_router
from app.api.health import router as health_router
from app.api.meta_ads import router as meta_ads_router
from app.api.mailgun import router as mailgun_router
from app.api.pinterest_ads import router as pinterest_ads_router
from app.api.snapchat_ads import router as snapchat_ads_router
from app.api.storage import router as storage_router
from app.api.sync_orchestration import router as sync_orchestration_router
from app.api.team import router as team_router
from app.api.tiktok_ads import router as tiktok_ads_router
from app.api.user_profile import router as user_profile_router
from app.api.rules import router as rules_router
from app.core.config import load_settings
from app.services.client_registry import client_registry_service
from app.services.company_settings import company_settings_service
from app.services.auth_email_tokens import auth_email_tokens_service
from app.services.email_templates import email_templates_service
from app.services.email_notifications import email_notifications_service
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
app.include_router(mailgun_router)
app.include_router(tiktok_ads_router)
app.include_router(pinterest_ads_router)
app.include_router(snapchat_ads_router)
app.include_router(dashboard_router)
app.include_router(campaigns_router)
app.include_router(email_templates_router)
app.include_router(email_notifications_router)

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
app.include_router(sync_orchestration_router)


@app.get("/", tags=["root"])
def root() -> dict[str, str]:
    return {
        "service": "mcc-ai-platform",
        "environment": settings.app_env,
        "message": "Backend skeleton is running.",
    }


@app.on_event("startup")
def startup_event() -> None:
    if psycopg is not None:
        max_retries = 5
        acquired_lock = False
        global_conn = None

        for attempt in range(max_retries):
            try:
                global_conn = psycopg.connect(settings.database_url)
                with global_conn.cursor() as cur:
                    cur.execute("SELECT pg_try_advisory_lock(1, hashtext('global_schema_init'))")
                    acquired_lock = bool(cur.fetchone()[0])
                global_conn.commit()
                logger.info("Successfully connected to the database on startup.")
                break
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error("Failed to connect to the database after %d attempts.", max_retries)
                    raise
                logger.warning("Database connection failed (attempt %d/%d): %s. Retrying in 3 seconds...", attempt + 1, max_retries, e)
                time.sleep(3)

        if not acquired_lock:
            logger.info("Database schema is being initialized by another worker. Skipping locally.")
            if global_conn is not None:
                global_conn.close()
            return

        try:
            logger.info("Initializing runtime DB schema...")
            client_registry_service.initialize_schema()
            user_profile_service.initialize_schema()
            team_members_service.initialize_schema()
            company_settings_service.initialize_schema()
            auth_email_tokens_service.initialize_schema()
            email_templates_service.initialize_schema()
            email_notifications_service.initialize_schema()
        finally:
            if global_conn is not None:
                try:
                    with global_conn.cursor() as cur:
                        cur.execute("SELECT pg_advisory_unlock(1, hashtext('global_schema_init'))")
                    global_conn.commit()
                except Exception as unlock_err:
                    logger.error(f"Failed to release global schema lock: {unlock_err}")
                finally:
                    global_conn.close()
