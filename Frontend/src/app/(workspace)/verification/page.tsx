"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  ArrowUpRight,
  BookOpen,
  Check,
  CircleHelp,
  GitBranch,
  Layers3,
  LoaderCircle,
  Pencil,
  Play,
  Plus,
  RotateCw,
  Scale,
  X,
} from "lucide-react";

import { VerificationGraph } from "@/components/verification-graph";
import { ApiError, api } from "@/lib/api";
import type {
  Curriculum,
  CurriculumVersion,
  Prerequisite,
  User,
  VerificationFinding,
  VerificationReference,
  VerificationReferenceRules,
  VerificationReferenceType,
  VerificationReport,
  VerificationRun,
} from "@/lib/api";

const REVIEW_ROLES = new Set(["ADMIN", "COMMITTEE_MEMBER", "REVIEWER"]);
const REFERENCE_MANAGE_ROLES = new Set(["ADMIN", "COMMITTEE_MEMBER"]);
const SEVERITIES = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"];
const REFERENCE_TYPES: VerificationReferenceType[] = [
  "INSTITUTIONAL",
  "OBE",
  "ACCREDITATION",
  "INDUSTRY",
];

const RULE_TEMPLATES: Record<VerificationReferenceType, VerificationReferenceRules> = {
  INSTITUTIONAL: {
    total_credits: { min: 120, max: 160 },
    semester_credits: { min: 12, max: 24 },
  },
  OBE: {
    required_po_codes: ["PO1", "PO2"],
    min_po_coverage_ratio: 1,
    min_approved_mapping_ratio: 0.8,
  },
  ACCREDITATION: {
    criterion: "Criterion 4: continuous improvement",
    required_course_types: ["LAB", "PROJECT"],
    min_po_coverage_ratio: 0.8,
  },
  INDUSTRY: {
    skills: [
      {
        code: "CLOUD",
        label: "Cloud engineering",
        keywords: ["cloud", "kubernetes"],
        required: true,
        min_courses: 1,
      },
    ],
    min_required_skill_coverage_ratio: 0.8,
  },
};

function errorMessage(error: unknown): string {
  return error instanceof ApiError ? error.message : "Something went wrong. Please try again.";
}

function formatDate(value: string | null): string {
  if (!value) return "—";
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

function formatDateOnly(value: string | null): string {
  if (!value) return "—";
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(new Date(`${value.slice(0, 10)}T00:00:00`));
}

function rangeLabel(range: { min?: number | null; max?: number | null } | undefined): string {
  if (!range) return "—";
  if (range.min != null && range.max != null) return `${range.min}–${range.max}`;
  if (range.min != null) return `≥ ${range.min}`;
  if (range.max != null) return `≤ ${range.max}`;
  return "—";
}

function referenceRulesSummary(reference: VerificationReference): string[] {
  const rules = reference.rules;
  const parts: string[] = [];
  if (rules.total_credits) parts.push(`Total credits ${rangeLabel(rules.total_credits)}`);
  if (rules.semester_credits) parts.push(`Semester credits ${rangeLabel(rules.semester_credits)}`);
  if (rules.semester_count) parts.push(`Semesters ${rangeLabel(rules.semester_count)}`);
  for (const [type, range] of Object.entries(rules.course_type_credits ?? {})) {
    parts.push(`${type} credits ${rangeLabel(range)}`);
  }
  for (const [type, range] of Object.entries(rules.course_type_share ?? {})) {
    parts.push(`${type} share ${rangeLabel(range)}`);
  }
  if (rules.required_po_codes?.length) parts.push(`POs ${rules.required_po_codes.join(", ")}`);
  if (rules.required_peo_codes?.length) parts.push(`PEOs ${rules.required_peo_codes.join(", ")}`);
  if (rules.required_course_types?.length) parts.push(`Course types ${rules.required_course_types.join(", ")}`);
  if (rules.criterion) parts.push(rules.criterion);
  if (rules.min_po_coverage_ratio != null) parts.push(`PO coverage ≥ ${Math.round(rules.min_po_coverage_ratio * 100)}%`);
  if (rules.min_approved_mapping_ratio != null) parts.push(`Approved mappings ≥ ${Math.round(rules.min_approved_mapping_ratio * 100)}%`);
  if (rules.skills?.length) parts.push(`Skills ${rules.skills.map((skill) => skill.code).join(", ")}`);
  if (rules.min_required_skill_coverage_ratio != null) {
    parts.push(`Required skills ≥ ${Math.round(rules.min_required_skill_coverage_ratio * 100)}%`);
  }
  return parts;
}

export default function VerificationPage() {
  const [user, setUser] = useState<User | null>(null);
  const [curricula, setCurricula] = useState<Curriculum[]>([]);
  const [versions, setVersions] = useState<CurriculumVersion[]>([]);
  const [runs, setRuns] = useState<VerificationRun[]>([]);
  const [findings, setFindings] = useState<VerificationFinding[]>([]);
  const [prerequisites, setPrerequisites] = useState<Prerequisite[]>([]);
  const [references, setReferences] = useState<VerificationReference[]>([]);
  const [curriculumId, setCurriculumId] = useState("");
  const [versionId, setVersionId] = useState("");
  const [runId, setRunId] = useState("");
  const [category, setCategory] = useState("ALL");
  const [severity, setSeverity] = useState("ALL");
  const [reviewingId, setReviewingId] = useState<string | null>(null);
  const [reviewComment, setReviewComment] = useState("");
  const [report, setReport] = useState<VerificationReport | null>(null);
  const [groupBy, setGroupBy] = useState<"category" | "severity" | "review_status">("category");
  const [reviewStatus, setReviewStatus] = useState("ALL");
  const [reportNonce, setReportNonce] = useState(0);
  const [referenceNonce, setReferenceNonce] = useState(0);
  const [editingReferenceId, setEditingReferenceId] = useState<string | null>(null);
  const [referenceType, setReferenceType] = useState<VerificationReferenceType>("INSTITUTIONAL");
  const [referenceProgramId, setReferenceProgramId] = useState("");
  const [referenceCode, setReferenceCode] = useState("");
  const [referenceTitle, setReferenceTitle] = useState("");
  const [referenceSource, setReferenceSource] = useState("");
  const [referenceVersion, setReferenceVersion] = useState("1.0");
  const [referenceSeverity, setReferenceSeverity] = useState("MEDIUM");
  const [referenceEffectiveDate, setReferenceEffectiveDate] = useState("");
  const [referenceRules, setReferenceRules] = useState(
    JSON.stringify(RULE_TEMPLATES.INSTITUTIONAL, null, 2),
  );
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

  useEffect(() => {
    let cancelled = false;
    if (!curriculumId || !versionId) return;
    api.listPrerequisites(curriculumId, versionId)
      .then((items) => { if (!cancelled) setPrerequisites(items); })
      .catch((caught: unknown) => { if (!cancelled) setError(errorMessage(caught)); });
    return () => { cancelled = true; };
  }, [curriculumId, versionId]);

  const selectedCurriculum = curricula.find((item) => item.id === curriculumId);
  const selectedVersion = versions.find((item) => item.id === versionId);
  const selectedProgramId = selectedCurriculum?.program_id ?? "";

  useEffect(() => {
    let cancelled = false;
    if (!selectedProgramId) return;
    api.listVerificationReferences({
      program_id: selectedProgramId,
      include_inactive: true,
    })
      .then((items) => { if (!cancelled) setReferences(items); })
      .catch((caught: unknown) => { if (!cancelled) setError(errorMessage(caught)); });
    return () => { cancelled = true; };
  }, [selectedProgramId, referenceNonce]);

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

  useEffect(() => {
    let cancelled = false;
    if (!runId) return;
    api.getVerificationReport(runId, groupBy)
      .then((data) => { if (!cancelled) setReport(data); })
      .catch((caught: unknown) => { if (!cancelled) setError(errorMessage(caught)); });
    return () => { cancelled = true; };
  }, [runId, groupBy, reportNonce]);

  const matchesFilters = useCallback((finding: VerificationFinding) =>
    (category === "ALL" || finding.category === category) &&
    (severity === "ALL" || finding.severity === severity) &&
    (reviewStatus === "ALL" || finding.review_status === reviewStatus)
  , [category, severity, reviewStatus]);
  const visibleFindings = useMemo(() => findings.filter(matchesFilters), [findings, matchesFilters]);
  const visibleReportGroups = useMemo(() => (report?.groups ?? [])
    .map((group) => ({ ...group, findings: group.findings.filter(matchesFilters) }))
    .filter((group) => group.findings.length > 0), [report, matchesFilters]);
  const selectedRun = runs.find((run) => run.id === runId) ?? null;
  const canReview = user?.roles.some((role) => REVIEW_ROLES.has(role)) ?? false;
  const canManageReferences = user?.roles.some((role) => REFERENCE_MANAGE_ROLES.has(role)) ?? false;
  const programs = useMemo(() => {
    const byId = new Map<string, { id: string; code: string; name: string }>();
    for (const item of curricula) {
      if (!byId.has(item.program_id)) {
        byId.set(item.program_id, {
          id: item.program_id,
          code: item.program_code,
          name: item.program_name,
        });
      }
    }
    return Array.from(byId.values()).sort((left, right) => left.code.localeCompare(right.code));
  }, [curricula]);

  const summary = selectedRun?.summary;
  const prerequisiteGraph = summary?.prerequisite_graph;
  const structure = summary?.structure;
  const topicOverlap = summary?.topic_overlap;
  const referenceComparison = summary?.reference_comparison;
  const activeReferenceCount = references.filter((reference) => reference.status === "ACTIVE").length;

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
      setReportNonce((value) => value + 1);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  function resetReferenceForm() {
    setEditingReferenceId(null);
    setReferenceType("INSTITUTIONAL");
    setReferenceProgramId("");
    setReferenceCode("");
    setReferenceTitle("");
    setReferenceSource("");
    setReferenceVersion("1.0");
    setReferenceSeverity("MEDIUM");
    setReferenceEffectiveDate("");
    setReferenceRules(JSON.stringify(RULE_TEMPLATES.INSTITUTIONAL, null, 2));
  }

  function startEditingReference(reference: VerificationReference) {
    setEditingReferenceId(reference.id);
    setReferenceType(reference.reference_type);
    setReferenceProgramId(reference.program_id ?? "");
    setReferenceCode(reference.code);
    setReferenceTitle(reference.title);
    setReferenceSource(reference.source);
    setReferenceVersion(reference.version_label);
    setReferenceSeverity(reference.severity);
    setReferenceEffectiveDate(reference.effective_date?.slice(0, 10) ?? "");
    setReferenceRules(JSON.stringify(reference.rules, null, 2));
  }

  async function submitReference(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!referenceCode.trim() || !referenceTitle.trim() || !referenceSource.trim()) {
      setError("Reference code, title, and source are required.");
      return;
    }
    let rules: VerificationReferenceRules;
    try {
      rules = JSON.parse(referenceRules) as VerificationReferenceRules;
    } catch {
      setError("Reference rules must be valid JSON.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      if (editingReferenceId) {
        await api.updateVerificationReference(editingReferenceId, {
          title: referenceTitle.trim(),
          source: referenceSource.trim(),
          version_label: referenceVersion.trim(),
          effective_date: referenceEffectiveDate || null,
          severity: referenceSeverity,
          rules,
        });
      } else {
        await api.createVerificationReference({
          program_id: referenceProgramId || null,
          reference_type: referenceType,
          code: referenceCode.trim().toUpperCase(),
          title: referenceTitle.trim(),
          source: referenceSource.trim(),
          version_label: referenceVersion.trim() || "1.0",
          effective_date: referenceEffectiveDate || null,
          severity: referenceSeverity,
          rules,
        });
      }
      setReferenceNonce((value) => value + 1);
      resetReferenceForm();
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  async function toggleReferenceStatus(reference: VerificationReference) {
    setBusy(true);
    setError(null);
    try {
      await api.updateVerificationReference(reference.id, {
        status: reference.status === "ACTIVE" ? "INACTIVE" : "ACTIVE",
      });
      setReferenceNonce((value) => value + 1);
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
          <p>Run prerequisite, content, structure, outcome, and governed-reference checks, then review evidence-backed findings for a curriculum version.</p>
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
            setFindings([]); setReport(null); setPrerequisites([]);
            setReferences([]);
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
            setFindings([]); setReport(null); setPrerequisites([]);
          }} disabled={!versions.length}>
            <option value="">Choose a version</option>
            {versions.map((version) => <option key={version.id} value={version.id}>v{version.version_label} · {version.status}</option>)}
          </select>
        </label>
        <label>
          <span>Verification run</span>
          <select value={runId} onChange={(event) => {
            setRunId(event.target.value);
            setFindings([]); setReport(null);
          }} disabled={!runs.length}>
            <option value="">Select a run</option>
            {runs.map((run) => <option key={run.id} value={run.id}>{formatDate(run.requested_at)} · {run.status}{run.is_stale ? " · STALE" : ""}</option>)}
          </select>
        </label>
        <div className="verification-context">
          <span>{selectedCurriculum?.program_name ?? "No curriculum selected"}</span>
          <small>{selectedVersion ? `${selectedVersion.courses.length} courses · ${selectedVersion.semesters.length} semesters · ${activeReferenceCount} active references` : "Select a version to begin"}</small>
        </div>
      </section>

      {!curricula.length ? (
        <section className="verification-empty"><CircleHelp aria-hidden="true" /><h2>No curricula available</h2><p>Create a curriculum before starting verification. Curriculum editing is available through the backend API.</p></section>
      ) : null}

      {selectedRun?.is_stale ? (
        <div className="verification-stale-banner" role="status">
          <AlertTriangle aria-hidden="true" />
          <div>
            <strong>Curriculum inputs changed since this run</strong>
            <span>The findings are a historical snapshot. Re-run verification to evaluate the current curriculum data and governed references.</span>
          </div>
          <button type="button" onClick={runVerification} disabled={busy || !canReview}>
            {busy ? <LoaderCircle className="verification-spin" aria-hidden="true" /> : <RotateCw aria-hidden="true" />}
            Re-run checks
          </button>
        </div>
      ) : null}

      {selectedRun ? (
        <section className="verification-summary" aria-label="Selected verification run summary">
          <div><span className="verification-label">RUN RESULT</span><strong className={`verification-result verification-result--${selectedRun.summary?.result?.toLowerCase() ?? selectedRun.status.toLowerCase()}`}>{selectedRun.summary?.result ?? selectedRun.status}</strong></div>
          <div><span className="verification-label">FINDINGS</span><strong>{selectedRun.summary?.total_findings ?? findings.length}</strong></div>
          <div><span className="verification-label">STARTED</span><strong>{formatDate(selectedRun.requested_at)}</strong></div>
          <div><span className="verification-label">INPUTS</span><strong className={selectedRun.is_stale ? "verification-stale" : ""}>{selectedRun.is_stale ? "Stale" : "Current"}</strong></div>
          <button className="verification-refresh" type="button" onClick={() => void refreshRuns(curriculumId, versionId)} disabled={busy} aria-label="Refresh verification runs"><RotateCw aria-hidden="true" /></button>
        </section>
      ) : null}

      {summary ? (
        <section className="verification-analysis" aria-label="Verification analysis summary">
          <div className="verification-analysis__card">
            <div className="verification-analysis__heading"><GitBranch aria-hidden="true" /><span>PREREQUISITE CHAINS</span></div>
            {prerequisiteGraph ? (
              <>
                <strong>{prerequisiteGraph.longest_chain_length} course longest chain</strong>
                <p>{prerequisiteGraph.longest_chain.length ? prerequisiteGraph.longest_chain.join(" → ") : "No prerequisite edges."}</p>
                <dl>
                  <div><dt>Edges</dt><dd>{prerequisiteGraph.edge_count}</dd></div>
                  <div><dt>Redundant</dt><dd>{prerequisiteGraph.transitive_redundant_edges}</dd></div>
                  <div><dt>Roots</dt><dd>{prerequisiteGraph.root_courses.length}</dd></div>
                  <div><dt>Leaves</dt><dd>{prerequisiteGraph.leaf_courses.length}</dd></div>
                </dl>
              </>
            ) : <p>No prerequisite summary in this run.</p>}
          </div>
          <div className="verification-analysis__card">
            <div className="verification-analysis__heading"><Scale aria-hidden="true" /><span>CREDITS & DISTRIBUTION</span></div>
            {structure ? (
              <>
                <strong>{structure.total_credits} total credits</strong>
                <p>{structure.active_course_count} active courses across {structure.semester_count} semesters · average {structure.average_semester_credits} credits per semester.</p>
                <dl>
                  <div><dt>Semester range</dt><dd>{structure.semester_credit_range.min}–{structure.semester_credit_range.max}</dd></div>
                  <div><dt>Expected semesters</dt><dd>{structure.expected_semester_count ?? "—"}</dd></div>
                </dl>
                <div className="verification-analysis__chips">
                  {Object.entries(structure.credits_by_course_type).map(([type, credits]) => <span key={type}>{type} {credits}</span>)}
                </div>
              </>
            ) : <p>No structure summary in this run.</p>}
          </div>
          <div className="verification-analysis__card">
            <div className="verification-analysis__heading"><BookOpen aria-hidden="true" /><span>TOPIC OVERLAP</span></div>
            {topicOverlap ? (
              <>
                <strong>{topicOverlap.candidates} topic candidates</strong>
                <p>{topicOverlap.pairs_evaluated} course pairs evaluated from names, descriptions, syllabi, and course outcomes.</p>
                <dl>
                  <div><dt>Redundancy</dt><dd>{topicOverlap.redundancy_candidates}</dd></div>
                  <div><dt>Progression</dt><dd>{topicOverlap.progression_candidates}</dd></div>
                  <div><dt>Unverified</dt><dd>{topicOverlap.unverified_progression_candidates}</dd></div>
                  <div><dt>Cross-discipline</dt><dd>{topicOverlap.cross_discipline_candidates}</dd></div>
                </dl>
              </>
            ) : <p>No topic summary in this run.</p>}
          </div>
          <div className="verification-analysis__card">
            <div className="verification-analysis__heading"><Layers3 aria-hidden="true" /><span>GOVERNED REFERENCES</span></div>
            {referenceComparison ? (
              <>
                <strong>{referenceComparison.checked ? `${referenceComparison.count} references evaluated` : "Not configured"}</strong>
                <p>{referenceComparison.checked ? "Institutional, OBE, accreditation, and industry rules were compared with curriculum evidence." : "Configure an active governed reference to enable reference comparison findings."}</p>
                <dl>
                  <div><dt>Active</dt><dd>{activeReferenceCount}</dd></div>
                  <div><dt>Invalid</dt><dd>{referenceComparison.invalid_references.length}</dd></div>
                </dl>
                <div className="verification-analysis__chips">
                  {referenceComparison.references.map((reference) => <span key={reference.id}>{reference.type} · {reference.code}</span>)}
                </div>
              </>
            ) : <p>No reference comparison in this run.</p>}
          </div>
        </section>
      ) : null}

      {selectedVersion ? (
        <section className="verification-map-panel" aria-label="Verification-aware curriculum map">
          <div className="verification-map-panel__heading">
            <div><span className="verification-label">CURRICULUM MAP</span><h2>Verification-aware course graph</h2><p>Courses are grouped by semester. Edges show prerequisite relationships; node colour reflects the highest linked finding.</p></div>
            {selectedRun ? <span className="verification-map-panel__run">{formatDate(selectedRun.requested_at)}</span> : null}
          </div>
          <VerificationGraph
            courses={selectedVersion.courses}
            prerequisites={prerequisites}
            findings={findings}
            topicOverlaps={topicOverlap?.top_overlaps ?? []}
          />
        </section>
      ) : null}

      <details className="verification-reference-panel">
        <summary>
          <div>
            <span className="verification-label">GOVERNED REFERENCES</span>
            <h2>Reference comparison setup</h2>
            <p>Institution-wide references apply everywhere. A program-specific reference with the same type and code overrides the institution-wide rule.</p>
          </div>
          <span className="verification-reference-panel__count">{activeReferenceCount} active · {references.length} total</span>
        </summary>
        <div className="verification-reference-panel__body">
          <div className="verification-reference-list">
            {references.length ? references.map((reference) => (
              <article className={`verification-reference-card${reference.status === "INACTIVE" ? " is-inactive" : ""}`} key={reference.id}>
                <div className="verification-reference-card__topline">
                  <span className="verification-category">{reference.reference_type}</span>
                  <span className="verification-reference-card__scope">{reference.program_id ? (programs.find((program) => program.id === reference.program_id)?.code ?? "Program") : "Institution-wide"}</span>
                  <span className={`verification-reference-card__status verification-reference-card__status--${reference.status.toLowerCase()}`}>{reference.status}</span>
                  <span className={`verification-severity verification-severity--${reference.severity.toLowerCase()}`}>{reference.severity}</span>
                </div>
                <h3>{reference.code} · {reference.title}</h3>
                <p>{reference.source} · version {reference.version_label} · effective {formatDateOnly(reference.effective_date)}</p>
                <div className="verification-reference-card__rules">
                  {referenceRulesSummary(reference).map((rule) => <span key={rule}>{rule}</span>)}
                </div>
                {canManageReferences ? (
                  <div className="verification-reference-card__actions">
                    <button type="button" onClick={() => startEditingReference(reference)}><Pencil aria-hidden="true" /> Edit</button>
                    <button type="button" onClick={() => void toggleReferenceStatus(reference)} disabled={busy}>{reference.status === "ACTIVE" ? "Deactivate" : "Activate"}</button>
                  </div>
                ) : null}
              </article>
            )) : <p className="verification-reference-empty">No governed references are configured for this program yet.</p>}
          </div>

          {canManageReferences ? (
            <form className="verification-reference-form" onSubmit={submitReference}>
              <div className="verification-reference-form__heading">
                <div><span className="verification-label">{editingReferenceId ? "EDIT REFERENCE" : "NEW REFERENCE"}</span><h3>{editingReferenceId ? "Update governed rule" : "Add a governed reference"}</h3></div>
                {editingReferenceId ? <button type="button" className="verification-reference-form__cancel" onClick={resetReferenceForm}><X aria-hidden="true" /> Cancel edit</button> : null}
              </div>
              <div className="verification-reference-form__grid">
                <label>Scope<select value={referenceProgramId} onChange={(event) => setReferenceProgramId(event.target.value)} disabled={Boolean(editingReferenceId)}><option value="">Institution-wide</option>{programs.map((program) => <option key={program.id} value={program.id}>{program.code} · {program.name}</option>)}</select></label>
                <label>Type<select value={referenceType} onChange={(event) => {
                  const next = event.target.value as VerificationReferenceType;
                  setReferenceType(next);
                  if (!editingReferenceId) setReferenceRules(JSON.stringify(RULE_TEMPLATES[next], null, 2));
                }} disabled={Boolean(editingReferenceId)}>{REFERENCE_TYPES.map((type) => <option key={type} value={type}>{type}</option>)}</select></label>
                <label>Code<input value={referenceCode} onChange={(event) => setReferenceCode(event.target.value)} placeholder="INST-2026" maxLength={50} disabled={Boolean(editingReferenceId)} /></label>
                <label>Version<input value={referenceVersion} onChange={(event) => setReferenceVersion(event.target.value)} placeholder="1.0" maxLength={50} /></label>
                <label className="verification-reference-form__wide">Title<input value={referenceTitle} onChange={(event) => setReferenceTitle(event.target.value)} placeholder="Institutional credit and distribution rules" maxLength={200} /></label>
                <label className="verification-reference-form__wide">Source<input value={referenceSource} onChange={(event) => setReferenceSource(event.target.value)} placeholder="Policy manual and section" maxLength={300} /></label>
                <label>Severity<select value={referenceSeverity} onChange={(event) => setReferenceSeverity(event.target.value)}>{SEVERITIES.map((item) => <option key={item}>{item}</option>)}</select></label>
                <label>Effective date<input type="date" value={referenceEffectiveDate} onChange={(event) => setReferenceEffectiveDate(event.target.value)} /></label>
              </div>
              <label className="verification-reference-form__rules">Rules (JSON)<textarea value={referenceRules} onChange={(event) => setReferenceRules(event.target.value)} rows={7} spellCheck={false} /></label>
              <div className="verification-reference-form__actions">
                <button type="submit" disabled={busy}>{busy ? <LoaderCircle className="verification-spin" aria-hidden="true" /> : editingReferenceId ? <Check aria-hidden="true" /> : <Plus aria-hidden="true" />}{editingReferenceId ? "Save reference" : "Create reference"}</button>
                <small>Rules are validated by type. Reference checks are advisory and never modify curriculum data.</small>
              </div>
            </form>
          ) : <p className="verification-reference-readonly">Only admins and curriculum committee members can create or edit governed references.</p>}
        </div>
      </details>

      {report && findings.length > 0 ? (
        <section className="verification-report" aria-label="Grouped verification report">
          <div className="verification-report__heading">
            <div><span className="verification-label">GROUPED REPORT</span><h2>{report.total_findings} findings by {groupBy.replaceAll("_", " ")}</h2></div>
            <label>Group by<select value={groupBy} onChange={(event) => setGroupBy(event.target.value as typeof groupBy)}><option value="category">Category</option><option value="severity">Severity</option><option value="review_status">Review status</option></select></label>
          </div>
          <div className="verification-report__counts">
            <div><span>By category</span>{Object.entries(report.counts_by_category).map(([key, value]) => <small key={key}>{key.replaceAll("_", " ")} <b>{value}</b></small>)}</div>
            <div><span>By severity</span>{Object.entries(report.counts_by_severity).map(([key, value]) => <small key={key}>{key} <b>{value}</b></small>)}</div>
            <div><span>By review</span>{Object.entries(report.counts_by_review_status).map(([key, value]) => <small key={key}>{key.replaceAll("_", " ")} <b>{value}</b></small>)}</div>
          </div>
          <div className="verification-report__groups">
            {visibleReportGroups.length ? visibleReportGroups.map((group) => <details key={group.key}><summary><strong>{group.key.replaceAll("_", " ")}</strong><span>{group.findings.length}</span></summary><ul>{group.findings.map((finding) => <li key={finding.id}><span className={`verification-severity verification-severity--${finding.severity.toLowerCase()}`}>{finding.severity}</span><button type="button" onClick={() => { setReviewingId(finding.id); setReviewComment(finding.review_comments ?? ""); document.getElementById(`finding-${finding.id}`)?.scrollIntoView({ behavior: "smooth", block: "center" }); }}>{finding.title}</button></li>)}</ul></details>) : <p className="verification-report__empty">No findings match the current filters.</p>}
          </div>
        </section>
      ) : null}

      {runs.length > 0 ? (
        <div className="verification-filter-row">
          <div><h2>Findings</h2><span>{visibleFindings.length} shown of {findings.length}</span></div>
          <label>Category<select value={category} onChange={(event) => setCategory(event.target.value)}><option value="ALL">All categories</option>{Array.from(new Set(findings.map((finding) => finding.category))).sort().map((item) => <option key={item}>{item}</option>)}</select></label>
          <label>Severity<select value={severity} onChange={(event) => setSeverity(event.target.value)}><option value="ALL">All severities</option>{SEVERITIES.filter((item) => findings.some((finding) => finding.severity === item)).map((item) => <option key={item}>{item}</option>)}</select></label>
          <label>Review status<select value={reviewStatus} onChange={(event) => setReviewStatus(event.target.value)}><option value="ALL">All statuses</option>{Array.from(new Set(findings.map((finding) => finding.review_status))).sort().map((item) => <option key={item}>{item}</option>)}</select></label>
        </div>
      ) : null}

      {runs.length === 0 && curricula.length > 0 ? (
        <section className="verification-empty"><Play aria-hidden="true" /><h2>No verification runs yet</h2><p>Select a curriculum version and run checks to create the first report.</p></section>
      ) : null}
      {runs.length > 0 && findings.length === 0 ? (
        <section className="verification-empty verification-empty--passed"><Check aria-hidden="true" /><h2>No findings in this run</h2><p>The current prerequisite, content, structure, outcome, and reference checks did not identify issues in this curriculum version.</p></section>
      ) : null}

      <section className="verification-findings" aria-label="Verification findings">
        {visibleFindings.map((finding) => (
          <article className="verification-finding" id={`finding-${finding.id}`} key={finding.id}>
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
