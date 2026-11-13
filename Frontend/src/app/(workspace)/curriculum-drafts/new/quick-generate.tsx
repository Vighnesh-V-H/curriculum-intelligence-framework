"use client";

import { useEffect, useState } from "react";
import type { ChangeEvent, FormEvent } from "react";
import { useRouter } from "next/navigation";
import { ApiError, api } from "@/lib/api";
import type { CourseType, CurriculumDraft, Program } from "@/lib/api";
import { Spinner } from "@/components/ui/spinner";

const ALLOWED_EXTENSIONS = new Set([".pdf", ".docx", ".txt", ".md", ".csv"]);
const MAX_FILE_BYTES = 20 * 1024 * 1024;
const MAX_FILES = 5;

function courseTypeFor(category: string, types: CourseType[]): string {
  const normalized = category.trim().toLowerCase();
  const exact = types.find((type) => type.code.toLowerCase() === normalized);
  const partial = types.find((type) => normalized.includes(type.code.toLowerCase()) || type.name.toLowerCase().includes(normalized));
  const core = types.find((type) => type.code.toUpperCase() === "CORE");
  return (exact ?? partial ?? core ?? (types.length === 1 ? types[0] : undefined))?.code ?? "";
}

function academicYearFor(date: Date): string {
  const year = date.getFullYear();
  const firstYear = date.getMonth() >= 6 ? year : year - 1;
  return `${firstYear}-${String(firstYear + 1).slice(-2)}`;
}

export function QuickGenerateCurriculum() {
  const router = useRouter();
  const [programs, setPrograms] = useState<Program[]>([]);
  const [courseTypes, setCourseTypes] = useState<CourseType[]>([]);
  const [files, setFiles] = useState<File[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedProgramId, setSelectedProgramId] = useState("");
  const [busy, setBusy] = useState(false);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!busy) return;
    const timer = window.setInterval(() => setElapsedSeconds((seconds) => seconds + 1), 1000);
    return () => window.clearInterval(timer);
  }, [busy]);

  useEffect(() => {
    let cancelled = false;
    Promise.all([api.listPrograms(), api.listCourseTypes()])
      .then(([programRows, typeRows]) => {
        if (cancelled) return;
        setPrograms(programRows);
        setCourseTypes(typeRows);
      })
      .catch((caught) => {
        if (!cancelled) setError(caught instanceof ApiError ? caught.message : "Could not load programs.");
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  function handleFilesChanged(event: ChangeEvent<HTMLInputElement>) {
    const selected = Array.from(event.currentTarget.files ?? []);
    if (selected.length > MAX_FILES) {
      setError(`Choose no more than ${MAX_FILES} documents.`);
      event.currentTarget.value = "";
      return;
    }
    for (const file of selected) {
      const extension = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
      if (!ALLOWED_EXTENSIONS.has(extension)) {
        setError(`${file.name} is not a supported document type.`);
        event.currentTarget.value = "";
        return;
      }
      if (!file.size) {
        setError(`${file.name} is empty.`);
        event.currentTarget.value = "";
        return;
      }
      if (file.size > MAX_FILE_BYTES) {
        setError(`${file.name} is larger than 20 MB.`);
        event.currentTarget.value = "";
        return;
      }
    }
    setFiles(selected);
    setError("");
  }

  async function generate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedProgramId || !files.length || busy) return;
    const program = programs.find((item) => item.id === selectedProgramId);
    if (!program) return;
    setElapsedSeconds(0);
    setBusy(true);
    setError("");
    try {
      const now = new Date();
      const academicYear = academicYearFor(now);
      const regulation = String(now.getFullYear());
      const generated = await api.generateCurriculumDraft(files);

      const categories = [...new Set(generated.semesters.flatMap((semester) => semester.courses.map((course) => course.category.trim().toLowerCase()).filter(Boolean)))];
      const courseTypeCodes = Object.fromEntries(categories.map((category) => [category, courseTypeFor(category, courseTypes)]));
      const unresolved = categories.filter((category) => !courseTypeCodes[category]);
      if (unresolved.length) throw new Error(`No course type is configured for: ${unresolved.join(", ")}.`);

      const normalizedDraft: CurriculumDraft = {
        ...generated,
        program: {
          ...generated.program,
          name: program.name,
          degree: program.degree_type,
          duration_years: program.duration_years,
        },
        semesters: generated.semesters.map((semester) => ({
          ...semester,
          courses: semester.courses.map((course) => ({
            ...course,
            category: course.category.trim() || "General",
            credits: course.credits && course.credits > 0 && course.credits <= 30 ? course.credits : 3,
          })),
        })),
      };
      const saved = await api.saveCurriculumDraft({
        program_id: program.id,
        academic_year: academicYear,
        regulation,
        title: program.name,
        course_type_codes: courseTypeCodes,
        credits_by_course_code: {},
        draft: normalizedDraft,
      });
      router.replace(`/curricula/${encodeURIComponent(saved.id)}`);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : caught instanceof Error ? caught.message : "Could not create this curriculum. Check the selected program and documents, then try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="quick-generate-page">
      <form className="quick-generate-panel" aria-labelledby="quick-generate-title" onSubmit={generate}>
        <h1 id="quick-generate-title">Generate curriculum</h1>
        <label htmlFor="quick-generate-program">Program</label>
        <select
          id="quick-generate-program"
          value={selectedProgramId}
          disabled={loading || busy || !programs.length}
          onChange={(event) => { setSelectedProgramId(event.target.value); setError(""); }}
        >
          <option value="" disabled>{loading ? "Loading programs…" : programs.length ? "Select a program" : "No programs available"}</option>
          {programs.map((program) => <option key={program.id} value={program.id}>{program.code} · {program.name}</option>)}
        </select>
        <label htmlFor="quick-generate-files">Reference documents</label>
        <input id="quick-generate-files" type="file" accept=".pdf,.docx,.txt,.md,.csv" multiple disabled={loading || busy} onChange={handleFilesChanged} />
        <p className="quick-generate-hint">Upload 1–5 files (PDF, DOCX, TXT, MD, or CSV; up to 20 MB each).</p>
        {files.length > 0 && <p className="quick-generate-files">{files.map((file) => file.name).join(" · ")}</p>}
        {error && <p className="quick-generate-error" role="alert">{error}</p>}
        {!loading && !programs.length && !error && <p className="quick-generate-error">Create a program before generating a curriculum.</p>}
        <button className="quick-generate-submit" type="submit" disabled={loading || busy || !programs.length || !selectedProgramId || !files.length}>
          {busy ? <><Spinner /> Creating curriculum…</> : "Generate curriculum"}
        </button>
        {busy && <div className="quick-generate-progress" role="status" aria-live="polite"><strong>Creating and saving your curriculum…</strong><span>{elapsedSeconds < 20 ? "This may take a minute." : "The AI service is taking longer than usual. Please keep this page open; an error will appear if it cannot finish."}</span></div>}
      </form>
    </main>
  );
}
