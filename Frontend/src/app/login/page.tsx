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
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-indigo-600">
          Sign in to your workspace
        </p>
        <h1 className="mt-3 text-2xl font-semibold text-slate-900">Sign in</h1>
        <p className="mt-2 text-sm text-slate-500">
          Use your institution account to access curriculum review and
          verification tools.
        </p>

        <form className="mt-8 space-y-5" onSubmit={handleSubmit}>
          <div>
            <label
              className="block text-sm font-medium text-slate-700"
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
              className="mt-2 w-full rounded-lg border border-slate-300 px-3 py-2 text-slate-900 outline-none transition focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200"
              placeholder="faculty.name"
            />
          </div>

          <div>
            <label
              className="block text-sm font-medium text-slate-700"
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
              className="mt-2 w-full rounded-lg border border-slate-300 px-3 py-2 text-slate-900 outline-none transition focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200"
              placeholder="••••••••"
            />
          </div>

          {error ? (
            <p
              role="alert"
              className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700"
            >
              {error}
            </p>
          ) : null}

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {loading ? "Signing in…" : "Sign in"}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-slate-500">
          New here?{" "}
          <Link
            href="/register"
            className="font-semibold text-indigo-600 hover:text-indigo-500"
          >
            Create an account
          </Link>
        </p>
        </div>
      </section>
    </main>
  );
}
