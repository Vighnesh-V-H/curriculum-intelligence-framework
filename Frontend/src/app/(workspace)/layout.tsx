"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { WorkspaceNav } from "@/components/workspace-nav";
import { ApiError, User, api, clearStoredToken, getStoredToken } from "@/lib/api";

const WRITER_ROLES = new Set(["ADMIN", "COMMITTEE_MEMBER", "FACULTY"]);

export default function WorkspaceLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<User | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function loadUser() {
      if (!getStoredToken()) {
        router.replace("/login");
        return;
      }
      try {
        const currentUser = await api.me();
        if (!cancelled) setUser(currentUser);
      } catch (caught) {
        if (caught instanceof ApiError && caught.status === 401) {
          clearStoredToken();
          router.replace("/login");
        } else if (!cancelled) {
          setError(caught instanceof ApiError ? caught.message : "Unable to load your profile.");
        }
      }
    }
    loadUser();
    return () => { cancelled = true; };
  }, [router]);

  function handleSignOut() {
    clearStoredToken();
    router.replace("/login");
  }

  if (error) {
    return (
      <div className="workspace-gate-shell">
        <div className="workspace-gate-shell__content" aria-hidden="true">{children}</div>
        <main className="workspace-gate">
          <p className="workspace-gate__eyebrow">CURRICULUM WORKSPACE</p>
          <h1>We couldn’t load your workspace.</h1>
          <p>{error}</p>
          <div>
            <button type="button" onClick={() => window.location.reload()}>Try again</button>
            <button type="button" onClick={() => router.replace("/login")}>Return to sign in</button>
          </div>
        </main>
      </div>
    );
  }
  if (!user) {
    return (
      <div className="workspace-gate-shell">
        <div className="workspace-gate-shell__content" aria-hidden="true">{children}</div>
        <main className="workspace-gate" role="status" aria-live="polite">
          <span className="workspace-gate__loader" aria-hidden="true" />
          <p>Loading your workspace…</p>
        </main>
      </div>
    );
  }

  const canWrite = user.roles.some((role) => WRITER_ROLES.has(role));
  return (
    <WorkspaceNav
      active={
        pathname.startsWith("/curriculum-drafts")
          ? "drafts"
          : pathname.startsWith("/documents")
            ? "documents"
            : pathname.startsWith("/verification")
              ? "verification"
              : pathname.startsWith("/curricula")
                ? "curricula"
                : pathname.startsWith("/users")
                  ? "users"
                  : "dashboard"
      }
      user={user}
      onSignOut={handleSignOut}
      onGenerate={canWrite ? () => router.push("/curriculum-drafts/new") : undefined}
    >
      {children}
    </WorkspaceNav>
  );
}
