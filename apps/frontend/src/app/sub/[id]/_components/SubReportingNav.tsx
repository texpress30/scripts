"use client";

import Link from "next/link";
import React from "react";

export function SubReportingNav({ clientId }: { clientId: number }) {
  return (
    <div className="mb-4 flex items-center gap-4 text-sm">
      <Link href={`/sub/${clientId}/media-buying`} className="text-indigo-600 transition-colors hover:text-indigo-700 hover:underline">Media Buying</Link>
      <Link href={`/sub/${clientId}/media-tracker`} className="text-indigo-600 transition-colors hover:text-indigo-700 hover:underline">Media Tracker</Link>
      <Link href={`/sub/${clientId}/data`} className="text-indigo-600 transition-colors hover:text-indigo-700 hover:underline">Data</Link>
    </div>
  );
}
