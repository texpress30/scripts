from fastapi import APIRouter, HTTPException, status

from app.schemas.auth import LoginRequest, LoginResponse
from app.services.audit import audit_log_service
from app.services.auth import create_access_token, validate_login_credentials
from app.services.rate_limiter import RateLimitExceeded, rate_limiter_service
from app.services.rbac import ROLE_PERMISSIONS

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest) -> LoginResponse:
    email = payload.email.strip().lower()
    role = payload.role.strip().lower()

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

    if role not in ROLE_PERMISSIONS:
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
