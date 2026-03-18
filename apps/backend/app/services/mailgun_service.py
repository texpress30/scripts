from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests

from app.core.config import load_settings
from app.services.integration_secrets_store import IntegrationSecretValue, integration_secrets_store

_PROVIDER = "mailgun"
_SCOPE = "agency_default"
_REQUIRED_KEYS: tuple[str, ...] = ("api_key", "domain", "base_url", "from_email", "from_name")
_OPTIONAL_KEYS: tuple[str, ...] = ("reply_to", "enabled")
_CONFIG_SOURCE_DB = "db"
_CONFIG_SOURCE_ENV = "env"
_CONFIG_SOURCE_NONE = "none"


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

    def _build_config_from_values(self, values: dict[str, str]) -> MailgunConfig | None:
        normalized_api_key = _normalize_text(values.get("api_key", ""))
        normalized_domain = _normalize_text(values.get("domain", ""))
        normalized_base_url_raw = _normalize_text(values.get("base_url", ""))
        normalized_from_email_raw = _normalize_text(values.get("from_email", ""))
        normalized_from_name = _normalize_text(values.get("from_name", ""))
        normalized_reply_to_raw = _normalize_text(values.get("reply_to", ""))
        if (
            normalized_api_key == ""
            or normalized_domain == ""
            or normalized_base_url_raw == ""
            or normalized_from_email_raw == ""
            or normalized_from_name == ""
        ):
            return None

        try:
            normalized_base_url = _normalize_base_url(normalized_base_url_raw)
            normalized_from_email = _normalize_email(normalized_from_email_raw, field_name="from_email")
            normalized_reply_to = _normalize_email(normalized_reply_to_raw, field_name="reply_to") if normalized_reply_to_raw else ""
        except ValueError:
            return None

        enabled_raw = _normalize_text(values.get("enabled", "1")).lower()
        enabled = enabled_raw not in {"0", "false", "no", "off"}
        return MailgunConfig(
            api_key=normalized_api_key,
            domain=normalized_domain,
            base_url=normalized_base_url,
            from_email=normalized_from_email,
            from_name=normalized_from_name,
            reply_to=normalized_reply_to,
            enabled=enabled,
        )

    def _db_values(self) -> dict[str, str]:
        return {key: self._read_secret(key) for key in _REQUIRED_KEYS + _OPTIONAL_KEYS}

    def _env_values(self) -> dict[str, str]:
        settings = load_settings()
        return {
            "api_key": settings.mailgun_api_key,
            "domain": settings.mailgun_domain,
            "base_url": settings.mailgun_base_url,
            "from_email": settings.mailgun_from_email,
            "from_name": settings.mailgun_from_name,
            "reply_to": settings.mailgun_reply_to,
            "enabled": "1" if settings.mailgun_enabled else "0",
        }

    def _resolve_config(self) -> tuple[MailgunConfig | None, str]:
        env_config = self._build_config_from_values(self._env_values())
        if env_config is not None:
            return env_config, _CONFIG_SOURCE_ENV

        db_config = self._build_config_from_values(self._db_values())
        if db_config is not None:
            return db_config, _CONFIG_SOURCE_DB

        return None, _CONFIG_SOURCE_NONE

    def get_config(self) -> MailgunConfig | None:
        config, _source = self._resolve_config()
        return config

    def status(self) -> dict[str, object]:
        config, source = self._resolve_config()
        if config is None:
            return {
                "configured": False,
                "enabled": False,
                "config_source": _CONFIG_SOURCE_NONE,
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
            "config_source": source,
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

    def import_from_env(self) -> dict[str, object]:
        env_values = self._env_values()
        env_config = self._build_config_from_values(env_values)
        if env_config is None:
            raise ValueError("Config Mailgun incomplet în env (MAILGUN_API_KEY/DOMAIN/BASE_URL/FROM_EMAIL/FROM_NAME).")

        integration_secrets_store.upsert_secret(provider=_PROVIDER, secret_key="api_key", value=env_config.api_key, scope=_SCOPE)
        integration_secrets_store.upsert_secret(provider=_PROVIDER, secret_key="domain", value=env_config.domain, scope=_SCOPE)
        integration_secrets_store.upsert_secret(provider=_PROVIDER, secret_key="base_url", value=env_config.base_url, scope=_SCOPE)
        integration_secrets_store.upsert_secret(provider=_PROVIDER, secret_key="from_email", value=env_config.from_email, scope=_SCOPE)
        integration_secrets_store.upsert_secret(provider=_PROVIDER, secret_key="from_name", value=env_config.from_name, scope=_SCOPE)
        integration_secrets_store.upsert_secret(provider=_PROVIDER, secret_key="reply_to", value=env_config.reply_to, scope=_SCOPE)
        integration_secrets_store.upsert_secret(provider=_PROVIDER, secret_key="enabled", value="1" if env_config.enabled else "0", scope=_SCOPE)

        payload = self.status()
        return {
            "imported": True,
            "message": "Configurația Mailgun din env a fost sincronizată în DB (utilitar legacy).",
            **payload,
        }

    def assert_available(self) -> MailgunConfig:
        config = self.get_config()
        if config is None:
            raise MailgunIntegrationError("Mailgun nu este configurat", status_code=503)
        if not config.enabled:
            raise MailgunIntegrationError("Integrarea Mailgun este dezactivată", status_code=503)
        return config

    def send_email(self, *, to_email: str, subject: str, text: str, html: str | None = None) -> dict[str, object]:
        config = self.assert_available()

        normalized_to = _normalize_email(to_email, field_name="to_email")
        normalized_subject = _normalize_text(subject)
        normalized_text = _normalize_text(text)
        if normalized_subject == "":
            raise ValueError("subject este obligatoriu")
        if normalized_text == "":
            raise ValueError("text este obligatoriu")

        request_url = f"{config.base_url}/v3/{config.domain}/messages"
        normalized_html = "" if html is None else str(html)
        form_data: dict[str, str] = {
            "from": f"{config.from_name} <{config.from_email}>",
            "to": normalized_to,
            "subject": normalized_subject,
            "text": normalized_text,
        }
        if normalized_html.strip() != "":
            form_data["html"] = normalized_html
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
        external_message = "accepted"
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
            "accepted": True,
            "delivery_status": "accepted",
            "provider_message": external_message,
            "provider_id": external_id,
            "message": external_message,
            "id": external_id,
            "to_email": normalized_to,
            "subject": normalized_subject,
            "sent_at": datetime.now(tz=timezone.utc).isoformat(),
        }

    def send_test_email(self, *, to_email: str, subject: str | None, text: str | None) -> dict[str, object]:
        normalized_subject = _normalize_text(subject or "") or "Mailgun test email"
        normalized_text = _normalize_text(text or "") or "Acesta este un email de test trimis din platformă."
        return self.send_email(to_email=to_email, subject=normalized_subject, text=normalized_text)


mailgun_service = MailgunService()
