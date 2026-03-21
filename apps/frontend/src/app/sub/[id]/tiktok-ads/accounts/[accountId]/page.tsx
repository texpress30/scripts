"use client";

import { useParams } from "next/navigation";
import React from "react";

import { SubAdsCampaignDrilldownPage } from "@/app/sub/[id]/_components/SubAdsCampaignDrilldownPage";
import { getSubTikTokAdsCampaignsTable } from "@/lib/api";

export default function SubTikTokAdsAccountCampaignsPage() {
  const params = useParams<{ id: string; accountId: string }>();
  const clientId = Number(params.id);
  const accountId = decodeURIComponent(String(params.accountId || ""));

  return (
    <SubAdsCampaignDrilldownPage
      clientId={clientId}
      accountId={accountId}
      platformTitle="TikTok Ads"
      backRoute={`/sub/${clientId}/tiktok-ads`}
      storageKey="sub-tiktok-ads-campaigns-visible-columns-v1"
      fetchCampaigns={getSubTikTokAdsCampaignsTable}
      campaignHref={(campaignId) => `/sub/${clientId}/tiktok-ads/accounts/${encodeURIComponent(accountId)}/campaigns/${encodeURIComponent(campaignId)}`}
    />
  );
}
