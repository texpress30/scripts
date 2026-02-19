"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

export function ProtectedPage({ children }: { children: React.ReactNode }) {
  const router = useRouter();

  useEffect(() => {
    const token = localStorage.getItem("mcc_token");
    if (!token) router.replace("/login");
  }, [router]);

  return <>{children}</>;
}
