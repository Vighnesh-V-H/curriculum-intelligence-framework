"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { getStoredToken } from "@/lib/api";

export default function Home() {
  const router = useRouter();

  useEffect(() => {
    router.replace(getStoredToken() ? "/dashboard" : "/login");
  }, [router]);

  return (
    <main className="home-redirect">
      <span className="workspace-brand-mark" aria-hidden="true">C</span>
      <p>Opening your curriculum workspace</p>
    </main>
  );
}
