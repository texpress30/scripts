from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_current_user
from app.schemas.auth import ImpersonateRequest, ImpersonateResponse, LoginRequest, LoginResponse
from app.services.audit import audit_log_service
from app.services.auth import AuthUser, create_access_token, validate_login_credentials
from app.services.rate_limiter import RateLimitExceeded, rate_limiter_service
from app.services.rbac import is_supported_role, normalize_role

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest) -> LoginResponse:
    email = payload.email.strip().lower()
    role = normalize_role(payload.role)

    try:
        rate_limiter_service.check(f"auth:{email}", limit=20, window_seconds=60)
    except RateLimitExceeded as exc:
        audit_log_service.log(
            actor_email=email,
            actor_role="anonymous",
            action="auth.login.rate_limited",
            resource="auth:login",
            details={"role": role},
        )
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc

    if not is_supported_role(payload.role):
        audit_log_service.log(
            actor_email=email,
            actor_role="anonymous",
            action="auth.login.failed",
            resource="auth:login",
            details={"reason": "unsupported_role", "role": payload.role},
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unsupported role: {payload.role}")

    if not validate_login_credentials(payload.email, payload.password):
        audit_log_service.log(
            actor_email=email,
            actor_role=role,
            action="auth.login.failed",
            resource="auth:login",
            details={"reason": "invalid_credentials"},
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    access_token = create_access_token(email=payload.email, role=role)
    audit_log_service.log(
        actor_email=email,
        actor_role=role,
        action="auth.login.succeeded",
        resource="auth:login",
        details={"role": role},
    )
    return LoginResponse(access_token=access_token)


@router.post("/impersonate", response_model=ImpersonateResponse)
def impersonate(payload: ImpersonateRequest, user: AuthUser = Depends(get_current_user)) -> ImpersonateResponse:
    actor_role = normalize_role(user.role)
    if actor_role not in {"super_admin", "agency_owner", "agency_admin"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admin roles can impersonate users")

    target_role = normalize_role(payload.role)
    if not is_supported_role(payload.role):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unsupported role: {payload.role}")

    target_email = payload.email.strip().lower()
    access_token = create_access_token(email=target_email, role=target_role)
    audit_log_service.log(
        actor_email=user.email,
        actor_role=actor_role,
        action="auth.impersonate.succeeded",
        resource="auth:impersonate",
        details={"target_email": target_email, "target_role": target_role},
    )
    return ImpersonateResponse(access_token=access_token)
