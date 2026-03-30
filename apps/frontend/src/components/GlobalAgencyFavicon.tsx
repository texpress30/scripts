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
    let retryTimeout: ReturnType<typeof setTimeout> | null = null;

    async function loadCompanyLogo(attempt = 0) {
      try {
        const payload = await apiRequest<CompanySettingsLogoResponse>("/company/settings");
        if (!ignore) {
          setAgencyLogoUrl(String(payload?.logo_url ?? "").trim());
          setRefreshKey((prev) => prev + 1);
        }
      } catch {
        if (!ignore && attempt < 3) {
          retryTimeout = setTimeout(() => void loadCompanyLogo(attempt + 1), 2000 * (attempt + 1));
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
      if (retryTimeout) clearTimeout(retryTimeout);
      window.removeEventListener("company-settings-updated", onCompanySettingsUpdated);
    };
  }, []);

  return <GlobalFavicon agencyLogoUrl={agencyLogoUrl} refreshKey={refreshKey} />;
}
