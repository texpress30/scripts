"use client";

import { useParams } from "next/navigation";
import React from "react";

import { SubAdsPerformanceTablePage } from "../_components/SubAdsPerformanceTablePage";
import { getSubGoogleAdsTable } from "@/lib/api";

export default function SubGoogleAdsPage() {
  const params = useParams<{ id: string }>();
  const clientId = Number(params.id);

  return (
    <SubAdsPerformanceTablePage
      clientId={clientId}
      platformTitle="Google Ads"
      platformDescription="Performance multi-account • Google Ads"
      storageKey="sub-google-ads-visible-columns-v1"
      accountRouteBase="google-ads"
      fetchTable={getSubGoogleAdsTable}
    />
  );
}
