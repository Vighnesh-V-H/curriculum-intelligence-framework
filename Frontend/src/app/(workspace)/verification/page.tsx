"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, ArrowUpRight, Check, CircleHelp, LoaderCircle, Play, RotateCw, X } from "lucide-react";

import { ApiError, api } from "@/lib/api";
import type { Curriculum, CurriculumVersion, User, VerificationFinding, VerificationRun } from "@/lib/api";

const REVIEW_ROLES = new Set(["ADMIN", "COMMITTEE_MEMBER", "REVIEWER"]);
const SEVERITIES = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"];

function errorMessage(error: unknown): string {
  return error instanceof ApiError ? error.message : "Something went wrong. Please try again.";
}

function formatDate(value: string | null): string {
  if (!value) return "—";
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

export default function VerificationPage() {
  const [user, setUser] = useState<User | null>(null);
  const [curricula, setCurricula] = useState<Curriculum[]>([]);
  const [versions, setVersions] = useState<CurriculumVersion[]>([]);
  const [runs, setRuns] = useState<VerificationRun[]>([]);
  const [findings, setFindings] = useState<VerificationFinding[]>([]);
  const [curriculumId, setCurriculumId] = useState("");
  const [versionId, setVersionId] = useState("");
  const [runId, setRunId] = useState("");
  const [category, setCategory] = useState("ALL");
  const [severity, setSeverity] = useState("ALL");
  const [reviewingId, setReviewingId] = useState<string | null>(null);
  const [reviewComment, setReviewComment] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([api.me(), api.listCurricula()])
      .then(([currentUser, items]) => {
        if (cancelled) return;
        setUser(currentUser);
        setCurricula(items);
        setCurriculumId(items[0]?.id ?? "");
      })
      .catch((caught: unknown) => {
        if (!cancelled) setError(errorMessage(caught));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    let cancelled = false;
    if (!curriculumId) return;
    api.getCurriculumVersions(curriculumId)
      .then((items) => {
        if (cancelled) return;
        setVersions(items);
        setVersionId(items[items.length - 1]?.id ?? "");
      })
      .catch((caught: unknown) => { if (!cancelled) setError(errorMessage(caught)); });
    return () => { cancelled = true; };
  }, [curriculumId]);

  const refreshRuns = useCallback(async (id: string, version: string) => {
    const items = await api.listVerificationRuns(id, version);
    setRuns(items);
    setRunId((current) => items.some((run) => run.id === current) ? current : items[0]?.id ?? "");
  }, []);

  useEffect(() => {
    let cancelled = false;
    if (!curriculumId || !versionId) return;
    api.listVerificationRuns(curriculumId, versionId)
      .then((items) => {
        if (cancelled) return;
        setRuns(items);
        setRunId(items[0]?.id ?? "");
      })
      .catch((caught: unknown) => { if (!cancelled) setError(errorMessage(caught)); });
    return () => { cancelled = true; };
  }, [curriculumId, versionId]);

  useEffect(() => {
    let cancelled = false;
    if (!runId) return;
    api.listVerificationFindings(runId)
      .then((items) => { if (!cancelled) setFindings(items); })
      .catch((caught: unknown) => { if (!cancelled) setError(errorMessage(caught)); });
    return () => { cancelled = true; };
  }, [runId]);

  const visibleFindings = useMemo(() => findings.filter((finding) =>
    (category === "ALL" || finding.category === category) &&
    (severity === "ALL" || finding.severity === severity)
  ), [findings, category, severity]);
  const selectedRun = runs.find((run) => run.id === runId) ?? null;
  const canReview = user?.roles.some((role) => REVIEW_ROLES.has(role)) ?? false;
  const selectedCurriculum = curricula.find((item) => item.id === curriculumId);
  const selectedVersion = versions.find((item) => item.id === versionId);

  async function runVerification() {
    if (!curriculumId || !versionId) return;
    setBusy(true);
    setError(null);
    try {
      const run = await api.startVerification(curriculumId, versionId);
      await refreshRuns(curriculumId, versionId);
      setRunId(run.id);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  async function submitReview(findingId: string, decision: "ACCEPTED" | "REJECTED" | "MODIFIED") {
    setBusy(true);
    setError(null);
    try {
      const updated = await api.reviewVerificationFinding(findingId, decision, reviewComment.trim());
      setFindings((current) => current.map((finding) => finding.id === findingId ? updated : finding));
      setReviewingId(null);
      setReviewComment("");
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <div className="verification-loading" role="status"><LoaderCircle aria-hidden="true" /> Loading verification workspace…</div>;

  return (
    <main className="verification-page">
      <header className="verification-heading">
        <div>
          <p className="verification-eyebrow">CURRICULUM QUALITY</p>
          <h1>Verification</h1>
          <p>Run prerequisite checks and review evidence-backed findings for a curriculum version.</p>
        </div>
        <button className="verification-run-button" type="button" onClick={runVerification} disabled={!versionId || busy || !canReview}>
          {busy ? <LoaderCircle className="verification-spin" aria-hidden="true" /> : <Play aria-hidden="true" />}
          Run checks
        </button>
      </header>

      {error ? <div className="verification-alert" role="alert"><AlertTriangle aria-hidden="true" /> <span>{error}</span><button type="button" onClick={() => setError(null)} aria-label="Dismiss error"><X aria-hidden="true" /></button></div> : null}

      <section className="verification-controls" aria-label="Select curriculum to verify">
        <label>
          <span>Curriculum</span>
          <select value={curriculumId} onChange={(event) => {
            setCurriculumId(event.target.value);
            setVersions([]);
            setVersionId("");
            setRuns([]);
            setRunId("");
            setFindings([]);
          }}>
            <option value="">Choose a curriculum</option>
            {curricula.map((item) => <option key={item.id} value={item.id}>{item.program_code} · {item.title || item.regulation}</option>)}
          </select>
        </label>
        <label>
          <span>Version</span>
          <select value={versionId} onChange={(event) => {
            setVersionId(event.target.value);
            setRuns([]);
            setRunId("");
            setFindings([]);
          }} disabled={!versions.length}>
            <option value="">Choose a version</option>
            {versions.map((version) => <option key={version.id} value={version.id}>v{version.version_label} · {version.status}</option>)}
          </select>
        </label>
        <label>
          <span>Verification run</span>
          <select value={runId} onChange={(event) => {
            setRunId(event.target.value);
            setFindings([]);
          }} disabled={!runs.length}>
            <option value="">Select a run</option>
            {runs.map((run) => <option key={run.id} value={run.id}>{formatDate(run.requested_at)} · {run.status}</option>)}
          </select>
        </label>
        <div className="verification-context">
          <span>{selectedCurriculum?.program_name ?? "No curriculum selected"}</span>
          <small>{selectedVersion ? `${selectedVersion.courses.length} active courses · ${selectedVersion.semesters.length} semesters` : "Select a version to begin"}</small>
        </div>
      </section>

      {!curricula.length ? (
        <section className="verification-empty"><CircleHelp aria-hidden="true" /><h2>No curricula available</h2><p>Create a curriculum before starting verification. Curriculum editing is available through the backend API.</p></section>
      ) : null}

      {selectedRun ? (
        <section className="verification-summary" aria-label="Selected verification run summary">
          <div><span className="verification-label">RUN RESULT</span><strong className={`verification-result verification-result--${selectedRun.summary?.result?.toLowerCase() ?? selectedRun.status.toLowerCase()}`}>{selectedRun.summary?.result ?? selectedRun.status}</strong></div>
          <div><span className="verification-label">FINDINGS</span><strong>{selectedRun.summary?.total_findings ?? findings.length}</strong></div>
          <div><span className="verification-label">STARTED</span><strong>{formatDate(selectedRun.requested_at)}</strong></div>
          <button className="verification-refresh" type="button" onClick={() => void refreshRuns(curriculumId, versionId)} disabled={busy} aria-label="Refresh verification runs"><RotateCw aria-hidden="true" /></button>
        </section>
      ) : null}

      {runs.length > 0 ? (
        <div className="verification-filter-row">
          <div><h2>Findings</h2><span>{visibleFindings.length} shown of {findings.length}</span></div>
          <label>Category<select value={category} onChange={(event) => setCategory(event.target.value)}><option value="ALL">All categories</option>{Array.from(new Set(findings.map((finding) => finding.category))).sort().map((item) => <option key={item}>{item}</option>)}</select></label>
          <label>Severity<select value={severity} onChange={(event) => setSeverity(event.target.value)}><option value="ALL">All severities</option>{SEVERITIES.filter((item) => findings.some((finding) => finding.severity === item)).map((item) => <option key={item}>{item}</option>)}</select></label>
        </div>
      ) : null}

      {runs.length === 0 && curricula.length > 0 ? (
        <section className="verification-empty"><Play aria-hidden="true" /><h2>No verification runs yet</h2><p>Select a curriculum version and run checks to create the first report.</p></section>
      ) : null}
      {runs.length > 0 && findings.length === 0 ? (
        <section className="verification-empty verification-empty--passed"><Check aria-hidden="true" /><h2>No findings in this run</h2><p>The current prerequisite checks did not identify issues in this curriculum version.</p></section>
      ) : null}

      <section className="verification-findings" aria-label="Verification findings">
        {visibleFindings.map((finding) => (
          <article className="verification-finding" key={finding.id}>
            <div className="verification-finding__topline">
              <span className={`verification-severity verification-severity--${finding.severity.toLowerCase()}`}>{finding.severity}</span>
              <span className="verification-category">{finding.category.replaceAll("_", " ")}</span>
              <span className={`verification-review-state verification-review-state--${finding.review_status.toLowerCase()}`}>{finding.review_status.replaceAll("_", " ")}</span>
              {finding.confidence !== null ? <span className="verification-confidence">{Math.round(finding.confidence * 100)}% confidence</span> : null}
            </div>
            <h3>{finding.title}</h3>
            {finding.description ? <p className="verification-finding__description">{finding.description}</p> : null}
            {finding.evidence ? <blockquote><span>Evidence</span>{finding.evidence}</blockquote> : null}
            {finding.recommendation ? <p className="verification-recommendation"><strong>Suggested review</strong>{finding.recommendation}</p> : null}
            {finding.references.length ? <div className="verification-references">Related records {finding.references.map((reference) => <span key={reference.id}>{reference.entity_type.replaceAll("_", " ")}</span>)}</div> : null}
            {finding.review_status !== "PENDING" ? <p className="verification-review-meta">Reviewed {formatDate(finding.reviewed_at)}{finding.review_comments ? ` · ${finding.review_comments}` : ""}</p> : null}
            {canReview && finding.requires_human_review ? (
              <div className="verification-review-actions">
                {reviewingId === finding.id ? (
                  <>
                    <label className="verification-comment"><span>Review note <small>(optional)</small></span><textarea value={reviewComment} onChange={(event) => setReviewComment(event.target.value)} maxLength={5000} rows={2} placeholder="Add context for this decision" /></label>
                    <div className="verification-decision-buttons">
                      <button type="button" onClick={() => void submitReview(finding.id, "ACCEPTED")} disabled={busy}><Check aria-hidden="true" /> Accept</button>
                      <button type="button" onClick={() => void submitReview(finding.id, "MODIFIED")} disabled={busy}>Mark modified</button>
                      <button type="button" onClick={() => void submitReview(finding.id, "REJECTED")} disabled={busy}><X aria-hidden="true" /> Reject</button>
                      <button className="verification-cancel" type="button" onClick={() => { setReviewingId(null); setReviewComment(""); }}>Cancel</button>
                    </div>
                  </>
                ) : <button className="verification-open-review" type="button" onClick={() => { setReviewingId(finding.id); setReviewComment(finding.review_comments ?? ""); }}>Review finding <ArrowUpRight aria-hidden="true" /></button>}
              </div>
            ) : null}
          </article>
        ))}
      </section>
    </main>
  );
}
