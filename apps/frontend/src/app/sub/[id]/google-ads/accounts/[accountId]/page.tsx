"use client";

import { useParams } from "next/navigation";
import React from "react";

import { SubAdsCampaignDrilldownPage } from "@/app/sub/[id]/_components/SubAdsCampaignDrilldownPage";
import { getSubGoogleAdsCampaignsTable } from "@/lib/api";

export default function SubGoogleAdsAccountCampaignsPage() {
  const params = useParams<{ id: string; accountId: string }>();
  const clientId = Number(params.id);
  const accountId = decodeURIComponent(String(params.accountId || ""));

  return (
    <SubAdsCampaignDrilldownPage
      clientId={clientId}
      accountId={accountId}
      platformTitle="Google Ads"
      backRoute={`/sub/${clientId}/google-ads`}
      storageKey="sub-google-ads-campaigns-visible-columns-v1"
      fetchCampaigns={getSubGoogleAdsCampaignsTable}
      campaignHref={(campaignId) => `/sub/${clientId}/google-ads/accounts/${encodeURIComponent(accountId)}/campaigns/${encodeURIComponent(campaignId)}`}
    />
  );
}
