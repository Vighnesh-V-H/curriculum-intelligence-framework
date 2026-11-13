"use client";

import "./draft-save.css";
import { useEffect, useRef, useState } from "react";
import type { ChangeEvent, DragEvent, FormEvent } from "react";
import Link from "next/link";
import {
  ArrowDownToLine,
  ArrowLeft,
  ArrowRight,
  BookOpen,
  Check,
  FileText,
  GraduationCap,
  Layers3,
  Sparkles,
  Upload,
  X,
} from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ApiError, api } from "@/lib/api";
import type { CourseType, Curriculum, CurriculumDraft, DraftCourse, DraftMapping, DraftOutcome, DraftSemester, Program } from "@/lib/api";

const ALLOWED_EXTENSIONS = [".pdf", ".docx", ".txt", ".md", ".csv"];
const MAX_FILE_MB = 20;
const MAX_FILES = 5;
const DEFAULT_DRAFT_CREDITS = 3;

type DraftView = "roadmap" | "outcomes";

type DraftMetadata = {
  program_id: string;
  academic_year: string;
  regulation: string;
  title: string;
};

type BusyPhase = "idle" | "generating" | "saving";

function fileExtension(filename: string): string {
  const dot = filename.lastIndexOf(".");
  return dot <= 0 ? "" : filename.slice(dot).toLowerCase();
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function validateFiles(files: File[]): string | null {
  if (files.length > MAX_FILES) return `Choose no more than ${MAX_FILES} files.`;
  for (const file of files) {
    if (!ALLOWED_EXTENSIONS.includes(fileExtension(file.name))) {
      return `${file.name} is not a supported file type.`;
    }
    if (file.size === 0) return `${file.name} is empty.`;
    if (file.size > MAX_FILE_MB * 1024 * 1024) {
      return `${file.name} is larger than ${MAX_FILE_MB} MB.`;
    }
  }
  return null;
}

function countCourses(semesters: DraftSemester[]): number {
  return semesters.reduce((total, semester) => total + semester.courses.length, 0);
}

function courseOutcomeRows(semesters: DraftSemester[]) {
  return semesters.flatMap((semester) =>
    semester.courses.flatMap((course) =>
      course.outcomes.map((outcome) => ({
        courseCode: course.code,
        courseTitle: course.title,
        outcomeCode: outcome.code,
        statement: outcome.statement,
      })),
    ),
  );
}

function downloadDraft(draft: CurriculumDraft): void {
  const file = new Blob([JSON.stringify(draft, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(file);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "curriculum-draft.json";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function draftCategories(draft: CurriculumDraft): string[] {
  return [
    ...new Set(
      draft.semesters.flatMap((semester) =>
        semester.courses
          .map((course) => course.category.trim().toLowerCase())
          .filter(Boolean),
      ),
    ),
  ];
}

function matchCourseType(category: string, courseTypes: CourseType[]): string {
  const exact = courseTypes.find((type) => type.code.toLowerCase() === category);
  const partial = courseTypes.find(
    (type) =>
      category.includes(type.code.toLowerCase())
      || type.name.toLowerCase().includes(category),
  );
  const core = courseTypes.find((type) => type.code.toUpperCase() === "CORE");
  const only = courseTypes.length === 1 ? courseTypes[0] : undefined;
  return (exact ?? partial ?? core ?? only)?.code ?? "";
}

function courseTypeDefaults(
  draft: CurriculumDraft,
  courseTypes: CourseType[],
): Record<string, string> {
  return Object.fromEntries(
    draftCategories(draft).map((category) => [
      category,
      matchCourseType(category, courseTypes),
    ]),
  );
}

function applyDefaultCredits(draft: CurriculumDraft): {
  draft: CurriculumDraft;
  defaulted: string[];
} {
  const defaulted: string[] = [];
  let changed = false;
  const semesters = draft.semesters.map((semester) => ({
    ...semester,
    courses: semester.courses.map((course) => {
      const category = course.category.trim() || "General";
      const hasValidCredits = course.credits !== null
        && course.credits > 0
        && course.credits <= 30;
      if (hasValidCredits && category === course.category) return course;
      changed = true;
      if (!hasValidCredits) defaulted.push(course.code);
      return {
        ...course,
        category,
        credits: hasValidCredits ? course.credits : DEFAULT_DRAFT_CREDITS,
      };
    }),
  }));
  return {
    draft: changed ? { ...draft, semesters } : draft,
    defaulted,
  };
}

function formatSavedDraftDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function draftRows(rows: Curriculum[]): Curriculum[] {
  return rows
    .filter((row) => row.latest_version?.status === "DRAFT")
    .sort((left, right) => Date.parse(right.updated_at) - Date.parse(left.updated_at));
}

function CourseEntry({
  course,
  editable,
  onChange,
}: {
  course: DraftCourse;
  editable: boolean;
  onChange: (patch: Partial<DraftCourse>) => void;
}) {
  return (
    <article className={`draft-course${editable ? " is-editing" : ""}`}>
      <div className="draft-course__heading">
        <Badge variant="outline">{course.code}</Badge>
        <div className="draft-course__name">
          {editable ? (
            <>
              <label>
                Course title
                <input
                  value={course.title}
                  onChange={(event) => onChange({ title: event.target.value })}
                />
              </label>
              <label>
                Summary
                <textarea
                  rows={2}
                  value={course.summary}
                  onChange={(event) => onChange({ summary: event.target.value })}
                />
              </label>
            </>
          ) : (
            <><h3>{course.title}</h3><p>{course.summary}</p></>
          )}
        </div>
        <div className="draft-course__meta">
          {editable ? (
            <>
              <label>
                Category
                <input
                  value={course.category}
                  onChange={(event) => onChange({ category: event.target.value })}
                />
              </label>
              <label>
                Credits
                <input
                  type="number"
                  min="1"
                  max="30"
                  step="1"
                  value={course.credits ?? ""}
                  onChange={(event) =>
                    onChange({ credits: event.target.value ? Number(event.target.value) : null })
                  }
                />
              </label>
            </>
          ) : (
            <>{course.credits !== null ? <span>{course.credits} credits</span> : null}{course.category ? <span>{course.category}</span> : null}</>
          )}
        </div>
      </div>
      <div className="draft-course__outcomes">
        <p>Course outcomes</p>
        <ul>
          {course.outcomes.map((outcome, index) => (
            <li key={`${course.code}-${index}`}>
              {editable ? (
                <>
                  <span className="draft-course__outcome-code">{outcome.code}</span>
                  <textarea
                    aria-label={`Outcome statement ${index + 1}`}
                    rows={2}
                    value={outcome.statement}
                    onChange={(event) => onChange({
                      outcomes: course.outcomes.map((item, itemIndex) =>
                        itemIndex === index ? { ...item, statement: event.target.value } : item,
                      ),
                    })}
                  />
                </>
              ) : (
                <><span>{outcome.code}</span><p>{outcome.statement}</p></>
              )}
            </li>
          ))}
        </ul>
      </div>
    </article>
  );
}

function SavedDraftsList({ refreshKey = 0 }: { refreshKey?: number }) {
  const [drafts, setDrafts] = useState<Curriculum[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");

  useEffect(() => {
    let cancelled = false;
    api.listCurricula()
      .then((rows) => {
        if (cancelled) return;
        setDrafts(draftRows(rows));
        setLoadError("");
      })
      .catch((caught) => {
        if (!cancelled) {
          setLoadError(
            caught instanceof ApiError
              ? caught.message
              : "Could not load saved drafts.",
          );
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [refreshKey]);

  return (
    <section className="draft-saved" aria-labelledby="draft-saved-title">
      <header className="draft-saved__header">
        <div>
          <p><BookOpen aria-hidden="true" /> Curriculum workspace</p>
          <h2 id="draft-saved-title">Saved drafts</h2>
          <span>Curricula whose latest version is still a draft, newest first.</span>
        </div>
        {!loading && !loadError ? (
          <Badge variant="outline">
            {drafts.length} {drafts.length === 1 ? "draft" : "drafts"}
          </Badge>
        ) : null}
      </header>
      {loading ? (
        <div className="draft-saved__status" role="status">
          <Spinner />
          <span>Loading saved drafts…</span>
        </div>
      ) : null}
      {loadError ? (
        <p className="draft-save__error" role="alert">{loadError}</p>
      ) : null}
      {!loading && !loadError && drafts.length === 0 ? (
        <p className="draft-empty-state">
          No saved drafts yet. Generate a curriculum and it will appear here.
        </p>
      ) : null}
      {!loading && !loadError && drafts.length > 0 ? (
        <ul className="draft-saved__list">
          {drafts.map((draft) => (
            <li key={draft.id}>
              <div className="draft-saved__identity">
                <span>{draft.program_code} · {draft.program_name}</span>
                <strong>{draft.title ?? `${draft.program_name} curriculum`}</strong>
                <p>{draft.academic_year} · Regulation {draft.regulation}</p>
              </div>
              <div className="draft-saved__side">
                <div className="draft-saved__badges">
                  <Badge variant="secondary">Draft</Badge>
                  <span>v{draft.latest_version?.version_label ?? "1.0"}</span>
                </div>
                <small>Updated {formatSavedDraftDate(draft.updated_at)}</small>
                <Link href={`/curricula?curriculum=${draft.id}`}>
                  Open workspace
                  <ArrowRight aria-hidden="true" />
                </Link>
              </div>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}

function DraftResults({
  draft,
  metadata,
  initialSavedCurriculumId,
  initialSaveError,
  defaultedCredits,
  onStartOver,
}: {
  draft: CurriculumDraft;
  metadata: DraftMetadata;
  initialSavedCurriculumId: string;
  initialSaveError: string;
  defaultedCredits: string[];
  onStartOver: () => void;
}) {
  const [view, setView] = useState<DraftView>("roadmap");
  const [workingDraft, setWorkingDraft] = useState(draft);
  const [editing, setEditing] = useState(false);
  const [programs, setPrograms] = useState<Program[]>([]);
  const [courseTypes, setCourseTypes] = useState<CourseType[]>([]);
  const [courseTypeCodes, setCourseTypeCodes] = useState<Record<string, string>>({});
  const [saveBusy, setSaveBusy] = useState(false);
  const [saveError, setSaveError] = useState(initialSaveError);
  const [optionsError, setOptionsError] = useState("");
  const [savedCurriculumId, setSavedCurriculumId] = useState(initialSavedCurriculumId);
  const [activeMetadata, setActiveMetadata] = useState(metadata);
  const [savedDraftsRefreshKey, setSavedDraftsRefreshKey] = useState(0);
  const [saveProgramId, setSaveProgramId] = useState(metadata.program_id);
  const categories = draftCategories(workingDraft);
  const missingCreditCourses = workingDraft.semesters
    .flatMap((semester) => semester.courses)
    .filter((course) => course.credits === null);

  function updateCourse(semesterNumber: number, courseCode: string, patch: Partial<DraftCourse>) {
    setWorkingDraft((current) => ({
      ...current,
      semesters: current.semesters.map((semester) => {
        if (semester.semester_number !== semesterNumber) return semester;
        return {
          ...semester,
          courses: semester.courses.map((course) =>
            course.code === courseCode ? { ...course, ...patch } : course,
          ),
        };
      }),
    }));
  }

  function updateSemester(semesterNumber: number, patch: Partial<DraftSemester>) {
    setWorkingDraft((current) => ({
      ...current,
      semesters: current.semesters.map((semester) =>
        semester.semester_number === semesterNumber ? { ...semester, ...patch } : semester,
      ),
    }));
  }

  function updateDefinition(kind: "peos" | "pos", index: number, patch: Partial<DraftOutcome>) {
    setWorkingDraft((current) => ({
      ...current,
      [kind]: current[kind].map((definition, definitionIndex) =>
        definitionIndex === index ? { ...definition, ...patch } : definition,
      ),
    }));
  }

  function updateMapping(
    courseCode: string,
    outcomeCode: string,
    programOutcomeCode: string,
    level: number,
  ) {
    setWorkingDraft((current) => {
      const matches = (mapping: DraftMapping) =>
        mapping.course_code.toUpperCase() === courseCode.toUpperCase()
        && mapping.course_outcome_code.toUpperCase() === outcomeCode.toUpperCase()
        && mapping.program_outcome_code.toUpperCase() === programOutcomeCode.toUpperCase();
      const present = current.mappings.some(matches);
      const typedLevel = level as 1 | 2 | 3;
      const mappings = level === 0
        ? current.mappings.filter((mapping) => !matches(mapping))
        : present
          ? current.mappings.map((mapping) =>
            matches(mapping) ? { ...mapping, level: typedLevel } : mapping,
          )
          : [...current.mappings, {
            course_code: courseCode,
            course_outcome_code: outcomeCode,
            program_outcome_code: programOutcomeCode,
            level: typedLevel,
          }];
      return { ...current, mappings };
    });
  }

  useEffect(() => {
    let cancelled = false;
    Promise.all([api.listPrograms(), api.listCourseTypes()])
      .then(([programRows, typeRows]) => {
        if (cancelled) return;
        setPrograms(programRows);
        setCourseTypes(typeRows);
        setCourseTypeCodes(courseTypeDefaults(workingDraft, typeRows));
      })
      .catch((caught) => setOptionsError(caught instanceof ApiError ? caught.message : "Could not load programs and course types."));
    return () => { cancelled = true; };
  // Seed defaults from the generated categories; edited categories require a new choice.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function saveDraft(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const credits = Object.fromEntries(missingCreditCourses.map((course) => [
      course.code.toUpperCase(), Number(form.get(`credits:${course.code}`)),
    ]));
    const nextMetadata: DraftMetadata = {
      program_id: String(form.get("program_id")),
      academic_year: String(form.get("academic_year")).trim(),
      regulation: String(form.get("regulation")).trim(),
      title: String(form.get("title") || "").trim(),
    };
    setSaveBusy(true); setSaveError("");
    try {
      const saved = await api.saveCurriculumDraft({
        ...nextMetadata,
        title: nextMetadata.title || null,
        course_type_codes: courseTypeCodes,
        credits_by_course_code: credits,
        draft: workingDraft,
      });
      setActiveMetadata(nextMetadata);
      setSavedCurriculumId(saved.id);
      setEditing(false);
      setSavedDraftsRefreshKey((current) => current + 1);
    } catch (caught) {
      setSaveError(caught instanceof ApiError ? caught.message : "Could not save the curriculum draft.");
    } finally { setSaveBusy(false); }
  }
  const [selectedSemester, setSelectedSemester] = useState(
    workingDraft.semesters[0]?.semester_number ?? 1,
  );
  const selected =
    workingDraft.semesters.find((semester) => semester.semester_number === selectedSemester) ??
    workingDraft.semesters[0];
  const outcomes = courseOutcomeRows(workingDraft.semesters);
  const mappedOutcomes = new Set(
    workingDraft.mappings.map(
      (mapping) =>
        `${mapping.course_code.toUpperCase()}|${mapping.course_outcome_code.toUpperCase()}`,
    ),
  );
  const mappedCount = outcomes.filter((outcome) =>
    mappedOutcomes.has(`${outcome.courseCode.toUpperCase()}|${outcome.outcomeCode.toUpperCase()}`),
  ).length;
  const coverage = outcomes.length === 0 ? 0 : Math.round((mappedCount / outcomes.length) * 100);
  const mappingLevels = new Map(
    workingDraft.mappings.map((mapping) => [
      `${mapping.course_code.toUpperCase()}|${mapping.course_outcome_code.toUpperCase()}|${mapping.program_outcome_code.toUpperCase()}`,
      mapping.level,
    ]),
  );
  const programOutcomeCodes = workingDraft.pos.map((outcome) => outcome.code.toUpperCase());
  const hasRequiredText = Boolean(workingDraft.program.summary.trim())
    && workingDraft.semesters.every((semester) => Boolean(semester.semester_name.trim() && semester.focus.trim())
      && semester.courses.every((course) => Boolean(course.title.trim() && course.category.trim() && course.summary.trim())
        && course.outcomes.length > 0 && course.outcomes.every((outcome) => Boolean(outcome.code.trim() && outcome.statement.trim()))))
    && [...workingDraft.peos, ...workingDraft.pos].every((outcome) => Boolean(outcome.code.trim() && outcome.statement.trim()));
  const hasValidCredits = workingDraft.semesters.every((semester) => semester.courses.every(
    (course) => course.credits === null || (course.credits > 0 && course.credits <= 30),
  ));
  const canSave = coverage === 100 && hasRequiredText && hasValidCredits
    && categories.every((category) => Boolean(courseTypeCodes[category]));

  return (
    <div className="draft-results">
      <div className="draft-results__toolbar">
        <Link href="/dashboard" className="draft-back-link">
          <ArrowLeft aria-hidden="true" />
          Workspace overview
        </Link>
        <div className="draft-results__actions">
          <Button variant="outline" onClick={() => downloadDraft(workingDraft)}>
            <ArrowDownToLine data-icon="inline-start" aria-hidden="true" />
            Download JSON
          </Button>
          <Button variant="outline" aria-pressed={editing} disabled={Boolean(savedCurriculumId)} onClick={() => setEditing((current) => !current)}>
            {editing ? "Finish editing" : "Edit generated content"}
          </Button>
          <Button variant="secondary" onClick={onStartOver}>
            Start another draft
            <ArrowRight data-icon="inline-end" aria-hidden="true" />
          </Button>
        </div>
      </div>

      {editing && <p className="draft-editing-note" role="status">Changes apply to this draft. Review mappings and required fields before saving.</p>}
      {defaultedCredits.length > 0 ? (
        <p className="draft-default-note" role="note">
          No usable credit value was generated for {defaultedCredits.join(", ")}; {DEFAULT_DRAFT_CREDITS} credits were applied automatically.
        </p>
      ) : null}
      <header className="draft-results__intro">
        <div className="draft-results__eyebrow">
          <Badge variant="secondary">
            {savedCurriculumId ? (
              <><Check data-icon="inline-start" aria-hidden="true" /> Saved as draft</>
            ) : (
              <><FileText data-icon="inline-start" aria-hidden="true" /> Not saved yet</>
            )}
          </Badge>
          <span>{savedCurriculumId ? "Generated and saved curriculum draft" : "Generated curriculum draft"}</span>
        </div>
        <div className="draft-results__title-row">
          <div>
            <h1>{workingDraft.program.name ?? "Curriculum draft"}</h1>
            {editing ? (
              <label className="draft-program-summary">Program summary<textarea rows={3} value={workingDraft.program.summary} onChange={(event) => setWorkingDraft((current) => ({ ...current, program: { ...current.program, summary: event.target.value } }))} /></label>
            ) : <p>{workingDraft.program.summary}</p>}
          </div>
          <div className="draft-results__program-meta">
            {activeMetadata.academic_year ? <span>{activeMetadata.academic_year}</span> : null}
            {activeMetadata.regulation ? <span>{activeMetadata.regulation}</span> : null}
            {workingDraft.program.degree ? <span>{workingDraft.program.degree}</span> : null}
            {workingDraft.program.duration_years ? (
              <span>{workingDraft.program.duration_years} years</span>
            ) : null}
          </div>
        </div>
      </header>

      <dl className="draft-summary" aria-label="Draft summary">
        <div>
          <dt>Semesters</dt>
          <dd>{workingDraft.semesters.length}</dd>
        </div>
        <div>
          <dt>Courses</dt>
          <dd>{countCourses(workingDraft.semesters)}</dd>
        </div>
        <div>
          <dt>Program outcomes</dt>
          <dd>{workingDraft.pos.length}</dd>
        </div>
        <div>
          <dt>Mapped course outcomes</dt>
          <dd>{coverage}%</dd>
        </div>
      </dl>

      <div className="draft-view-tabs" role="tablist" aria-label="Draft sections">
        <button
          type="button"
          role="tab"
          aria-selected={view === "roadmap"}
          className={view === "roadmap" ? "is-active" : ""}
          onClick={() => setView("roadmap")}
        >
          <Layers3 aria-hidden="true" />
          Curriculum roadmap
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={view === "outcomes"}
          className={view === "outcomes" ? "is-active" : ""}
          onClick={() => setView("outcomes")}
        >
          <GraduationCap aria-hidden="true" />
          Outcomes and mappings
        </button>
      </div>

      {view === "roadmap" ? (
        <section className="draft-roadmap" aria-label="Curriculum roadmap">
          <nav className="draft-semester-nav" aria-label="Choose a semester">
            <h2>Semester plan</h2>
            {workingDraft.semesters.map((semester) => (
              <button
                type="button"
                key={semester.semester_number}
                aria-current={
                  semester.semester_number === selected?.semester_number ? "step" : undefined
                }
                className={
                  semester.semester_number === selected?.semester_number ? "is-active" : ""
                }
                onClick={() => setSelectedSemester(semester.semester_number)}
              >
                <span className="draft-semester-nav__number">
                  {String(semester.semester_number).padStart(2, "0")}
                </span>
                <span className="draft-semester-nav__copy">
                  <strong>{semester.semester_name}</strong>
                  <small>{semester.courses.length} courses</small>
                </span>
                <ArrowRight aria-hidden="true" />
              </button>
            ))}
          </nav>

          {selected ? (
            <div className="draft-semester-detail">
              <header className="draft-semester-detail__header">
                <div>
                  <p>Semester {String(selected.semester_number).padStart(2, "0")}</p>
                  <h2>{selected.semester_name}</h2>
                </div>
                <Badge variant="outline">{selected.courses.length} courses</Badge>
                {editing ? (
                <div className="draft-semester-edit-fields">
                  <label>Semester name<input value={selected.semester_name} onChange={(event) => updateSemester(selected.semester_number, { semester_name: event.target.value })} /></label>
                  <label>Focus<textarea rows={2} value={selected.focus} onChange={(event) => updateSemester(selected.semester_number, { focus: event.target.value })} /></label>
                </div>
              ) : <span className="draft-semester-detail__focus">{selected.focus}</span>}
              </header>
              <div className="draft-course-list">
                {selected.courses.map((course) => (
                  <CourseEntry
                    key={course.code}
                    course={course}
                    editable={editing}
                    onChange={(patch) => updateCourse(selected.semester_number, course.code, patch)}
                  />
                ))}
              </div>
            </div>
          ) : (
            <p className="draft-empty-state">No semester data was returned.</p>
          )}
        </section>
      ) : (
        <section className="draft-outcomes" aria-label="Program outcomes and mappings">
          <div className="draft-outcome-groups">
            <section>
              <header>
                <p>Graduate objectives</p>
                <h2>Program educational objectives</h2>
              </header>
              {workingDraft.peos.length ? (
                <ol className="draft-outcome-list">
                  {workingDraft.peos.map((peo, index) => (
                    <li key={peo.code}>
                      <Badge variant="outline">{peo.code}</Badge>
                      {editing ? <textarea aria-label={`${peo.code} statement`} rows={3} value={peo.statement} onChange={(event) => updateDefinition("peos", index, { statement: event.target.value })} /> : <p>{peo.statement}</p>}
                    </li>
                  ))}
                </ol>
              ) : (
                <p className="draft-empty-state">No PEOs were returned.</p>
              )}
            </section>
            <section>
              <header>
                <p>Program outcomes</p>
                <h2>What graduates can do</h2>
              </header>
              {workingDraft.pos.length ? (
                <ol className="draft-outcome-list">
                  {workingDraft.pos.map((po, index) => (
                    <li key={po.code}>
                      <Badge variant="outline">{po.code}</Badge>
                      {editing ? <textarea aria-label={`${po.code} statement`} rows={3} value={po.statement} onChange={(event) => updateDefinition("pos", index, { statement: event.target.value })} /> : <p>{po.statement}</p>}
                    </li>
                  ))}
                </ol>
              ) : (
                <p className="draft-empty-state">No POs were returned.</p>
              )}
            </section>
          </div>

          <section className="draft-matrix">
            <header className="draft-matrix__header">
              <div>
                <p>Course outcome coverage</p>
                <h2>CO–PO mapping matrix</h2>
              </div>
              <span>1 low · 2 moderate · 3 high</span>
            </header>
            {outcomes.length && programOutcomeCodes.length ? (
              <Table className="draft-matrix__table">
                <TableCaption>
                  Mapping strength between each course outcome and program outcome.
                </TableCaption>
                <TableHeader>
                  <TableRow>
                    <TableHead>Course</TableHead>
                    <TableHead>Outcome</TableHead>
                    {programOutcomeCodes.map((code) => (
                      <TableHead key={code} className="draft-matrix__po-head">
                        {code}
                      </TableHead>
                    ))}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {outcomes.map((outcome) => (
                    <TableRow key={`${outcome.courseCode}|${outcome.outcomeCode}`}>
                      <TableCell>
                        <span className="draft-matrix__course-code">{outcome.courseCode}</span>
                        <span className="draft-matrix__course-title">{outcome.courseTitle}</span>
                      </TableCell>
                      <TableCell>
                        <span className="draft-matrix__co-code">{outcome.outcomeCode}</span>
                        <span className="draft-matrix__co-statement">{outcome.statement}</span>
                      </TableCell>
                      {programOutcomeCodes.map((code) => {
                        const level = mappingLevels.get(
                          `${outcome.courseCode.toUpperCase()}|${outcome.outcomeCode.toUpperCase()}|${code}`,
                        );
                        return (
                          <TableCell key={code} className="draft-matrix__level">
                            {editing ? (
                              <select aria-label={`Mapping ${outcome.courseCode} ${outcome.outcomeCode} to ${code}`} value={level ?? 0} onChange={(event) => updateMapping(outcome.courseCode, outcome.outcomeCode, code, Number(event.target.value))}>
                                <option value={0}>Unmapped</option><option value={1}>1 · Low</option><option value={2}>2 · Moderate</option><option value={3}>3 · High</option>
                              </select>
                            ) : level ?? "—"}
                          </TableCell>
                        );
                      })}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : (
              <p className="draft-empty-state">No outcome mappings were returned.</p>
            )}
          </section>
        </section>
      )}

      <section className="draft-save" aria-labelledby="draft-save-title">
        <div className="draft-save__intro">
          <p>{savedCurriculumId ? "Saved draft" : "Manual save required"}</p>
          <h2 id="draft-save-title">
            {savedCurriculumId ? "This curriculum is in the workspace" : "Save this curriculum draft"}
          </h2>
          <span>
            {savedCurriculumId
              ? `Stored as version 1.0 for ${activeMetadata.academic_year} · ${activeMetadata.regulation}. Nothing was approved or published.`
              : "The draft is still available in this preview. Review the metadata, assign course types, and save it manually."}
          </span>
        </div>
        {savedCurriculumId ? (
          <div className="draft-save__success" role="status">
            <strong>Curriculum draft saved to the database.</strong>
            <p>It is stored as version 1.0 in DRAFT status. Generated PEOs, POs, and mappings remain unapproved for academic review.</p>
            <Link href={`/curricula?curriculum=${savedCurriculumId}`}>Open curriculum workspace</Link>
          </div>
        ) : (
          <form className="draft-save__form" onSubmit={saveDraft}>
            {saveError && <p className="draft-save__error" role="alert">{saveError}</p>}
            {optionsError && <p className="draft-save__error" role="alert">{optionsError}</p>}
            <div className="draft-save__fields">
              <label>Program<select name="program_id" required value={saveProgramId} onChange={(event) => setSaveProgramId(event.target.value)}><option value="" disabled>Select an existing program</option>{programs.map((program) => <option key={program.id} value={program.id}>{program.code} · {program.name}</option>)}</select></label>
              <label>Academic year<input name="academic_year" required defaultValue={metadata.academic_year} placeholder="2026–2027" /></label>
              <label>Regulation<input name="regulation" required defaultValue={metadata.regulation} placeholder="R2026" /></label>
              <label>Curriculum title<input name="title" defaultValue={metadata.title || workingDraft.program.name || ""} /></label>
            </div>
            <div className="draft-save__categories">
              <h3>Map generated course categories</h3>
              {categories.map((category) => <label key={category}>{category}<select value={courseTypeCodes[category] ?? ""} onChange={(event) => setCourseTypeCodes((current) => ({ ...current, [category]: event.target.value }))} required><option value="" disabled>Select course type</option>{courseTypes.map((type) => <option key={type.code} value={type.code}>{type.name} ({type.code})</option>)}</select></label>)}
            </div>
            {missingCreditCourses.length > 0 && <div className="draft-save__credits"><h3>Credits not provided in the draft</h3>{missingCreditCourses.map((course) => <label key={course.code}>{course.code} · {course.title}<input name={`credits:${course.code}`} type="number" min="0.5" max="30" step="0.5" defaultValue="3" required /></label>)}</div>}
            <div className="draft-save__submit"><p>The save is all-or-nothing. Existing PEO/PO codes are versioned; curriculum and generated mappings stay in draft status.{!canSave ? " Keep every course outcome mapped and assign a type to each category." : ""}</p><Button type="submit" disabled={saveBusy || !programs.length || !courseTypes.length || !canSave}>{saveBusy ? <><Spinner data-icon="inline-start" /> Saving curriculum…</> : "Save as curriculum draft"}</Button></div>
            {!optionsError && !programs.length && <p className="draft-save__error">Create a program in the curriculum workspace before saving this draft.</p>}
          </form>
        )}
      </section>
      <p className="draft-results__note">
        {savedCurriculumId
          ? "This draft was saved automatically as version 1.0 in DRAFT status. Review it in the curriculum workspace; saving does not approve or publish the proposal."
          : "This draft is not in the database yet. Saving creates an editable draft and does not approve or publish the proposal."}
      </p>
      <SavedDraftsList refreshKey={savedDraftsRefreshKey} />
    </div>
  );
}

export default function NewCurriculumDraftPage() {
  const [files, setFiles] = useState<File[]>([]);
  const [topic, setTopic] = useState("");
  const [programs, setPrograms] = useState<Program[]>([]);
  const [courseTypes, setCourseTypes] = useState<CourseType[]>([]);
  const [optionsLoading, setOptionsLoading] = useState(true);
  const [optionsError, setOptionsError] = useState("");
  const [programId, setProgramId] = useState("");
  const [academicYear, setAcademicYear] = useState("");
  const [regulation, setRegulation] = useState("");
  const [title, setTitle] = useState("");
  const [draft, setDraft] = useState<CurriculumDraft | null>(null);
  const [draftMetadata, setDraftMetadata] = useState<DraftMetadata | null>(null);
  const [savedCurriculumId, setSavedCurriculumId] = useState("");
  const [autoSaveError, setAutoSaveError] = useState("");
  const [defaultedCredits, setDefaultedCredits] = useState<string[]>([]);
  const [busyPhase, setBusyPhase] = useState<BusyPhase>("idle");
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const busy = busyPhase !== "idle";

  useEffect(() => {
    let cancelled = false;
    Promise.all([api.listPrograms(), api.listCourseTypes()])
      .then(([programRows, typeRows]) => {
        if (cancelled) return;
        setPrograms(programRows);
        setCourseTypes(typeRows);
        setOptionsError("");
      })
      .catch((caught) => {
        if (cancelled) return;
        setOptionsError(
          caught instanceof ApiError
            ? caught.message
            : "Could not load programs and course types.",
        );
      })
      .finally(() => {
        if (!cancelled) setOptionsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  function acceptFiles(nextFiles: File[]) {
    const validationError = validateFiles(nextFiles);
    if (validationError && nextFiles.length > 0) {
      setError(validationError);
      return;
    }
    setFiles(nextFiles);
    setError(null);
  }

  function handleFilesChanged(event: ChangeEvent<HTMLInputElement>) {
    acceptFiles(Array.from(event.currentTarget.files ?? []));
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    acceptFiles(Array.from(event.dataTransfer.files));
  }

  function removeFile(indexToRemove: number) {
    setFiles((current) => current.filter((_, index) => index !== indexToRemove));
    setError(null);
    if (inputRef.current) inputRef.current.value = "";
  }

  function startOver() {
    setDraft(null);
    setDraftMetadata(null);
    setSavedCurriculumId("");
    setAutoSaveError("");
    setDefaultedCredits([]);
    setFiles([]);
    setTopic("");
    setBusyPhase("idle");
    setError(null);
    if (inputRef.current) inputRef.current.value = "";
  }

  async function handleGenerate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalizedTopic = topic.trim();
    if (!normalizedTopic && files.length === 0) {
      setError("Enter a curriculum topic or add at least one reference document.");
      return;
    }
    const validationError = validateFiles(files);
    if (validationError) {
      setError(validationError);
      return;
    }
    const selectedProgram = programs.find((program) => program.id === programId);
    if (!selectedProgram) {
      setError("Choose the program this curriculum belongs to.");
      return;
    }
    const normalizedYear = academicYear.trim();
    if (!normalizedYear) {
      setError("Enter the academic year for this curriculum.");
      return;
    }
    const normalizedRegulation = regulation.trim();
    if (!normalizedRegulation) {
      setError("Enter the regulation for this curriculum.");
      return;
    }
    if (!courseTypes.length) {
      setError("No active course types are configured, so generated courses cannot be saved.");
      return;
    }

    setBusyPhase("generating");
    setError(null);
    try {
      let generated: CurriculumDraft;
      try {
        generated = await api.generateCurriculumDraft(files, normalizedTopic);
      } catch (caught) {
        setError(
          caught instanceof ApiError
            ? caught.message
            : "The curriculum service could not be reached. Check the backend and try again.",
        );
        return;
      }

      const normalized = applyDefaultCredits(generated);
      const categories = draftCategories(normalized.draft);
      const typeCodes = courseTypeDefaults(normalized.draft, courseTypes);
      const unresolved = categories.filter((category) => !typeCodes[category]);
      const metadata: DraftMetadata = {
        program_id: selectedProgram.id,
        academic_year: normalizedYear,
        regulation: normalizedRegulation,
        title: title.trim(),
      };
      let savedId = "";
      let saveFailure = "";
      if (unresolved.length > 0) {
        saveFailure = `The draft was generated but not saved automatically because no course type matches: ${unresolved.join(", ")}. Choose a course type below and save manually.`;
      } else {
        setBusyPhase("saving");
        try {
          const saved = await api.saveCurriculumDraft({
            ...metadata,
            title: metadata.title || null,
            course_type_codes: typeCodes,
            credits_by_course_code: {},
            draft: normalized.draft,
          });
          savedId = saved.id;
        } catch (caught) {
          if (caught instanceof ApiError && caught.code === "curriculum_exists") {
            saveFailure = "The draft was generated but not saved automatically: a curriculum already exists for this program and regulation. Choose a different regulation below, or open the existing draft from the saved list.";
          } else {
            const detail = caught instanceof ApiError
              ? caught.message
              : "the curriculum service could not be reached.";
            saveFailure = `The draft was generated but not saved automatically: ${detail}`;
          }
        }
      }

      setDraft(normalized.draft);
      setDraftMetadata(metadata);
      setSavedCurriculumId(savedId);
      setAutoSaveError(saveFailure);
      setDefaultedCredits(normalized.defaulted);
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : "The curriculum draft could not be completed. Try again.",
      );
    } finally {
      setBusyPhase("idle");
    }
  }

  if (draft && draftMetadata) {
    return (
      <div className="draft-studio">
        <DraftResults
          draft={draft}
          metadata={draftMetadata}
          initialSavedCurriculumId={savedCurriculumId}
          initialSaveError={autoSaveError}
          defaultedCredits={defaultedCredits}
          onStartOver={startOver}
        />
      </div>
    );
  }

  const hasTopic = Boolean(topic.trim());
  const missingSource = !hasTopic && files.length === 0;
  const canSubmit = !busy
    && !missingSource
    && !optionsLoading
    && !optionsError
    && programs.length > 0
    && courseTypes.length > 0;
  let progressTitle = "Designing your curriculum";
  let progressDetail =
    "Turning your topic brief into a semester roadmap, course outcomes, and proposed mappings.";
  if (busyPhase === "saving") {
    progressTitle = "Saving your curriculum draft";
    progressDetail = `Creating curriculum version 1.0 for ${academicYear.trim() || "the selected year"} · ${regulation.trim() || "the selected regulation"} in DRAFT status.`;
  } else if (files.length > 0) {
    progressTitle = hasTopic ? "Reading your documents and brief" : "Reading your documents";
    progressDetail =
      "Extracting the source material and building the curriculum roadmap with its outcomes and mappings.";
  }

  return (
    <div className="draft-studio">
      <div className="draft-studio__toolbar">
        <Link href="/dashboard" className="draft-back-link">
          <ArrowLeft aria-hidden="true" />
          Workspace overview
        </Link>
        <Badge variant="outline">Draft studio</Badge>
      </div>

      <header className="draft-studio__intro">
        <p className="draft-eyebrow"><Sparkles aria-hidden="true" /> Curriculum design</p>
        <h1>Build a curriculum from a topic or your documents.</h1>
        <p>
          Describe what the program should cover, add reference documents if you have them, and
          generate a semester-by-semester roadmap, outcomes, and proposed mappings. The result is
          saved to the curriculum workspace automatically as an unapproved draft.
        </p>
      </header>

      <div className="draft-studio__workspace">
        <section className="draft-source-panel">
          <header className="draft-section-heading">
            <span>01</span>
            <div>
              <h2>Shape the curriculum</h2>
              <p>Set where the draft belongs, then start with a topic, source documents, or both.</p>
            </div>
          </header>

          <form onSubmit={handleGenerate}>
            <FieldGroup>
              <div className="draft-source-divider">
                <span>Curriculum details</span>
              </div>

              <div className="draft-metadata-grid">
                <Field className="draft-metadata-wide" data-invalid={Boolean(error) && !programId}>
                  <FieldLabel htmlFor="draft-program">Program</FieldLabel>
                  <select
                    id="draft-program"
                    className="draft-metadata-control"
                    value={programId}
                    onChange={(event) => {
                      setProgramId(event.target.value);
                      if (error) setError(null);
                    }}
                    disabled={busy || optionsLoading}
                    aria-invalid={Boolean(error) && !programId}
                    required
                  >
                    <option value="" disabled>
                      {optionsLoading ? "Loading programs…" : "Select an existing program"}
                    </option>
                    {programs.map((program) => (
                      <option key={program.id} value={program.id}>
                        {program.code} · {program.name}
                      </option>
                    ))}
                  </select>
                  <FieldDescription>
                    The saved curriculum is created for this program.
                  </FieldDescription>
                </Field>

                <Field data-invalid={Boolean(error) && !academicYear.trim()}>
                  <FieldLabel htmlFor="draft-academic-year">Academic year</FieldLabel>
                  <input
                    id="draft-academic-year"
                    className="draft-metadata-control"
                    value={academicYear}
                    onChange={(event) => {
                      setAcademicYear(event.target.value);
                      if (error) setError(null);
                    }}
                    placeholder="2026–2027"
                    disabled={busy}
                    aria-invalid={Boolean(error) && !academicYear.trim()}
                    required
                  />
                </Field>

                <Field data-invalid={Boolean(error) && !regulation.trim()}>
                  <FieldLabel htmlFor="draft-regulation">Regulation</FieldLabel>
                  <input
                    id="draft-regulation"
                    className="draft-metadata-control"
                    value={regulation}
                    onChange={(event) => {
                      setRegulation(event.target.value);
                      if (error) setError(null);
                    }}
                    placeholder="R2026"
                    disabled={busy}
                    aria-invalid={Boolean(error) && !regulation.trim()}
                    required
                  />
                </Field>

                <Field className="draft-metadata-wide">
                  <FieldLabel htmlFor="draft-title">Curriculum title (optional)</FieldLabel>
                  <input
                    id="draft-title"
                    className="draft-metadata-control"
                    value={title}
                    onChange={(event) => setTitle(event.target.value)}
                    placeholder="Uses the generated program name if left blank"
                    disabled={busy}
                  />
                </Field>
              </div>

              {optionsLoading ? (
                <p className="draft-options-status">
                  <Spinner />
                  Loading programs and course types…
                </p>
              ) : null}
              {optionsError ? (
                <p className="draft-options-error" role="alert">{optionsError}</p>
              ) : null}
              {!optionsLoading && !optionsError && !programs.length ? (
                <p className="draft-options-error" role="alert">
                  No programs are configured. <Link href="/curricula">Create a program in the curriculum workspace</Link> before generating a draft.
                </p>
              ) : null}
              {!optionsLoading && !optionsError && programs.length > 0 && !courseTypes.length ? (
                <p className="draft-options-error" role="alert">
                  No active course types are configured. Ask an administrator to add them before generating a draft.
                </p>
              ) : null}

              <div className="draft-source-divider">
                <span>Curriculum brief</span>
              </div>

              <Field data-invalid={Boolean(error) && missingSource}>
                <FieldLabel htmlFor="draft-topic">Curriculum topic or brief</FieldLabel>
                <textarea
                  id="draft-topic"
                  className="draft-topic-input"
                  rows={4}
                  maxLength={500}
                  value={topic}
                  onChange={(event) => {
                    setTopic(event.target.value);
                    if (error) setError(null);
                  }}
                  placeholder="e.g. B.Tech in Artificial Intelligence, 4 years, 8 semesters, with applied projects and industry exposure."
                  disabled={busy}
                  aria-invalid={Boolean(error) && missingSource}
                  aria-describedby="draft-topic-help"
                />
                <div className="draft-topic-meta">
                  <FieldDescription id="draft-topic-help">
                    Use this, the documents below, or both. Describe the program, degree, duration,
                    or focus; the LLM proposes the roadmap, course outcomes, PEOs, POs, and
                    mappings.
                  </FieldDescription>
                  <span aria-hidden="true">{topic.length}/500</span>
                </div>
              </Field>

              <div className="draft-source-divider">
                <span>Reference documents (optional)</span>
              </div>

              <Field data-invalid={Boolean(error)}>
                <FieldLabel htmlFor="draft-source-files">Add curriculum files</FieldLabel>
                <div
                  className={`draft-dropzone${dragging ? " is-dragging" : ""}`}
                  onDragOver={(event) => {
                    event.preventDefault();
                    setDragging(true);
                  }}
                  onDragLeave={(event) => {
                    if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
                      setDragging(false);
                    }
                  }}
                  onDrop={handleDrop}
                >
                  <Input
                    ref={inputRef}
                    id="draft-source-files"
                    type="file"
                    multiple
                    accept={ALLOWED_EXTENSIONS.join(",")}
                    onChange={handleFilesChanged}
                    disabled={busy}
                    aria-invalid={Boolean(error)}
                    aria-describedby="draft-file-help"
                    className="draft-file-input"
                  />
                  <Upload aria-hidden="true" className="draft-dropzone__icon" />
                  <p className="draft-dropzone__title">Drop documents here</p>
                  <p className="draft-dropzone__copy">or select files from your computer</p>
                  <Button
                    type="button"
                    variant="outline"
                    disabled={busy}
                    onClick={() => inputRef.current?.click()}
                  >
                    Browse files
                  </Button>
                </div>
                <FieldDescription id="draft-file-help">
                  PDF, DOCX, TXT, MD, or CSV · up to {MAX_FILES} files · {MAX_FILE_MB} MB per file.
                  Add files when you want the draft grounded in existing curriculum material.
                </FieldDescription>
              </Field>
            </FieldGroup>

            {files.length > 0 ? (
              <ul className="draft-file-list" aria-label="Selected files">
                {files.map((file, index) => (
                  <li key={`${file.name}-${file.size}-${file.lastModified}`}>
                    <FileText aria-hidden="true" />
                    <span className="draft-file-list__name">{file.name}</span>
                    <span className="draft-file-list__size">{formatBytes(file.size)}</span>
                    <button
                      type="button"
                      className="draft-file-list__remove"
                      onClick={() => removeFile(index)}
                      disabled={busy}
                      aria-label={`Remove ${file.name}`}
                    >
                      <X aria-hidden="true" />
                    </button>
                  </li>
                ))}
              </ul>
            ) : null}

            {error ? (
              <Alert variant="destructive" className="draft-error">
                <AlertTitle>Draft generation needs attention</AlertTitle>
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            ) : null}

            {busy ? (
              <div className="draft-progress" role="status" aria-live="polite">
                <Spinner />
                <div>
                  <strong>{progressTitle}</strong>
                  <p>
                    {progressDetail} Longer programs can take a little time.
                  </p>
                </div>
              </div>
            ) : null}

            <div className="draft-submit-row">
              <p>
                Generating saves version 1.0 automatically in DRAFT status. Missing credits default
                to {DEFAULT_DRAFT_CREDITS}. Nothing is approved or published.
              </p>
              <Button type="submit" size="lg" disabled={!canSubmit}>
                {busy ? (
                  <>
                    <Spinner data-icon="inline-start" />
                    {busyPhase === "saving" ? "Saving draft" : "Generating draft"}
                  </>
                ) : (
                  <>
                    <Sparkles data-icon="inline-start" />
                    Generate and save draft
                  </>
                )}
              </Button>
            </div>
          </form>
        </section>

        <aside className="draft-guide">
          <div className="draft-guide__label">THE WORKFLOW</div>
          <h2>One draft, saved and ready for academic review.</h2>
          <p className="draft-guide__intro">
            Generation writes the plan to the curriculum workspace as an unapproved draft. Your
            committee decides what belongs in the curriculum.
          </p>
          <ol className="draft-guide__steps">
            <li>
              <span>01</span>
              <div><strong>Semester roadmap</strong><p>Courses, credits, and learning focus.</p></div>
            </li>
            <li>
              <span>02</span>
              <div><strong>Course outcomes</strong><p>Clear outcomes attached to each course.</p></div>
            </li>
            <li>
              <span>03</span>
              <div><strong>Outcome mapping</strong><p>Proposed PEOs, POs, and CO–PO levels.</p></div>
            </li>
            <li>
              <span>04</span>
              <div><strong>Saved as a draft</strong><p>Version 1.0 is stored in DRAFT status for review.</p></div>
            </li>
          </ol>
          <div className="draft-guide__foot">
            <GraduationCap aria-hidden="true" />
            <p>Nothing is approved or published automatically. Review the saved draft in the curriculum workspace.</p>
          </div>
        </aside>
      </div>

      <SavedDraftsList />
    </div>
  );
}
