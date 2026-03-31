import logging
import time
from time import perf_counter

try:
    import psycopg
except ImportError:
    psycopg = None

from app.db.pool import open_pool, close_pool

logger = logging.getLogger(__name__)

from fastapi import FastAPI
from fastapi import Request
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
from app.services.subaccount_business_profile_store import subaccount_business_profile_store
from app.services.auth_email_tokens import auth_email_tokens_service
from app.services.email_templates import email_templates_service
from app.services.email_notifications import email_notifications_service
from app.services.team_members import team_members_service
from app.services.performance_reports import performance_reports_store
from app.services.sync_runs_store import sync_runs_store
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


@app.middleware("http")
async def request_timing_middleware(request: Request, call_next):
    start = perf_counter()
    response = await call_next(request)
    duration_ms = (perf_counter() - start) * 1000.0
    response.headers["X-Process-Time-Ms"] = f"{duration_ms:.2f}"

    # Lightweight observability for p95/p99 by route/method/status.
    route_label = request.url.path
    logger.info(
        "http_request method=%s path=%s status=%s duration_ms=%.2f",
        request.method,
        route_label,
        response.status_code,
        duration_ms,
    )
    return response

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
        is_sqlite = settings.database_url.startswith("sqlite")

        max_retries = 5
        for attempt in range(max_retries):
            try:
                open_pool(settings.database_url)
                logger.info("Successfully connected to the database on startup.")
                break
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error("Failed to connect to the database after %d attempts.", max_retries)
                    raise
                logger.warning("Database connection failed (attempt %d/%d): %s. Retrying in 3 seconds...", attempt + 1, max_retries, e)
                time.sleep(3)

        if not is_sqlite:
            from app.db.pool import get_connection

            with get_connection() as conn:
                with conn.cursor() as cur:
                    # Transaction-scoped lock: released on commit, safe for pooled connections.
                    cur.execute("SELECT pg_try_advisory_xact_lock(1, hashtext('global_schema_init'))")
                    cur.fetchone()
                conn.commit()

    client_registry_service.initialize_schema()
    user_profile_service.initialize_schema()
    team_members_service.initialize_schema()
    company_settings_service.initialize_schema()
    subaccount_business_profile_store.initialize_schema()
    auth_email_tokens_service.initialize_schema()
    email_templates_service.initialize_schema()
    email_notifications_service.initialize_schema()
    performance_reports_store.initialize_schema()

    try:
        result = sync_runs_store.cleanup_rate_limit_errors(hours_back=72)
        deleted_runs = result.get("deleted_runs", 0)
        deleted_chunks = result.get("deleted_chunks", 0)
        reset_accounts = result.get("reset_accounts", 0)
        logger.info(
            "[STARTUP-CLEANUP] Deleted %d rate-limit error runs, %d chunks, reset %d accounts",
            deleted_runs,
            deleted_chunks,
            reset_accounts,
        )
    except Exception:
        logger.exception("[STARTUP-CLEANUP] Failed to run rate-limit error cleanup")


@app.on_event("shutdown")
def shutdown_event() -> None:
    close_pool()
