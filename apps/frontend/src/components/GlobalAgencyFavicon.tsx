"use client";

import React from "react";
import { useEffect, useState } from "react";

import { apiRequest } from "@/lib/api";
import { GlobalFavicon } from "@/components/GlobalFavicon";

type CompanySettingsLogoResponse = {
  logo_url?: string | null;
};

export function GlobalAgencyFavicon() {
  const [agencyLogoUrl, setAgencyLogoUrl] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    let ignore = false;

    async function loadCompanyLogo() {
      try {
        const payload = await apiRequest<CompanySettingsLogoResponse>("/company/settings", { requireAuth: true });
        if (!ignore) {
          setAgencyLogoUrl(String(payload?.logo_url ?? "").trim());
          setRefreshKey((prev) => prev + 1);
        }
      } catch {
        if (!ignore) {
          setAgencyLogoUrl("");
          setRefreshKey((prev) => prev + 1);
        }
      }
    }

    function onCompanySettingsUpdated() {
      void loadCompanyLogo();
    }

    void loadCompanyLogo();
    window.addEventListener("company-settings-updated", onCompanySettingsUpdated);
    return () => {
      ignore = true;
      window.removeEventListener("company-settings-updated", onCompanySettingsUpdated);
    };
  }, []);

  return <GlobalFavicon agencyLogoUrl={agencyLogoUrl} refreshKey={refreshKey} />;
}
