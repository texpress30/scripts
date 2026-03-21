"use client";

import { useParams } from "next/navigation";
import React from "react";

import { SubAdsAdGroupDrilldownPage } from "@/app/sub/[id]/_components/SubAdsAdGroupDrilldownPage";
import { getSubTikTokAdsCampaignAdGroupsTable } from "@/lib/api";

export default function SubTikTokAdsCampaignAdGroupsPage() {
  const params = useParams<{ id: string; accountId: string; campaignId: string }>();
  const clientId = Number(params.id);
  const accountId = decodeURIComponent(String(params.accountId || ""));
  const campaignId = decodeURIComponent(String(params.campaignId || ""));

  return (
    <SubAdsAdGroupDrilldownPage
      clientId={clientId}
      accountId={accountId}
      campaignId={campaignId}
      platformTitle="TikTok Ads"
      itemLabelPlural="Ad groups"
      backRoute={`/sub/${clientId}/tiktok-ads/accounts/${encodeURIComponent(accountId)}`}
      storageKey="sub-tiktok-ads-campaign-adgroups-visible-columns-v1"
      fetchAdGroups={getSubTikTokAdsCampaignAdGroupsTable}
    />
  );
}
