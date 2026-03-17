from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_current_user
from app.schemas.auth import (
    ImpersonateRequest,
    ImpersonateResponse,
    LoginRequest,
    LoginResponse,
    ResetPasswordConfirmRequest,
    ResetPasswordConfirmResponse,
)
from app.services.audit import audit_log_service
from app.services.auth import (
    AuthLoginError,
    AuthUser,
    authenticate_user_from_db,
    create_access_token,
    set_user_password,
    validate_login_credentials,
    validate_new_password,
)
from app.services.auth_email_tokens import AuthEmailTokenError, auth_email_tokens_service
from app.services.rate_limiter import RateLimitExceeded, rate_limiter_service
from app.services.rbac import is_supported_role, normalize_role

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest) -> LoginResponse:
    email = payload.email.strip().lower()
    requested_role = normalize_role(payload.role)

    try:
        rate_limiter_service.check(f"auth:{email}", limit=20, window_seconds=60)
    except RateLimitExceeded as exc:
        audit_log_service.log(
            actor_email=email,
            actor_role="anonymous",
            action="auth.login.rate_limited",
            resource="auth:login",
            details={"role": requested_role},
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

    try:
        db_user = authenticate_user_from_db(email=payload.email, password=payload.password, requested_role=payload.role)
        access_token = create_access_token(
            email=db_user.email,
            role=db_user.role,
            user_id=db_user.user_id,
            scope_type=db_user.scope_type,
            membership_id=db_user.membership_id,
            subaccount_id=db_user.subaccount_id,
            subaccount_name=db_user.subaccount_name,
            is_env_admin=db_user.is_env_admin,
        )
        audit_log_service.log(
            actor_email=email,
            actor_role=db_user.role,
            action="auth.login.succeeded",
            resource="auth:login",
            details={
                "source": "db",
                "role": db_user.role,
                "membership_id": db_user.membership_id,
                "scope_type": db_user.scope_type,
                "subaccount_id": db_user.subaccount_id,
            },
        )
        return LoginResponse(access_token=access_token)
    except AuthLoginError as db_exc:
        if validate_login_credentials(payload.email, payload.password):
            access_token = create_access_token(
                email=email,
                role="super_admin",
                scope_type="agency",
                is_env_admin=True,
            )
            audit_log_service.log(
                actor_email=email,
                actor_role="super_admin",
                action="auth.login.succeeded",
                resource="auth:login",
                details={"source": "env_fallback", "requested_role": requested_role},
            )
            return LoginResponse(access_token=access_token)

        audit_log_service.log(
            actor_email=email,
            actor_role=requested_role,
            action="auth.login.failed",
            resource="auth:login",
            details={"reason": db_exc.reason, "status_code": db_exc.status_code},
        )
        raise HTTPException(status_code=db_exc.status_code, detail=db_exc.message) from db_exc


@router.post("/reset-password/confirm", response_model=ResetPasswordConfirmResponse)
def reset_password_confirm(payload: ResetPasswordConfirmRequest) -> ResetPasswordConfirmResponse:
    try:
        validate_new_password(payload.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    try:
        token_payload = auth_email_tokens_service.validate_password_reset_token(raw_token=payload.token)
    except AuthEmailTokenError as exc:
        audit_log_service.log(
            actor_email="anonymous",
            actor_role="anonymous",
            action="auth.reset_password.failed",
            resource="auth:reset_password",
            details={"reason": exc.reason},
        )
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    try:
        set_user_password(user_id=token_payload.user_id, new_password=payload.new_password)
    except ValueError as exc:
        audit_log_service.log(
            actor_email=token_payload.email,
            actor_role="anonymous",
            action="auth.reset_password.failed",
            resource="auth:reset_password",
            details={"reason": "user_not_resettable"},
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    try:
        consumed_token = auth_email_tokens_service.consume_password_reset_token(raw_token=payload.token)
    except AuthEmailTokenError as exc:
        audit_log_service.log(
            actor_email=token_payload.email,
            actor_role="anonymous",
            action="auth.reset_password.failed",
            resource="auth:reset_password",
            details={"reason": exc.reason},
        )
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    auth_email_tokens_service.invalidate_active_tokens(
        user_id=consumed_token.user_id,
        token_type=consumed_token.token_type,
        exclude_token_id=consumed_token.id,
    )

    audit_log_service.log(
        actor_email=consumed_token.email,
        actor_role="anonymous",
        action="auth.reset_password.success",
        resource="auth:reset_password",
        details={"user_id": consumed_token.user_id},
    )
    return ResetPasswordConfirmResponse(message="Parola a fost resetată cu succes")


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
