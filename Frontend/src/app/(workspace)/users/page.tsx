"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { RotateCw, ShieldCheck } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  ApiError,
  api,
  clearStoredToken,
  getStoredToken,
} from "@/lib/api";
import type { RoleCode, User, UserStatus } from "@/lib/api";

const ROLE_OPTIONS: { code: RoleCode; label: string; description: string }[] = [
  {
    code: "ADMIN",
    label: "Administrator",
    description: "Full access, including user administration.",
  },
  {
    code: "COMMITTEE_MEMBER",
    label: "Committee member",
    description: "Reviews curricula and verification findings.",
  },
  {
    code: "FACULTY",
    label: "Faculty",
    description: "Creates and edits curriculum content.",
  },
  {
    code: "REVIEWER",
    label: "Reviewer",
    description: "Read-only access to curricula and reports.",
  },
];

const STATUS_OPTIONS: { value: UserStatus; label: string }[] = [
  { value: "ACTIVE", label: "Active" },
  { value: "INACTIVE", label: "Inactive" },
  { value: "LOCKED", label: "Locked" },
];

const STATUS_STYLES: Record<UserStatus, string> = {
  ACTIVE: "border-success/35 bg-success/10 text-success",
  INACTIVE: "border-border bg-muted text-muted-foreground",
  LOCKED: "border-destructive/35 bg-destructive/10 text-destructive",
};

function errorMessage(error: unknown): string {
  return error instanceof ApiError
    ? error.message
    : "The request could not be completed.";
}

function formatDate(value: string | null): string {
  if (!value) return "Never";
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part.charAt(0).toUpperCase())
    .join("");
}

function sortedUsers(rows: User[]): User[] {
  return [...rows].sort((left, right) =>
    left.full_name.localeCompare(right.full_name, undefined, {
      sensitivity: "base",
    }),
  );
}

export default function UsersPage() {
  const router = useRouter();
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [users, setUsers] = useState<User[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [savingUserId, setSavingUserId] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const isAdmin = currentUser?.roles.includes("ADMIN") ?? false;

  const refreshUsers = useCallback(async () => {
    setRefreshing(true);
    setError(null);
    try {
      const rows = await api.listUsers();
      setUsers(sortedUsers(rows));
      setLoadError(null);
    } catch (caught) {
      setLoadError(errorMessage(caught));
    } finally {
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function loadWorkspace() {
      if (!getStoredToken()) {
        router.replace("/login");
        return;
      }
      try {
        const me = await api.me();
        if (cancelled) return;
        setCurrentUser(me);
        if (!me.roles.includes("ADMIN")) {
          setUsers([]);
          return;
        }
        const rows = await api.listUsers();
        if (!cancelled) setUsers(sortedUsers(rows));
      } catch (caught) {
        if (caught instanceof ApiError && caught.status === 401) {
          clearStoredToken();
          router.replace("/login");
          return;
        }
        if (!cancelled) setLoadError(errorMessage(caught));
      }
    }

    void loadWorkspace();
    return () => {
      cancelled = true;
    };
  }, [router]);

  function replaceUser(next: User) {
    setUsers((current) =>
      current
        ? sortedUsers(current.map((item) => (item.id === next.id ? next : item)))
        : [next],
    );
  }

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const roles = data.getAll("roles").map(String) as RoleCode[];
    setError(null);
    setNotice(null);
    if (!roles.length) {
      setError("Select at least one role for the new account.");
      return;
    }
    setCreating(true);
    try {
      const created = await api.createUser({
        username: String(data.get("username")),
        email: String(data.get("email")),
        password: String(data.get("password")),
        full_name: String(data.get("full_name")),
        roles,
      });
      setUsers((current) =>
        sortedUsers(current ? [...current, created] : [created]),
      );
      setNotice(`Account created for ${created.full_name}.`);
      form.reset();
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setCreating(false);
    }
  }

  async function handleRoles(event: FormEvent<HTMLFormElement>, target: User) {
    event.preventDefault();
    const roles = new FormData(event.currentTarget)
      .getAll("roles")
      .map(String) as RoleCode[];
    setError(null);
    setNotice(null);
    if (!roles.length) {
      setError("A user must keep at least one role.");
      return;
    }
    setSavingUserId(target.id);
    try {
      const updated = await api.assignUserRoles(target.id, roles);
      replaceUser(updated);
      setNotice(`Roles updated for ${updated.full_name}.`);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setSavingUserId(null);
    }
  }

  async function handleStatus(target: User, status: UserStatus) {
    if (status === target.status) return;
    setError(null);
    setNotice(null);
    setSavingUserId(target.id);
    try {
      const updated = await api.updateUserStatus(target.id, status);
      replaceUser(updated);
      setNotice(`${updated.full_name} is now ${status.toLowerCase()}.`);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setSavingUserId(null);
    }
  }

  function handleSignOut() {
    clearStoredToken();
    router.replace("/login");
  }

  if (loadError && !users) {
    return (
      <main className="mx-auto flex min-h-[60vh] max-w-2xl items-center justify-center">
        <div className="w-full rounded-xl border border-destructive/30 bg-card p-6">
          <h1 className="text-lg font-semibold text-foreground">
            User administration is unavailable
          </h1>
          <p className="mt-2 text-sm text-muted-foreground">{loadError}</p>
          <div className="mt-5 flex flex-wrap gap-2">
            <Button type="button" onClick={() => void refreshUsers()}>
              Try again
            </Button>
            <Button type="button" variant="outline" onClick={handleSignOut}>
              Return to sign in
            </Button>
          </div>
        </div>
      </main>
    );
  }

  if (!currentUser || !users) {
    return (
      <main
        className="mx-auto flex min-h-[60vh] max-w-2xl items-center justify-center"
        role="status"
        aria-live="polite"
      >
        <p className="text-sm text-muted-foreground">Loading user accounts…</p>
      </main>
    );
  }

  if (!isAdmin) {
    return (
      <main className="mx-auto flex min-h-[60vh] max-w-2xl items-center justify-center">
        <div className="w-full rounded-xl border border-border bg-card p-6">
          <ShieldCheck
            aria-hidden="true"
            className="h-5 w-5 text-muted-foreground"
          />
          <h1 className="mt-3 text-lg font-semibold text-foreground">
            Administrators only
          </h1>
          <p className="mt-2 text-sm text-muted-foreground">
            User accounts and role assignments are restricted to
            administrators.
          </p>
          <Link
            href="/dashboard"
            className="mt-5 inline-flex min-h-9 items-center rounded-lg bg-primary px-4 text-sm font-semibold text-primary-foreground"
          >
            Return to overview
          </Link>
        </div>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-6xl">
      <header className="page-heading flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold text-foreground">Users</h1>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
            Create accounts, assign roles, and manage access. Changes take
            effect immediately.
          </p>
        </div>
        <Button
          type="button"
          variant="outline"
          onClick={() => void refreshUsers()}
          disabled={refreshing}
        >
          <RotateCw
            aria-hidden="true"
            className={refreshing ? "animate-spin" : undefined}
          />
          {refreshing ? "Refreshing…" : "Refresh"}
        </Button>
      </header>

      {error ? (
        <p
          role="alert"
          className="mt-6 rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive"
        >
          {error}
        </p>
      ) : null}
      {notice ? (
        <p
          role="status"
          className="mt-6 rounded-lg border border-success/30 bg-success/10 px-3 py-2 text-sm text-success"
        >
          {notice}
        </p>
      ) : null}

      <div className="mt-8 grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
        <section
          aria-labelledby="user-list-heading"
          className="overflow-hidden rounded-xl border border-border bg-card"
        >
          <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-border px-5 py-4">
            <h2 id="user-list-heading" className="text-base font-semibold">
              Accounts
            </h2>
            <span className="text-xs text-muted-foreground">
              {users.length} {users.length === 1 ? "user" : "users"}
            </span>
          </div>

          {users.length === 0 ? (
            <p className="px-5 py-10 text-center text-sm text-muted-foreground">
              No user accounts yet. Create the first account with the form.
            </p>
          ) : (
            <div>
              {users.map((account) => {
                const isSelf = account.id === currentUser.id;
                const busy = savingUserId === account.id;
                return (
                  <article
                    key={account.id}
                    className="border-b border-border px-5 py-5 last:border-b-0"
                  >
                    <div className="flex flex-wrap items-start justify-between gap-4">
                      <div className="flex min-w-0 items-start gap-3">
                        <span
                          aria-hidden="true"
                          className="grid h-10 w-10 flex-none place-items-center rounded-full bg-primary/10 text-xs font-semibold text-primary"
                        >
                          {initials(account.full_name)}
                        </span>
                        <div className="min-w-0">
                          <h3 className="text-sm font-semibold text-foreground">
                            {account.full_name}
                            {isSelf ? (
                              <span className="ml-2 text-xs font-normal text-muted-foreground">
                                You
                              </span>
                            ) : null}
                          </h3>
                          <p className="mt-0.5 truncate text-xs text-muted-foreground">
                            @{account.username} · {account.email}
                          </p>
                          <p className="mt-1 text-xs text-muted-foreground">
                            Created {formatDate(account.created_at)} · Last
                            sign-in {formatDate(account.last_login_at)}
                          </p>
                        </div>
                      </div>
                      <div className="flex flex-wrap items-center gap-3">
                        <div className="flex flex-wrap gap-1.5">
                          {account.roles.map((role) => (
                            <span
                              key={role}
                              className="rounded-full border border-border bg-muted/60 px-2 py-0.5 text-[11px] font-medium text-foreground"
                            >
                              {role
                                .replaceAll("_", " ")
                                .toLowerCase()
                                .replace(/^\w/, (letter) =>
                                  letter.toUpperCase(),
                                )}
                            </span>
                          ))}
                        </div>
                        <span
                          className={`rounded-full border px-2.5 py-0.5 text-[11px] font-semibold ${STATUS_STYLES[account.status]}`}
                        >
                          {account.status.toLowerCase()}
                        </span>
                      </div>
                    </div>

                    {isSelf ? (
                      <p className="mt-3 text-xs text-muted-foreground">
                        Your own roles and status cannot be changed here.
                      </p>
                    ) : (
                      <div className="mt-4 grid gap-3 border-t border-border pt-4 md:grid-cols-[minmax(0,1fr)_220px] md:items-start">
                        <details className="rounded-lg border border-border bg-background/50">
                          <summary className="cursor-pointer px-3 py-2 text-xs font-semibold text-primary">
                            Manage roles
                          </summary>
                          <form
                            key={account.roles.join("-")}
                            onSubmit={(event) =>
                              void handleRoles(event, account)
                            }
                            className="border-t border-border px-3 pb-3 pt-3"
                          >
                            <fieldset>
                              <legend className="sr-only">
                                Roles for {account.full_name}
                              </legend>
                              <div className="grid gap-2 sm:grid-cols-2">
                                {ROLE_OPTIONS.map((role) => (
                                  <label
                                    key={role.code}
                                    className="flex items-start gap-2 rounded-md border border-border bg-card p-2.5 text-xs"
                                  >
                                    <input
                                      type="checkbox"
                                      name="roles"
                                      value={role.code}
                                      defaultChecked={account.roles.includes(
                                        role.code,
                                      )}
                                      className="mt-0.5 h-3.5 w-3.5 accent-[var(--primary)]"
                                    />
                                    <span>
                                      <b className="block font-semibold text-foreground">
                                        {role.label}
                                      </b>
                                      <span className="mt-0.5 block text-muted-foreground">
                                        {role.description}
                                      </span>
                                    </span>
                                  </label>
                                ))}
                              </div>
                            </fieldset>
                            <Button
                              type="submit"
                              size="sm"
                              className="mt-3"
                              disabled={busy}
                            >
                              {busy ? "Saving…" : "Save roles"}
                            </Button>
                          </form>
                        </details>

                        <label className="grid gap-1 text-xs font-medium text-muted-foreground">
                          Account status
                          <select
                            value={account.status}
                            aria-label={`Status for ${account.full_name}`}
                            disabled={busy}
                            onChange={(event) =>
                              void handleStatus(
                                account,
                                event.target.value as UserStatus,
                              )
                            }
                            className="h-8 rounded-lg border border-input bg-background px-2 text-sm text-foreground"
                          >
                            {STATUS_OPTIONS.map((option) => (
                              <option key={option.value} value={option.value}>
                                {option.label}
                              </option>
                            ))}
                          </select>
                        </label>
                      </div>
                    )}
                  </article>
                );
              })}
            </div>
          )}
        </section>

        <aside
          aria-labelledby="create-user-heading"
          className="rounded-xl border border-border bg-card p-5 lg:sticky lg:top-24"
        >
          <h2 id="create-user-heading" className="text-base font-semibold">
            Create account
          </h2>
          <p className="mt-1 text-xs text-muted-foreground">
            Passwords are hashed by the backend. Share the initial password
            with the user through a secure channel.
          </p>
          <form onSubmit={handleCreate} className="mt-4 grid gap-3.5">
            <label className="grid gap-1.5 text-xs font-medium text-muted-foreground">
              Full name
              <Input name="full_name" required maxLength={200} />
            </label>
            <label className="grid gap-1.5 text-xs font-medium text-muted-foreground">
              Username
              <Input
                name="username"
                required
                minLength={3}
                maxLength={100}
                pattern="[a-zA-Z0-9._-]+"
                autoComplete="off"
                placeholder="faculty.name"
              />
            </label>
            <label className="grid gap-1.5 text-xs font-medium text-muted-foreground">
              Email
              <Input
                name="email"
                type="email"
                required
                autoComplete="off"
                placeholder="faculty.name@institution.edu"
              />
            </label>
            <label className="grid gap-1.5 text-xs font-medium text-muted-foreground">
              Initial password
              <Input
                name="password"
                type="password"
                required
                minLength={8}
                maxLength={128}
                autoComplete="new-password"
                placeholder="At least 8 characters"
              />
            </label>

            <fieldset>
              <legend className="text-xs font-medium text-muted-foreground">
                Roles
              </legend>
              <div className="mt-2 grid gap-2">
                {ROLE_OPTIONS.map((role) => (
                  <label
                    key={role.code}
                    className="flex items-start gap-2 rounded-md border border-border bg-background/50 p-2.5 text-xs"
                  >
                    <input
                      type="checkbox"
                      name="roles"
                      value={role.code}
                      defaultChecked={role.code === "FACULTY"}
                      className="mt-0.5 h-3.5 w-3.5 accent-[var(--primary)]"
                    />
                    <span>
                      <b className="block font-semibold text-foreground">
                        {role.label}
                      </b>
                      <span className="mt-0.5 block text-muted-foreground">
                        {role.description}
                      </span>
                    </span>
                  </label>
                ))}
              </div>
            </fieldset>

            <Button type="submit" disabled={creating}>
              {creating ? "Creating…" : "Create account"}
            </Button>
          </form>
        </aside>
      </div>
    </main>
  );
}
