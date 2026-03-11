"use client";

import { useParams } from "next/navigation";
import React from "react";

import { SubSectionPlaceholderPage } from "../_components/SubSectionPlaceholderPage";

export default function SubMetaAdsPage() {
  const params = useParams<{ id: string }>();
  const clientId = Number(params.id);

  return <SubSectionPlaceholderPage clientId={clientId} sectionTitle="Meta Ads" />;
}
