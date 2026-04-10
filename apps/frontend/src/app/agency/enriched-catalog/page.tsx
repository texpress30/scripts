"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function EnrichedCatalogPage() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/agency/enriched-catalog/templates");
  }, [router]);
  return null;
}
