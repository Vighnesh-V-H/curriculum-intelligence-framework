"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { ApiError, User, api, clearStoredToken } from "@/lib/api";

const MODULES = [
  {
    title: "Documents",
    description: "Upload curriculum files and review AI analysis.",
    href: "/documents",
    available: true,
  },
  {
    title: "Curriculum versions",
    description: "Create and revise programs, semesters, and courses.",
    available: false,
  },
  {
    title: "Outcome mapping",
    description: "Manage program outcomes and CO-PO mappings.",
    available: false,
  },
];

function formatDate(value: string | null): string {
  if (!value) {
    return "Not yet";
  }
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
      try {
        const currentUser = await api.me();
        if (!cancelled) {
          setUser(currentUser);
        }
      } catch (caught) {
        if (caught instanceof ApiError && caught.status === 401) {
          clearStoredToken();
          router.replace("/login");
          return;
        }
        if (!cancelled) {
          setError(
            caught instanceof ApiError
              ? caught.message
              : "Unable to load your profile.",
          );
        }
      }
    }

    loadCurrentUser();
    return () => {
      cancelled = true;
    };
  }, [router]);

  function handleSignOut() {
    clearStoredToken();
    router.replace("/login");
  }

  if (error) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-50 px-6">
        <div className="max-w-md rounded-xl border border-red-200 bg-white p-6 shadow-sm">
          <h1 className="text-lg font-semibold text-slate-900">
            Unable to load dashboard
          </h1>
          <p className="mt-2 text-sm text-red-600">{error}</p>
          <button
            onClick={handleSignOut}
            className="mt-4 rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white"
          >
            Return to sign in
          </button>
        </div>
      </main>
    );
  }

  if (!user) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-50 text-sm text-slate-500">
        Loading your workspace…
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-slate-50 px-6 py-10">
      <div className="mx-auto max-w-5xl">
        <header className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-indigo-600">
              Curriculum Intelligence
            </p>
            <h1 className="mt-2 text-3xl font-semibold text-slate-900">
              {user.full_name}
            </h1>
            <p className="mt-1 text-sm text-slate-500">
              {user.email} · @{user.username}
            </p>
          </div>
          <button
            onClick={handleSignOut}
            className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-400"
          >
            Sign out
          </button>
        </header>

        <section className="mt-8 grid gap-4 md:grid-cols-3">
          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Account status
            </p>
            <p className="mt-2 text-lg font-semibold text-emerald-600">
              {user.status}
            </p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Assigned roles
            </p>
            <div className="mt-2 flex flex-wrap gap-2">
              {user.roles.map((role) => (
                <span
                  key={role}
                  className="rounded-full bg-indigo-50 px-3 py-1 text-xs font-semibold text-indigo-700"
                >
                  {role.replaceAll("_", " ")}
                </span>
              ))}
            </div>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Last sign in
            </p>
            <p className="mt-2 text-sm font-medium text-slate-800">
              {formatDate(user.last_login_at)}
            </p>
          </div>
        </section>

        <section className="mt-10">
          <h2 className="text-lg font-semibold text-slate-900">
            Workspace modules
          </h2>
          <div className="mt-4 grid gap-4 md:grid-cols-3">
            {MODULES.map((module) => {
              const body = (
                <>
                  <h3 className="text-sm font-semibold text-slate-800">
                    {module.title}
                  </h3>
                  <p className="mt-2 text-sm text-slate-500">
                    {module.description}
                  </p>
                  <p
                    className={
                      module.available
                        ? "mt-4 text-xs font-semibold uppercase tracking-wide text-indigo-600"
                        : "mt-4 text-xs font-semibold uppercase tracking-wide text-slate-400"
                    }
                  >
                    {module.available ? "Open module" : "Coming next"}
                  </p>
                </>
              );
              return module.available && module.href ? (
                <Link
                  key={module.title}
                  href={module.href}
                  className="rounded-xl border border-indigo-200 bg-white p-5 shadow-sm transition hover:border-indigo-400"
                >
                  {body}
                </Link>
              ) : (
                <article
                  key={module.title}
                  className="rounded-xl border border-dashed border-slate-300 bg-white/70 p-5"
                >
                  {body}
                </article>
              );
            })}
          </div>
        </section>
      </div>
    </main>
  );
}
