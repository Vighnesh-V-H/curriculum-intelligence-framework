"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { ApiError, api, getStoredToken, storeToken } from "@/lib/api";
import { ThemeToggle } from "@/components/theme-toggle";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (getStoredToken()) {
      router.replace("/dashboard");
    }
  }, [router]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const result = await api.login(username.trim(), password);
      storeToken(result.access_token);
      router.replace("/dashboard");
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : "Unable to reach the authentication service.",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="auth-shell">
      <section className="auth-panel">
        <div className="auth-panel-theme"><ThemeToggle /></div>
        <div className="auth-aside">
          <Link href="/" className="brand-mark"><span className="brand-symbol">C</span> Curriculum Intelligence</Link>
          <div className="auth-aside-copy">
            <span className="auth-kicker">A clearer view of your curriculum</span>
            <p>Bring every course, outcome, and document into focus.</p>
            <div className="auth-illustration"><span>PROGRAM OUTCOMES</span><i /><i /><i /><span>COURSE ALIGNMENT</span></div>
          </div>
          <span className="auth-aside-foot">Designed for better learning journeys.</span>
        </div>
        <div className="auth-form-wrap">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-primary">
          Sign in to your workspace
        </p>
        <h1 className="mt-3 text-2xl font-semibold text-foreground">Sign in</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Use your institution account to access curriculum review and
          verification tools.
        </p>

        <form className="mt-8 space-y-5" onSubmit={handleSubmit}>
          <div>
            <label
              className="block text-sm font-medium text-foreground"
              htmlFor="username"
            >
              Username or email
            </label>
            <input
              id="username"
              name="username"
              autoComplete="username"
              required
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              className="mt-2 w-full rounded-lg border border-input px-3 py-2 text-foreground outline-none transition focus:border-ring focus:ring-2 focus:ring-ring/30"
              placeholder="faculty.name"
            />
          </div>

          <div>
            <label
              className="block text-sm font-medium text-foreground"
              htmlFor="password"
            >
              Password
            </label>
            <input
              id="password"
              name="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="mt-2 w-full rounded-lg border border-input px-3 py-2 text-foreground outline-none transition focus:border-ring focus:ring-2 focus:ring-ring/30"
              placeholder="••••••••"
            />
          </div>

          {error ? (
            <p
              role="alert"
              className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive"
            >
              {error}
            </p>
          ) : null}

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground transition hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {loading ? "Signing in…" : "Sign in"}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-muted-foreground">
          New here?{" "}
          <Link
            href="/register"
            className="font-semibold text-primary hover:text-primary/80"
          >
            Create an account
          </Link>
        </p>
        </div>
      </section>
    </main>
  );
}
