"use client";

import { useParams } from "next/navigation";
import React from "react";

import { SubAdsPerformanceTablePage } from "../_components/SubAdsPerformanceTablePage";
import { getSubTikTokAdsTable } from "@/lib/api";

export default function SubTikTokAdsPage() {
  const params = useParams<{ id: string }>();
  const clientId = Number(params.id);

  return (
    <SubAdsPerformanceTablePage
      clientId={clientId}
      platformTitle="TikTok Ads"
      platformDescription="Performance multi-account • TikTok Ads"
      storageKey="sub-tiktok-ads-visible-columns-v1"
      fetchTable={getSubTikTokAdsTable}
    />
  );
}
