"use client";

import { useParams } from "next/navigation";
import React from "react";

import { SubAdsAdGroupDrilldownPage } from "@/app/sub/[id]/_components/SubAdsAdGroupDrilldownPage";
import { getSubMetaAdsCampaignAdGroupsTable } from "@/lib/api";

export default function SubMetaAdsCampaignAdSetsPage() {
  const params = useParams<{ id: string; accountId: string; campaignId: string }>();
  const clientId = Number(params.id);
  const accountId = decodeURIComponent(String(params.accountId || ""));
  const campaignId = decodeURIComponent(String(params.campaignId || ""));

  return (
    <SubAdsAdGroupDrilldownPage
      clientId={clientId}
      accountId={accountId}
      campaignId={campaignId}
      platformTitle="Meta Ads"
      itemLabelPlural="Ad sets"
      backRoute={`/sub/${clientId}/meta-ads/accounts/${encodeURIComponent(accountId)}`}
      storageKey="sub-meta-ads-campaign-adsets-visible-columns-v1"
      fetchAdGroups={getSubMetaAdsCampaignAdGroupsTable}
    />
  );
}
