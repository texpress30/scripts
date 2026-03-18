from __future__ import annotations

from dataclasses import dataclass


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
            "Acest link expiră în {{token_ttl_minutes}} minute."
        ),
        default_html_body=(
            "<p>Ai solicitat resetarea parolei.</p>"
            "<p>Folosește link-ul de mai jos pentru a seta o parolă nouă:</p>"
            "<p><a href=\"{{reset_link}}\">Resetează parola</a></p>"
            "<p>Acest link expiră în {{token_ttl_minutes}} minute.</p>"
        ),
        available_variables=("reset_link", "token_ttl_minutes", "user_email"),
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
            "Invitația expiră în {{token_ttl_minutes}} minute."
        ),
        default_html_body=(
            "<p>Ai fost invitat în platformă.</p>"
            "<p>Folosește link-ul de activare:</p>"
            "<p><a href=\"{{invite_link}}\">Activează contul</a></p>"
            "<p>Invitația expiră în {{token_ttl_minutes}} minute.</p>"
        ),
        available_variables=("invite_link", "token_ttl_minutes", "invited_email", "inviter_name"),
    ),
)


class EmailTemplatesService:
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


email_templates_service = EmailTemplatesService()
