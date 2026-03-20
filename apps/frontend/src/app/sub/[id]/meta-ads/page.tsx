"use client";

import { useParams } from "next/navigation";
import React from "react";

import { SubAdsPerformanceTablePage } from "../_components/SubAdsPerformanceTablePage";
import { getSubMetaAdsTable } from "@/lib/api";

export default function SubMetaAdsPage() {
  const params = useParams<{ id: string }>();
  const clientId = Number(params.id);

  return (
    <SubAdsPerformanceTablePage
      clientId={clientId}
      platformTitle="Meta Ads"
      platformDescription="Performance multi-account • Meta Ads"
      storageKey="sub-meta-ads-visible-columns-v1"
      fetchTable={getSubMetaAdsTable}
    />
  );
}
