"use client";

import "./curricula.css";
import Link from "next/link";
import { useEffect, useState } from "react";
import { ApiError, api, Curriculum } from "@/lib/api";

export default function CurriculaPage() {
  const [curricula, setCurricula] = useState<Curriculum[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    api.listCurricula()
      .then((rows) => { if (!cancelled) setCurricula(rows); })
      .catch((caught) => {
        if (!cancelled) setError(caught instanceof ApiError ? caught.message : "Could not load curriculums.");
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  return <main className="academic-page">
    <header className="academic-heading">
      <div><h1>Curriculums</h1><span>Browse and open saved curriculums.</span></div>
      <div className="academic-heading-actions">
        <Link className="curricula-generate-link" href="/generate-curriculum">Generate curriculum</Link>
      </div>
    </header>
    {error && <p className="academic-alert academic-alert--error" role="alert">{error}</p>}
    <section className="curricula-index" aria-labelledby="curricula-index-title">
      <div className="curricula-index__heading">
        <h2 id="curricula-index-title">All curriculums</h2>
        {!loading && <span>{curricula.length} {curricula.length === 1 ? "curriculum" : "curriculums"}</span>}
      </div>
      {loading ? <p className="academic-empty" role="status">Loading curriculums…</p>
        : curricula.length ? <ul className="curricula-index__list">{curricula.map((item) => <li key={item.id}>
          <Link href={`/curricula/${encodeURIComponent(item.id)}`}>
            <span><strong>{item.title || `${item.program_code} curriculum`}</strong><small>{item.program_code} · {item.program_name}</small></span>
            <span className="curricula-index__meta"><small>{item.regulation} · {item.academic_year}</small><small>Saved {new Date(item.created_at).toLocaleDateString()}</small></span>
          </Link>
        </li>)}</ul> : <div className="curricula-index__empty"><p>No curriculums saved yet.</p><span>Generate a curriculum from your reference documents to see it here.</span><Link href="/generate-curriculum">Generate a curriculum</Link></div>}
    </section>
  </main>;
}
