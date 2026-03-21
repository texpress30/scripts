"use client";

import { useParams } from "next/navigation";
import React from "react";

import { SubAdsCampaignDrilldownPage } from "@/app/sub/[id]/_components/SubAdsCampaignDrilldownPage";
import { getSubMetaAdsCampaignsTable } from "@/lib/api";

export default function SubMetaAdsAccountCampaignsPage() {
  const params = useParams<{ id: string; accountId: string }>();
  const clientId = Number(params.id);
  const accountId = decodeURIComponent(String(params.accountId || ""));

  return (
    <SubAdsCampaignDrilldownPage
      clientId={clientId}
      accountId={accountId}
      platformTitle="Meta Ads"
      backRoute={`/sub/${clientId}/meta-ads`}
      storageKey="sub-meta-ads-campaigns-visible-columns-v1"
      fetchCampaigns={getSubMetaAdsCampaignsTable}
    />
  );
}
