"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, CalendarClock, FileStack, Sparkles } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { ApiError, api, clearStoredToken, getStoredToken } from "@/lib/api";
import type { User } from "@/lib/api";

function formatDate(value: string | null): string {
  if (!value) return "Not yet";
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export default function DashboardPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadCurrentUser() {
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
          return;
        }
        if (!cancelled) {
          setError(caught instanceof ApiError ? caught.message : "Unable to load your profile.");
        }
      }
    }

    loadCurrentUser();
    return () => {
      cancelled = true;
    };
  }, [router]);

  if (error) {
    return (
      <div className="workspace-page-error">
        <p className="workspace-page-error__eyebrow">CURRICULUM WORKSPACE</p>
        <h1>Unable to load your dashboard.</h1>
        <p>{error}</p>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="workspace-page-loading" role="status" aria-live="polite">
        Loading your workspace…
      </div>
    );
  }

  const canDraft = user.roles.some((role) => ["ADMIN", "COMMITTEE_MEMBER", "FACULTY"].includes(role));

  return (
    <div className="dashboard-page">
      <header className="dashboard-heading">
        <div>
          <p className="dashboard-eyebrow">CURRICULUM INTELLIGENCE</p>
          <h1>Your curriculum workspace</h1>
          <p>Welcome, {user.full_name}. Start a draft or continue with your source material.</p>
        </div>
        <Badge variant="outline" className="dashboard-status">
          <span className="dashboard-status__dot" aria-hidden="true" />
          {user.status.replaceAll("_", " ").toLowerCase()}
        </Badge>
      </header>

      <section className="dashboard-draft-entry" aria-labelledby="dashboard-draft-title">
        <div className="dashboard-draft-entry__main">
          <div className="dashboard-draft-entry__eyebrow">
            <Sparkles aria-hidden="true" />
            Curriculum design
          </div>
          <h2 id="dashboard-draft-title">Turn source material into a curriculum draft.</h2>
          <p>
            Bring your program documents together, then generate and review a semester roadmap,
            course outcomes, and proposed mappings. Each draft is saved to the curriculum workspace
            automatically.
          </p>
          {canDraft ? (
            <Link className="dashboard-draft-entry__action" href="/curriculum-drafts/new">
              Open draft studio
              <ArrowRight aria-hidden="true" />
            </Link>
          ) : (
            <p className="dashboard-draft-entry__access-note">Your role does not include curriculum draft generation.</p>
          )}
          <span className="dashboard-draft-entry__note">AI-generated draft · saved in DRAFT status</span>
        </div>
        <ol className="dashboard-workflow" aria-label="Draft workflow">
          <li>
            <span>01</span>
            <div><strong>Source documents</strong><small>Upload your reference material</small></div>
          </li>
          <li>
            <span>02</span>
            <div><strong>Semester roadmap</strong><small>Review courses and learning focus</small></div>
          </li>
          <li>
            <span>03</span>
            <div><strong>Outcome mapping</strong><small>Inspect proposed coverage</small></div>
          </li>
        </ol>
      </section>

      <section className="dashboard-support-grid" aria-label="Workspace resources">
        <Link className="dashboard-resource" href="/documents">
          <span className="dashboard-resource__icon"><FileStack aria-hidden="true" /></span>
          <span className="dashboard-resource__body">
            <span className="dashboard-resource__eyebrow">SOURCE LIBRARY</span>
            <strong>Documents</strong>
            <span>Upload and review files used in curriculum work.</span>
          </span>
          <ArrowRight className="dashboard-resource__arrow" aria-hidden="true" />
        </Link>

        <section className="dashboard-account" aria-labelledby="dashboard-account-title">
          <div className="dashboard-account__heading">
            <span className="dashboard-account__icon"><CalendarClock aria-hidden="true" /></span>
            <div>
              <p>ACCOUNT</p>
              <h2 id="dashboard-account-title">Your workspace access</h2>
            </div>
          </div>
          <dl>
            <div>
              <dt>Roles</dt>
              <dd>{user.roles.map((role) => role.replaceAll("_", " ").toLowerCase()).join(" · ")}</dd>
            </div>
            <div>
              <dt>Last sign in</dt>
              <dd>{formatDate(user.last_login_at)}</dd>
            </div>
          </dl>
        </section>
      </section>
    </div>
  );
}
