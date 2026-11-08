"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { ApiError, api, storeToken } from "@/lib/api";
import { ThemeToggle } from "@/components/theme-toggle";

export default function RegisterPage() {
  const router = useRouter();
  const [fullName, setFullName] = useState("");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError(null);

    try {
      await api.register({
        username: username.trim(),
        email: email.trim(),
        password,
        full_name: fullName.trim(),
      });
      try {
        const result = await api.login(username.trim(), password);
        storeToken(result.access_token);
        router.replace("/dashboard");
        return;
      } catch {
        router.push("/login");
        return;
      }
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
            <span className="auth-kicker">Build with intention</span>
            <p>Turn curriculum evidence into a learning experience that adds up.</p>
            <div className="auth-illustration"><span>LEARNING GOALS</span><i /><i /><i /><span>CURRICULUM DESIGN</span></div>
          </div>
          <span className="auth-aside-foot">Designed for better learning journeys.</span>
        </div>
        <div className="auth-form-wrap">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-primary">
          Create your workspace account
        </p>
        <h1 className="mt-3 text-2xl font-semibold text-foreground">
          Create your account
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Self-register with faculty access. Committee and reviewer roles are
          assigned by an administrator.
        </p>

        <form className="mt-8 space-y-5" onSubmit={handleSubmit}>
          <div>
            <label
              className="block text-sm font-medium text-foreground"
              htmlFor="full_name"
            >
              Full name
            </label>
            <input
              id="full_name"
              name="full_name"
              autoComplete="name"
              required
              value={fullName}
              onChange={(event) => setFullName(event.target.value)}
              className="mt-2 w-full rounded-lg border border-input px-3 py-2 text-foreground outline-none transition focus:border-ring focus:ring-2 focus:ring-ring/30"
              placeholder="Faculty Name"
            />
          </div>

          <div>
            <label
              className="block text-sm font-medium text-foreground"
              htmlFor="username"
            >
              Username
            </label>
            <input
              id="username"
              name="username"
              autoComplete="username"
              required
              minLength={3}
              pattern="[A-Za-z0-9._-]+"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              className="mt-2 w-full rounded-lg border border-input px-3 py-2 text-foreground outline-none transition focus:border-ring focus:ring-2 focus:ring-ring/30"
              placeholder="faculty.name"
            />
          </div>

          <div>
            <label
              className="block text-sm font-medium text-foreground"
              htmlFor="email"
            >
              Email
            </label>
            <input
              id="email"
              name="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className="mt-2 w-full rounded-lg border border-input px-3 py-2 text-foreground outline-none transition focus:border-ring focus:ring-2 focus:ring-ring/30"
              placeholder="faculty.name@institution.edu"
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
              autoComplete="new-password"
              required
              minLength={8}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="mt-2 w-full rounded-lg border border-input px-3 py-2 text-foreground outline-none transition focus:border-ring focus:ring-2 focus:ring-ring/30"
              placeholder="At least 8 characters"
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
            {loading ? "Creating account…" : "Create account"}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-muted-foreground">
          Already have an account?{" "}
          <Link
            href="/login"
            className="font-semibold text-primary hover:text-primary/80"
          >
            Sign in
          </Link>
        </p>
        </div>
      </section>
    </main>
  );
}
