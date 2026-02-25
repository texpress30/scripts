from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import enforce_action_scope, get_current_user
from app.services.audit import audit_log_service
from app.services.auth import AuthUser
from app.services.google_ads import GoogleAdsIntegrationError, google_ads_service

router = APIRouter(prefix="/integrations/google", tags=["google"])


@router.get("/accounts")
def list_google_accounts_alias(user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    enforce_action_scope(user=user, action="integrations:status", scope="agency")
    try:
        accounts = google_ads_service.list_accessible_customers()
    except GoogleAdsIntegrationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="google_ads.accounts.list.alias",
        resource="integration:google_ads",
        details={"count": len(accounts)},
    )
    return {"items": accounts, "count": len(accounts)}
