from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.core.config import load_settings

try:
    import psycopg
except Exception:  # noqa: BLE001
    psycopg = None


AGENCY_DEFAULT_SCOPE_KEY = "agency_default"


@dataclass(frozen=True)
class EmailTemplateCatalogItem:
    key: str
    label: str
    description: str
    default_subject: str
    default_text_body: str
    default_html_body: str
    available_variables: tuple[str, ...]
    scope: str = "agency"


@dataclass(frozen=True)
class EffectiveEmailTemplate:
    key: str
    label: str
    description: str
    subject: str
    text_body: str
    html_body: str
    available_variables: tuple[str, ...]
    scope: str
    enabled: bool
    is_overridden: bool
    updated_at: datetime | None


@dataclass(frozen=True)
class RenderedEmailTemplate:
    key: str
    subject: str
    text_body: str
    html_body: str
    enabled: bool
    available_variables: tuple[str, ...]


@dataclass(frozen=True)
class EmailTemplatePreviewResult:
    key: str
    rendered_subject: str
    rendered_text_body: str
    rendered_html_body: str
    sample_variables: dict[str, str]
    is_overridden: bool


@dataclass(frozen=True)
class EmailTemplateOverrideInput:
    subject: str
    text_body: str
    html_body: str
    enabled: bool


@dataclass(frozen=True)
class EmailTemplateTestSendResult:
    key: str
    to_email: str
    accepted: bool
    delivery_status: str
    rendered_subject: str
    provider_message: str
    provider_id: str


_CANONICAL_EMAIL_TEMPLATES: tuple[EmailTemplateCatalogItem, ...] = (
    EmailTemplateCatalogItem(
        key="auth_forgot_password",
        label="Auth · Forgot Password",
        description="Email trimis când utilizatorul solicită resetarea parolei.",
        default_subject="Resetează parola",
        default_text_body=(
            "Ai solicitat resetarea parolei.\n\n"
            "Folosește link-ul de mai jos pentru a seta o parolă nouă:\n"
            "{{reset_link}}\n\n"
            "Acest link expiră în {{expires_minutes}} minute."
        ),
        default_html_body=(
            "<p>Ai solicitat resetarea parolei.</p>"
            "<p>Folosește link-ul de mai jos pentru a seta o parolă nouă:</p>"
            "<p><a href=\"{{reset_link}}\">Resetează parola</a></p>"
            "<p>Acest link expiră în {{expires_minutes}} minute.</p>"
        ),
        available_variables=("reset_link", "expires_minutes", "user_email"),
    ),
    EmailTemplateCatalogItem(
        key="team_invite_user",
        label="Team · Invite User",
        description="Email trimis când un utilizator este invitat în echipă.",
        default_subject="Invitație în platformă",
        default_text_body=(
            "Ai fost invitat în platformă.\n\n"
            "Folosește link-ul de activare:\n"
            "{{invite_link}}\n\n"
            "Invitația expiră în {{expires_minutes}} minute."
        ),
        default_html_body=(
            "<p>Ai fost invitat în platformă.</p>"
            "<p>Folosește link-ul de activare:</p>"
            "<p><a href=\"{{invite_link}}\">Activează contul</a></p>"
            "<p>Invitația expiră în {{expires_minutes}} minute.</p>"
        ),
        available_variables=("invite_link", "expires_minutes", "user_email"),
    ),
    EmailTemplateCatalogItem(
        key="team_account_ready",
        label="Team · Account Ready",
        description="Email trimis când utilizatorul are deja parolă setată și poate intra direct în login.",
        default_subject="Contul tău este pregătit",
        default_text_body=(
            "Contul tău este pregătit.\n\n"
            "Te poți autentifica folosind adresa {{user_email}}:\n"
            "{{login_link}}"
        ),
        default_html_body=(
            "<p>Contul tău este pregătit.</p>"
            "<p>Te poți autentifica folosind adresa <strong>{{user_email}}</strong>.</p>"
            "<p><a href=\"{{login_link}}\">Mergi la login</a></p>"
        ),
        available_variables=("login_link", "user_email"),
    ),
)

_CANONICAL_SAMPLE_VARIABLES: dict[str, dict[str, str]] = {
    "auth_forgot_password": {
        "reset_link": "https://app.example.com/reset-password?token=preview-token",
        "expires_minutes": "60",
        "user_email": "preview.user@example.com",
    },
    "team_invite_user": {
        "invite_link": "https://app.example.com/activate-invite?token=preview-token",
        "expires_minutes": "60",
        "user_email": "preview.user@example.com",
    },
    "team_account_ready": {
        "login_link": "https://app.example.com/login",
        "user_email": "preview.user@example.com",
    },
}


class EmailTemplatesService:
    def _connect(self):
        settings = load_settings()
        if psycopg is None:
            raise RuntimeError("psycopg is required for email template persistence")
        return psycopg.connect(settings.database_url)

    def initialize_schema(self) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS agency_email_templates (
                        id BIGSERIAL PRIMARY KEY,
                        template_key TEXT NOT NULL,
                        scope_key TEXT NOT NULL DEFAULT 'agency_default',
                        subject_override TEXT NOT NULL,
                        text_body_override TEXT NOT NULL,
                        html_body_override TEXT NOT NULL DEFAULT '',
                        enabled BOOLEAN NOT NULL DEFAULT TRUE,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        CONSTRAINT agency_email_templates_unique_scope_template UNIQUE (template_key, scope_key)
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_agency_email_templates_template_key
                    ON agency_email_templates(template_key)
                    """
                )
                cur.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_agency_email_templates_scope_key
                    ON agency_email_templates(scope_key)
                    """
                )
            conn.commit()

    def list_templates(self) -> list[EmailTemplateCatalogItem]:
        return list(_CANONICAL_EMAIL_TEMPLATES)

    def get_template(self, template_key: str) -> EmailTemplateCatalogItem | None:
        key = str(template_key or "").strip().lower()
        if key == "":
            return None
        for item in _CANONICAL_EMAIL_TEMPLATES:
            if item.key == key:
                return item
        return None

    def list_effective_templates(self) -> list[EffectiveEmailTemplate]:
        overrides_by_key = {row["template_key"]: row for row in self._list_override_rows(scope_key=AGENCY_DEFAULT_SCOPE_KEY)}
        items: list[EffectiveEmailTemplate] = []
        for item in _CANONICAL_EMAIL_TEMPLATES:
            items.append(self._build_effective_template(item=item, override_row=overrides_by_key.get(item.key)))
        return items

    def get_effective_template(self, template_key: str) -> EffectiveEmailTemplate | None:
        item = self.get_template(template_key)
        if item is None:
            return None
        override = self._fetch_override_row(template_key=item.key, scope_key=AGENCY_DEFAULT_SCOPE_KEY)
        return self._build_effective_template(item=item, override_row=override)

    def render_effective_template(
        self,
        *,
        template_key: str,
        variables: dict[str, object] | None,
    ) -> RenderedEmailTemplate | None:
        effective = self.get_effective_template(template_key)
        if effective is None:
            return None

        normalized_variables = {
            str(key).strip().lower(): str(value)
            for key, value in dict(variables or {}).items()
        }

        subject = self._render_template_text(
            template=effective.subject,
            variables=normalized_variables,
            available_variables=effective.available_variables,
        )
        text_body = self._render_template_text(
            template=effective.text_body,
            variables=normalized_variables,
            available_variables=effective.available_variables,
        )
        html_body = self._render_template_text(
            template=effective.html_body,
            variables=normalized_variables,
            available_variables=effective.available_variables,
        )

        return RenderedEmailTemplate(
            key=effective.key,
            subject=subject,
            text_body=text_body,
            html_body=html_body,
            enabled=effective.enabled,
            available_variables=effective.available_variables,
        )

    def get_sample_variables(self, *, template_key: str) -> dict[str, str]:
        item = self.get_template(template_key)
        if item is None:
            return {}
        base = dict(_CANONICAL_SAMPLE_VARIABLES.get(item.key, {}))
        for variable in item.available_variables:
            if variable not in base:
                base[variable] = f"sample_{variable}"
        return base

    def render_template_preview(
        self,
        *,
        template_key: str,
        subject: str | None = None,
        text_body: str | None = None,
        html_body: str | None = None,
    ) -> EmailTemplatePreviewResult | None:
        effective = self.get_effective_template(template_key)
        if effective is None:
            return None

        sample_variables = self.get_sample_variables(template_key=effective.key)
        rendered_subject = self._render_template_text(
            template=effective.subject if subject is None else str(subject),
            variables=sample_variables,
            available_variables=effective.available_variables,
        )
        rendered_text_body = self._render_template_text(
            template=effective.text_body if text_body is None else str(text_body),
            variables=sample_variables,
            available_variables=effective.available_variables,
        )
        rendered_html_body = self._render_template_text(
            template=effective.html_body if html_body is None else str(html_body),
            variables=sample_variables,
            available_variables=effective.available_variables,
        )
        return EmailTemplatePreviewResult(
            key=effective.key,
            rendered_subject=rendered_subject,
            rendered_text_body=rendered_text_body,
            rendered_html_body=rendered_html_body,
            sample_variables=sample_variables,
            is_overridden=effective.is_overridden,
        )

    def send_template_test_email(
        self,
        *,
        template_key: str,
        to_email: str,
        subject: str | None = None,
        text_body: str | None = None,
        html_body: str | None = None,
    ) -> EmailTemplateTestSendResult | None:
        preview = self.render_template_preview(
            template_key=template_key,
            subject=subject,
            text_body=text_body,
            html_body=html_body,
        )
        if preview is None:
            return None

        from app.services.mailgun_service import mailgun_service

        send_result = mailgun_service.send_email(
            to_email=to_email,
            subject=preview.rendered_subject,
            text=preview.rendered_text_body,
            html=preview.rendered_html_body,
        )
        return EmailTemplateTestSendResult(
            key=preview.key,
            to_email=str(send_result.get("to_email") or to_email).strip().lower(),
            accepted=bool(send_result.get("accepted", send_result.get("ok", True))),
            delivery_status=str(send_result.get("delivery_status") or "accepted"),
            rendered_subject=preview.rendered_subject,
            provider_message=str(send_result.get("provider_message") or send_result.get("message") or "accepted"),
            provider_id=str(send_result.get("provider_id") or send_result.get("id") or ""),
        )

    def _render_template_text(
        self,
        *,
        template: str,
        variables: dict[str, str],
        available_variables: tuple[str, ...],
    ) -> str:
        rendered = str(template or "")
        for variable in available_variables:
            placeholder = f"{{{{{variable}}}}}"
            replacement = variables.get(variable, "")
            rendered = rendered.replace(placeholder, replacement)
        return rendered

    def save_override(
        self,
        *,
        template_key: str,
        subject: str,
        text_body: str,
        html_body: str | None,
        enabled: bool | None,
    ) -> EffectiveEmailTemplate | None:
        item = self.get_template(template_key)
        if item is None:
            return None

        normalized = self._normalize_override_input(
            subject=subject,
            text_body=text_body,
            html_body=html_body,
            enabled=enabled,
            template_key=item.key,
        )
        self._upsert_override_row(template_key=item.key, scope_key=AGENCY_DEFAULT_SCOPE_KEY, payload=normalized)
        override = self._fetch_override_row(template_key=item.key, scope_key=AGENCY_DEFAULT_SCOPE_KEY)
        return self._build_effective_template(item=item, override_row=override)

    def reset_override(self, *, template_key: str) -> EffectiveEmailTemplate | None:
        item = self.get_template(template_key)
        if item is None:
            return None
        self._delete_override_row(template_key=item.key, scope_key=AGENCY_DEFAULT_SCOPE_KEY)
        return self._build_effective_template(item=item, override_row=None)

    def _normalize_override_input(
        self,
        *,
        subject: str,
        text_body: str,
        html_body: str | None,
        enabled: bool | None,
        template_key: str,
    ) -> EmailTemplateOverrideInput:
        normalized_subject = str(subject if subject is not None else "").strip()
        if normalized_subject == "":
            raise ValueError("subject este obligatoriu")

        normalized_text_body = str(text_body if text_body is not None else "")
        if normalized_text_body.strip() == "":
            raise ValueError("text_body este obligatoriu")

        normalized_html_body = "" if html_body is None else str(html_body)
        current_override = self._fetch_override_row(template_key=template_key, scope_key=AGENCY_DEFAULT_SCOPE_KEY)
        effective_enabled = bool(current_override["enabled"]) if current_override is not None else True
        if enabled is not None:
            effective_enabled = bool(enabled)

        return EmailTemplateOverrideInput(
            subject=normalized_subject,
            text_body=normalized_text_body,
            html_body=normalized_html_body,
            enabled=effective_enabled,
        )

    def _build_effective_template(
        self,
        *,
        item: EmailTemplateCatalogItem,
        override_row: dict[str, object] | None,
    ) -> EffectiveEmailTemplate:
        if override_row is None:
            return EffectiveEmailTemplate(
                key=item.key,
                label=item.label,
                description=item.description,
                subject=item.default_subject,
                text_body=item.default_text_body,
                html_body=item.default_html_body,
                available_variables=item.available_variables,
                scope=item.scope,
                enabled=True,
                is_overridden=False,
                updated_at=None,
            )

        return EffectiveEmailTemplate(
            key=item.key,
            label=item.label,
            description=item.description,
            subject=str(override_row.get("subject_override") or item.default_subject),
            text_body=str(override_row.get("text_body_override") or item.default_text_body),
            html_body=str(override_row.get("html_body_override") or ""),
            available_variables=item.available_variables,
            scope=item.scope,
            enabled=bool(override_row.get("enabled", True)),
            is_overridden=True,
            updated_at=override_row.get("updated_at") if isinstance(override_row.get("updated_at"), datetime) else None,
        )

    def _list_override_rows(self, *, scope_key: str) -> list[dict[str, object]]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT template_key, scope_key, subject_override, text_body_override, html_body_override, enabled, updated_at
                    FROM agency_email_templates
                    WHERE scope_key = %s
                    """,
                    (scope_key,),
                )
                rows = cur.fetchall() or []
        return [
            {
                "template_key": str(row[0]),
                "scope_key": str(row[1]),
                "subject_override": str(row[2]),
                "text_body_override": str(row[3]),
                "html_body_override": str(row[4] or ""),
                "enabled": bool(row[5]),
                "updated_at": row[6],
            }
            for row in rows
        ]

    def _fetch_override_row(self, *, template_key: str, scope_key: str) -> dict[str, object] | None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT template_key, scope_key, subject_override, text_body_override, html_body_override, enabled, updated_at
                    FROM agency_email_templates
                    WHERE template_key = %s AND scope_key = %s
                    LIMIT 1
                    """,
                    (template_key, scope_key),
                )
                row = cur.fetchone()
        if row is None:
            return None
        return {
            "template_key": str(row[0]),
            "scope_key": str(row[1]),
            "subject_override": str(row[2]),
            "text_body_override": str(row[3]),
            "html_body_override": str(row[4] or ""),
            "enabled": bool(row[5]),
            "updated_at": row[6],
        }

    def _upsert_override_row(self, *, template_key: str, scope_key: str, payload: EmailTemplateOverrideInput) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO agency_email_templates (
                        template_key,
                        scope_key,
                        subject_override,
                        text_body_override,
                        html_body_override,
                        enabled,
                        updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (template_key, scope_key)
                    DO UPDATE SET
                        subject_override = EXCLUDED.subject_override,
                        text_body_override = EXCLUDED.text_body_override,
                        html_body_override = EXCLUDED.html_body_override,
                        enabled = EXCLUDED.enabled,
                        updated_at = NOW()
                    """,
                    (
                        template_key,
                        scope_key,
                        payload.subject,
                        payload.text_body,
                        payload.html_body,
                        payload.enabled,
                    ),
                )
            conn.commit()

    def _delete_override_row(self, *, template_key: str, scope_key: str) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM agency_email_templates WHERE template_key = %s AND scope_key = %s",
                    (template_key, scope_key),
                )
            conn.commit()


email_templates_service = EmailTemplatesService()
