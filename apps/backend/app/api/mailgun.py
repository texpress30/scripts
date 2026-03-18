from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.dependencies import enforce_action_scope, get_current_user
from app.services.audit import audit_log_service
from app.services.auth import AuthUser
from app.services.mailgun_service import MailgunIntegrationError, mailgun_service

router = APIRouter(prefix="/agency/integrations/mailgun", tags=["mailgun", "integrations"])


class MailgunConfigRequest(BaseModel):
    api_key: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    base_url: str = Field(min_length=1)
    from_email: str = Field(min_length=3)
    from_name: str = Field(min_length=1)
    reply_to: str = ""
    enabled: bool = True


class MailgunTestRequest(BaseModel):
    to_email: str = Field(min_length=3)
    subject: str = ""
    text: str = ""


@router.get("/status")
def mailgun_status(user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    enforce_action_scope(user=user, action="integrations:status", scope="agency")
    status_payload = mailgun_service.status()
    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="mailgun.status",
        resource="integration:mailgun",
        details={"configured": bool(status_payload.get("configured")), "enabled": bool(status_payload.get("enabled"))},
    )
    return status_payload


@router.post("/config")
def save_mailgun_config(payload: MailgunConfigRequest, user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    enforce_action_scope(user=user, action="integrations:mailgun:config", scope="agency")
    try:
        response_payload = mailgun_service.upsert_config(
            api_key=payload.api_key,
            domain=payload.domain,
            base_url=payload.base_url,
            from_email=payload.from_email,
            from_name=payload.from_name,
            reply_to=payload.reply_to,
            enabled=payload.enabled,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="mailgun.config.saved",
        resource="integration:mailgun",
        details={
            "enabled": bool(response_payload.get("enabled")),
            "domain": response_payload.get("domain"),
            "base_url": response_payload.get("base_url"),
            "from_email": response_payload.get("from_email"),
        },
    )
    return response_payload


@router.post("/import-from-env")
def import_mailgun_config_from_env(user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    enforce_action_scope(user=user, action="integrations:mailgun:config", scope="agency")
    try:
        response_payload = mailgun_service.import_from_env()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="mailgun.config.import_from_env",
        resource="integration:mailgun",
        details={
            "imported": bool(response_payload.get("imported")),
            "config_source": response_payload.get("config_source"),
            "enabled": bool(response_payload.get("enabled")),
            "domain": response_payload.get("domain"),
            "from_email": response_payload.get("from_email"),
        },
    )
    return response_payload


@router.post("/test")
def send_mailgun_test(payload: MailgunTestRequest, user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    enforce_action_scope(user=user, action="integrations:mailgun:test", scope="agency")
    try:
        response_payload = mailgun_service.send_test_email(
            to_email=payload.to_email,
            subject=payload.subject,
            text=payload.text,
        )
    except ValueError as exc:
        audit_log_service.log(
            actor_email=user.email,
            actor_role=user.role,
            action="mailgun.test.failed",
            resource="integration:mailgun",
            details={"reason": str(exc)[:200]},
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except MailgunIntegrationError as exc:
        audit_log_service.log(
            actor_email=user.email,
            actor_role=user.role,
            action="mailgun.test.failed",
            resource="integration:mailgun",
            details={"reason": str(exc)[:200], "status_code": exc.status_code},
        )
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="mailgun.test.success",
        resource="integration:mailgun",
        details={"to_email": response_payload.get("to_email"), "subject": response_payload.get("subject")},
    )
    return response_payload
