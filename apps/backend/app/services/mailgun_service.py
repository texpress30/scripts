from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests

from app.services.integration_secrets_store import IntegrationSecretValue, integration_secrets_store

_PROVIDER = "mailgun"
_SCOPE = "agency_default"
_REQUIRED_KEYS: tuple[str, ...] = ("api_key", "domain", "base_url", "from_email", "from_name")
_OPTIONAL_KEYS: tuple[str, ...] = ("reply_to", "enabled")


class MailgunIntegrationError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class MailgunConfig:
    api_key: str
    domain: str
    base_url: str
    from_email: str
    from_name: str
    reply_to: str
    enabled: bool


def _normalize_text(value: str) -> str:
    return str(value or "").strip()


def _normalize_base_url(value: str) -> str:
    raw = _normalize_text(value).rstrip("/")
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or parsed.netloc == "":
        raise ValueError("base_url trebuie să fie un URL valid")
    return raw


def _normalize_email(value: str, *, field_name: str) -> str:
    candidate = _normalize_text(value).lower()
    if candidate == "" or "@" not in candidate or candidate.startswith("@") or candidate.endswith("@"):
        raise ValueError(f"{field_name} invalid")
    return candidate


def _mask_api_key(value: str) -> str:
    normalized = _normalize_text(value)
    if normalized == "":
        return ""
    if len(normalized) <= 6:
        return "*" * len(normalized)
    return f"{normalized[:3]}***{normalized[-3:]}"


def _safe_secret_value(secret: IntegrationSecretValue | None) -> str:
    if secret is None:
        return ""
    return _normalize_text(secret.value)


class MailgunService:
    def _read_secret(self, key: str) -> str:
        return _safe_secret_value(integration_secrets_store.get_secret(provider=_PROVIDER, secret_key=key, scope=_SCOPE))

    def get_config(self) -> MailgunConfig | None:
        values = {key: self._read_secret(key) for key in _REQUIRED_KEYS + _OPTIONAL_KEYS}
        if any(values[key] == "" for key in _REQUIRED_KEYS):
            return None
        enabled_raw = values.get("enabled", "1").strip().lower()
        enabled = enabled_raw not in {"0", "false", "no", "off"}
        return MailgunConfig(
            api_key=values["api_key"],
            domain=values["domain"],
            base_url=values["base_url"],
            from_email=values["from_email"],
            from_name=values["from_name"],
            reply_to=values.get("reply_to", ""),
            enabled=enabled,
        )

    def status(self) -> dict[str, object]:
        config = self.get_config()
        if config is None:
            return {
                "configured": False,
                "enabled": False,
                "domain": "",
                "base_url": "",
                "from_email": "",
                "from_name": "",
                "reply_to": "",
                "api_key_masked": "",
            }
        return {
            "configured": True,
            "enabled": config.enabled,
            "domain": config.domain,
            "base_url": config.base_url,
            "from_email": config.from_email,
            "from_name": config.from_name,
            "reply_to": config.reply_to,
            "api_key_masked": _mask_api_key(config.api_key),
        }

    def upsert_config(
        self,
        *,
        api_key: str,
        domain: str,
        base_url: str,
        from_email: str,
        from_name: str,
        reply_to: str | None,
        enabled: bool,
    ) -> dict[str, object]:
        normalized_api_key = _normalize_text(api_key)
        normalized_domain = _normalize_text(domain)
        normalized_base_url = _normalize_base_url(base_url)
        normalized_from_email = _normalize_email(from_email, field_name="from_email")
        normalized_from_name = _normalize_text(from_name)
        normalized_reply_to = _normalize_email(reply_to or "", field_name="reply_to") if _normalize_text(reply_to or "") else ""

        if normalized_api_key == "":
            raise ValueError("api_key este obligatoriu")
        if normalized_domain == "":
            raise ValueError("domain este obligatoriu")
        if normalized_from_name == "":
            raise ValueError("from_name este obligatoriu")

        integration_secrets_store.upsert_secret(provider=_PROVIDER, secret_key="api_key", value=normalized_api_key, scope=_SCOPE)
        integration_secrets_store.upsert_secret(provider=_PROVIDER, secret_key="domain", value=normalized_domain, scope=_SCOPE)
        integration_secrets_store.upsert_secret(provider=_PROVIDER, secret_key="base_url", value=normalized_base_url, scope=_SCOPE)
        integration_secrets_store.upsert_secret(provider=_PROVIDER, secret_key="from_email", value=normalized_from_email, scope=_SCOPE)
        integration_secrets_store.upsert_secret(provider=_PROVIDER, secret_key="from_name", value=normalized_from_name, scope=_SCOPE)
        integration_secrets_store.upsert_secret(provider=_PROVIDER, secret_key="reply_to", value=normalized_reply_to, scope=_SCOPE)
        integration_secrets_store.upsert_secret(provider=_PROVIDER, secret_key="enabled", value="1" if enabled else "0", scope=_SCOPE)

        return self.status()

    def send_test_email(self, *, to_email: str, subject: str | None, text: str | None) -> dict[str, object]:
        config = self.get_config()
        if config is None:
            raise MailgunIntegrationError("Mailgun nu este configurat", status_code=404)
        if not config.enabled:
            raise MailgunIntegrationError("Integrarea Mailgun este dezactivată", status_code=400)

        normalized_to = _normalize_email(to_email, field_name="to_email")
        normalized_subject = _normalize_text(subject or "") or "Mailgun test email"
        normalized_text = _normalize_text(text or "") or "Acesta este un email de test trimis din platformă."

        request_url = f"{config.base_url}/v3/{config.domain}/messages"
        form_data: dict[str, str] = {
            "from": f"{config.from_name} <{config.from_email}>",
            "to": normalized_to,
            "subject": normalized_subject,
            "text": normalized_text,
        }
        if config.reply_to:
            form_data["h:Reply-To"] = config.reply_to

        try:
            response = requests.post(
                request_url,
                auth=("api", config.api_key),
                data=form_data,
                timeout=10,
            )
        except requests.RequestException as exc:
            raise MailgunIntegrationError(f"Mailgun request failed: {str(exc)[:240]}", status_code=502) from exc

        if not response.ok:
            message = "Mailgun request failed"
            try:
                payload = response.json()
                if isinstance(payload, dict):
                    parsed = _normalize_text(str(payload.get("message") or ""))
                    if parsed:
                        message = parsed
            except Exception:  # noqa: BLE001
                raw = _normalize_text(response.text)
                if raw:
                    message = raw[:240]
            raise MailgunIntegrationError(f"Mailgun error ({response.status_code}): {message}", status_code=502)

        external_id = ""
        external_message = "sent"
        try:
            payload = response.json()
            if isinstance(payload, dict):
                external_id = _normalize_text(str(payload.get("id") or ""))
                parsed_message = _normalize_text(str(payload.get("message") or ""))
                if parsed_message:
                    external_message = parsed_message
        except Exception:  # noqa: BLE001
            pass

        return {
            "ok": True,
            "message": external_message,
            "id": external_id,
            "to_email": normalized_to,
            "subject": normalized_subject,
            "sent_at": datetime.now(tz=timezone.utc).isoformat(),
        }


mailgun_service = MailgunService()
