from __future__ import annotations

from app.core.config import load_settings

try:
    import psycopg
except Exception:  # noqa: BLE001
    psycopg = None


class CompanySettingsService:
    def _connect(self):
        settings = load_settings()
        if psycopg is None:
            raise RuntimeError("psycopg is required for company settings persistence")
        return psycopg.connect(settings.database_url)

    def initialize_schema(self) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS companies (
                        id BIGSERIAL PRIMARY KEY,
                        owner_email TEXT UNIQUE NOT NULL,
                        company_name TEXT NOT NULL DEFAULT '',
                        company_email TEXT NOT NULL DEFAULT '',
                        company_phone_prefix TEXT NOT NULL DEFAULT '+40',
                        company_phone TEXT NOT NULL DEFAULT '',
                        company_website TEXT NOT NULL DEFAULT '',
                        business_category TEXT NOT NULL DEFAULT '',
                        business_niche TEXT NOT NULL DEFAULT '',
                        platform_primary_use TEXT NOT NULL DEFAULT '',
                        address_line1 TEXT NOT NULL DEFAULT '',
                        city TEXT NOT NULL DEFAULT '',
                        postal_code TEXT NOT NULL DEFAULT '',
                        region TEXT NOT NULL DEFAULT '',
                        country TEXT NOT NULL DEFAULT 'România',
                        timezone TEXT NOT NULL DEFAULT 'Europe/Bucharest',
                        logo_url TEXT NOT NULL DEFAULT '',
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
            conn.commit()

    def _ensure_company(self, *, owner_email: str) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO companies (
                        owner_email, company_name, company_email, company_phone_prefix, country, timezone
                    ) VALUES (%s, %s, %s, '+40', 'România', 'Europe/Bucharest')
                    ON CONFLICT(owner_email) DO NOTHING
                    """,
                    (owner_email, "", owner_email),
                )
            conn.commit()

    def get_settings(self, *, owner_email: str) -> dict[str, str]:
        self._ensure_company(owner_email=owner_email)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT company_name, company_email, company_phone_prefix, company_phone, company_website,
                           business_category, business_niche, platform_primary_use,
                           address_line1, city, postal_code, region, country, timezone, logo_url
                    FROM companies
                    WHERE owner_email = %s
                    """,
                    (owner_email,),
                )
                row = cur.fetchone()

        if row is None:
            raise RuntimeError("Company settings not found")

        return {
            "company_name": str(row[0]),
            "company_email": str(row[1]),
            "company_phone_prefix": str(row[2]),
            "company_phone": str(row[3]),
            "company_website": str(row[4]),
            "business_category": str(row[5]),
            "business_niche": str(row[6]),
            "platform_primary_use": str(row[7]),
            "address_line1": str(row[8]),
            "city": str(row[9]),
            "postal_code": str(row[10]),
            "region": str(row[11]),
            "country": str(row[12]),
            "timezone": str(row[13]),
            "logo_url": str(row[14]),
        }

    def update_settings(self, *, owner_email: str, payload: dict[str, str]) -> dict[str, str]:
        self._ensure_company(owner_email=owner_email)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE companies
                    SET company_name = %s,
                        company_email = %s,
                        company_phone_prefix = %s,
                        company_phone = %s,
                        company_website = %s,
                        business_category = %s,
                        business_niche = %s,
                        platform_primary_use = %s,
                        address_line1 = %s,
                        city = %s,
                        postal_code = %s,
                        region = %s,
                        country = %s,
                        timezone = %s,
                        logo_url = %s,
                        updated_at = NOW()
                    WHERE owner_email = %s
                    """,
                    (
                        payload["company_name"],
                        payload["company_email"],
                        payload["company_phone_prefix"],
                        payload["company_phone"],
                        payload["company_website"],
                        payload["business_category"],
                        payload["business_niche"],
                        payload["platform_primary_use"],
                        payload["address_line1"],
                        payload["city"],
                        payload["postal_code"],
                        payload["region"],
                        payload["country"],
                        payload["timezone"],
                        payload["logo_url"],
                        owner_email,
                    ),
                )
            conn.commit()

        return self.get_settings(owner_email=owner_email)


company_settings_service = CompanySettingsService()
