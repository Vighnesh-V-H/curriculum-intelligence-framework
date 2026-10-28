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
    <main className="flex min-h-screen items-center justify-center bg-slate-950 text-slate-300">
      <p className="text-sm tracking-wide">Loading curriculum workspace…</p>
    </main>
  );
}
