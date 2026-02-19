from fastapi import APIRouter

from app.core.config import load_settings

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", summary="Health check")
def health_check() -> dict[str, str]:
    settings = load_settings()
    return {"status": "ok", "env": settings.app_env}
