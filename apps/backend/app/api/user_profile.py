from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_current_user
from app.schemas.user_profile import UpdatePasswordRequest, UpdateUserProfileRequest, UserProfileResponse
from app.services.auth import AuthUser
from app.services.user_profile import user_profile_service

router = APIRouter(prefix="/user", tags=["user-profile"])


@router.get("/profile", response_model=UserProfileResponse)
def get_profile(user: AuthUser = Depends(get_current_user)) -> UserProfileResponse:
    profile = user_profile_service.get_profile(email=user.email.strip().lower())
    return UserProfileResponse(**profile)


@router.patch("/profile", response_model=UserProfileResponse)
def update_profile(payload: UpdateUserProfileRequest, user: AuthUser = Depends(get_current_user)) -> UserProfileResponse:
    if payload.first_name.strip() == "":
        raise HTTPException(status_code=400, detail="First name cannot be left blank")
    if payload.last_name.strip() == "":
        raise HTTPException(status_code=400, detail="Last name cannot be left blank")

    profile = user_profile_service.update_profile(
        email=user.email.strip().lower(),
        first_name=payload.first_name.strip(),
        last_name=payload.last_name.strip(),
        phone=payload.phone.strip(),
        extension=payload.extension.strip(),
        platform_language=payload.platform_language,
    )
    return UserProfileResponse(**profile)


@router.post("/profile/password")
def update_password(payload: UpdatePasswordRequest, user: AuthUser = Depends(get_current_user)) -> dict[str, str]:
    if payload.password.strip() == "" or payload.confirm_password.strip() == "":
        raise HTTPException(status_code=400, detail="Password fields are required")
    if payload.password != payload.confirm_password:
        raise HTTPException(status_code=400, detail="Password and confirmation do not match")

    try:
        user_profile_service.update_password(
            email=user.email.strip().lower(),
            current_password=payload.current_password,
            password=payload.password,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"status": "ok"}
