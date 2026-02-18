from fastapi import APIRouter, HTTPException, status

from app.schemas.auth import LoginRequest, LoginResponse
from app.services.auth import create_access_token
from app.services.rate_limiter import RateLimitExceeded, rate_limiter_service
from app.services.rbac import ROLE_PERMISSIONS

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest) -> LoginResponse:
    try:
        rate_limiter_service.check(f"auth:{payload.email}", limit=20, window_seconds=60)
    except RateLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc

    role = payload.role.strip().lower()
    if role not in ROLE_PERMISSIONS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unsupported role: {payload.role}")

    access_token = create_access_token(email=payload.email, role=role)
    return LoginResponse(access_token=access_token)
