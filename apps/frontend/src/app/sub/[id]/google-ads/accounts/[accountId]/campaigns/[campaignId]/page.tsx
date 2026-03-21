"use client";

import { useParams } from "next/navigation";
import React from "react";

import { SubAdsAdGroupDrilldownPage } from "@/app/sub/[id]/_components/SubAdsAdGroupDrilldownPage";
import { getSubGoogleAdsCampaignAdGroupsTable } from "@/lib/api";

export default function SubGoogleAdsCampaignAdGroupsPage() {
  const params = useParams<{ id: string; accountId: string; campaignId: string }>();
  const clientId = Number(params.id);
  const accountId = decodeURIComponent(String(params.accountId || ""));
  const campaignId = decodeURIComponent(String(params.campaignId || ""));

  return (
    <SubAdsAdGroupDrilldownPage
      clientId={clientId}
      accountId={accountId}
      campaignId={campaignId}
      platformTitle="Google Ads"
      itemLabelPlural="Ad groups"
      backRoute={`/sub/${clientId}/google-ads/accounts/${encodeURIComponent(accountId)}`}
      storageKey="sub-google-ads-campaign-adgroups-visible-columns-v1"
      fetchAdGroups={getSubGoogleAdsCampaignAdGroupsTable}
    />
  );
}
