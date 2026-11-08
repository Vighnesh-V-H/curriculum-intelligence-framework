"use client";

import "./draft-save.css";
import { useEffect, useRef, useState } from "react";
import type { ChangeEvent, DragEvent, FormEvent } from "react";
import Link from "next/link";
import {
  ArrowDownToLine,
  ArrowLeft,
  ArrowRight,
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
import type { CourseType, CurriculumDraft, DraftCourse, DraftSemester, Program } from "@/lib/api";

const ALLOWED_EXTENSIONS = [".pdf", ".docx", ".txt", ".md", ".csv"];
const MAX_FILE_MB = 20;
const MAX_FILES = 5;

type DraftView = "roadmap" | "outcomes";

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
  if (files.length === 0) return "Choose at least one source document.";
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

function CourseEntry({ course }: { course: DraftCourse }) {
  return (
    <article className="draft-course">
      <div className="draft-course__heading">
        <Badge variant="outline">{course.code}</Badge>
        <div className="draft-course__name">
          <h3>{course.title}</h3>
          <p>{course.summary}</p>
        </div>
        <div className="draft-course__meta">
          {course.credits !== null ? <span>{course.credits} credits</span> : null}
          {course.category ? <span>{course.category}</span> : null}
        </div>
      </div>
      <div className="draft-course__outcomes">
        <p>Course outcomes</p>
        <ul>
          {course.outcomes.map((outcome) => (
            <li key={`${course.code}-${outcome.code}`}>
              <span>{outcome.code}</span>
              <p>{outcome.statement}</p>
            </li>
          ))}
        </ul>
      </div>
    </article>
  );
}

function DraftResults({
  draft,
  onStartOver,
}: {
  draft: CurriculumDraft;
  onStartOver: () => void;
}) {
  const [view, setView] = useState<DraftView>("roadmap");
  const [programs, setPrograms] = useState<Program[]>([]);
  const [courseTypes, setCourseTypes] = useState<CourseType[]>([]);
  const [courseTypeCodes, setCourseTypeCodes] = useState<Record<string, string>>({});
  const [saveBusy, setSaveBusy] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [savedCurriculumId, setSavedCurriculumId] = useState("");
  const categories = [...new Set(draft.semesters.flatMap((semester) => semester.courses.map((course) => course.category.trim().toLowerCase())))];
  const missingCreditCourses = draft.semesters.flatMap((semester) => semester.courses).filter((course) => course.credits === null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([api.listPrograms(), api.listCourseTypes()])
      .then(([programRows, typeRows]) => {
        if (cancelled) return;
        setPrograms(programRows);
        setCourseTypes(typeRows);
        const codes = Object.fromEntries(categories.map((category) => {
          const matched = typeRows.find((type) => type.code.toLowerCase() === category)
            ?? typeRows.find((type) => category.includes(type.code.toLowerCase()) || type.name.toLowerCase().includes(category))
            ?? typeRows.find((type) => type.code === "CORE");
          return [category, matched?.code ?? typeRows[0]?.code ?? ""];
        }));
        setCourseTypeCodes(codes);
      })
      .catch((caught) => setSaveError(caught instanceof ApiError ? caught.message : "Could not load programs and course types."));
    return () => { cancelled = true; };
  // Categories are immutable for this generated result.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function saveDraft(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const credits = Object.fromEntries(missingCreditCourses.map((course) => [
      course.code.toUpperCase(), Number(form.get(`credits:${course.code}`)),
    ]));
    setSaveBusy(true); setSaveError("");
    try {
      const saved = await api.saveCurriculumDraft({
        program_id: String(form.get("program_id")),
        academic_year: String(form.get("academic_year")),
        regulation: String(form.get("regulation")),
        title: String(form.get("title") || "") || null,
        course_type_codes: courseTypeCodes,
        credits_by_course_code: credits,
        draft,
      });
      setSavedCurriculumId(saved.id);
    } catch (caught) {
      setSaveError(caught instanceof ApiError ? caught.message : "Could not save the curriculum draft.");
    } finally { setSaveBusy(false); }
  }
  const [selectedSemester, setSelectedSemester] = useState(
    draft.semesters[0]?.semester_number ?? 1,
  );
  const selected =
    draft.semesters.find((semester) => semester.semester_number === selectedSemester) ??
    draft.semesters[0];
  const outcomes = courseOutcomeRows(draft.semesters);
  const mappedOutcomes = new Set(
    draft.mappings.map(
      (mapping) =>
        `${mapping.course_code.toUpperCase()}|${mapping.course_outcome_code.toUpperCase()}`,
    ),
  );
  const mappedCount = outcomes.filter((outcome) =>
    mappedOutcomes.has(`${outcome.courseCode.toUpperCase()}|${outcome.outcomeCode.toUpperCase()}`),
  ).length;
  const coverage = outcomes.length === 0 ? 0 : Math.round((mappedCount / outcomes.length) * 100);
  const mappingLevels = new Map(
    draft.mappings.map((mapping) => [
      `${mapping.course_code.toUpperCase()}|${mapping.course_outcome_code.toUpperCase()}|${mapping.program_outcome_code.toUpperCase()}`,
      mapping.level,
    ]),
  );
  const programOutcomeCodes = draft.pos.map((outcome) => outcome.code.toUpperCase());

  return (
    <div className="draft-results">
      <div className="draft-results__toolbar">
        <Link href="/dashboard" className="draft-back-link">
          <ArrowLeft aria-hidden="true" />
          Workspace overview
        </Link>
        <div className="draft-results__actions">
          <Button variant="outline" onClick={() => downloadDraft(draft)}>
            <ArrowDownToLine data-icon="inline-start" aria-hidden="true" />
            Download JSON
          </Button>
          <Button variant="secondary" onClick={onStartOver}>
            Start another draft
            <ArrowRight data-icon="inline-end" aria-hidden="true" />
          </Button>
        </div>
      </div>

      <header className="draft-results__intro">
        <div className="draft-results__eyebrow">
          <Badge variant="secondary">
            <Check data-icon="inline-start" aria-hidden="true" />
            Preview only
          </Badge>
          <span>Generated curriculum draft</span>
        </div>
        <div className="draft-results__title-row">
          <div>
            <h1>{draft.program.name ?? "Curriculum draft"}</h1>
            <p>{draft.program.summary}</p>
          </div>
          <div className="draft-results__program-meta">
            {draft.program.degree ? <span>{draft.program.degree}</span> : null}
            {draft.program.duration_years ? (
              <span>{draft.program.duration_years} years</span>
            ) : null}
          </div>
        </div>
      </header>

      <dl className="draft-summary" aria-label="Draft summary">
        <div>
          <dt>Semesters</dt>
          <dd>{draft.semesters.length}</dd>
        </div>
        <div>
          <dt>Courses</dt>
          <dd>{countCourses(draft.semesters)}</dd>
        </div>
        <div>
          <dt>Program outcomes</dt>
          <dd>{draft.pos.length}</dd>
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
            {draft.semesters.map((semester) => (
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
                <span className="draft-semester-detail__focus">{selected.focus}</span>
              </header>
              <div className="draft-course-list">
                {selected.courses.map((course) => (
                  <CourseEntry key={course.code} course={course} />
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
              {draft.peos.length ? (
                <ol className="draft-outcome-list">
                  {draft.peos.map((peo) => (
                    <li key={peo.code}>
                      <Badge variant="outline">{peo.code}</Badge>
                      <p>{peo.statement}</p>
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
              {draft.pos.length ? (
                <ol className="draft-outcome-list">
                  {draft.pos.map((po) => (
                    <li key={po.code}>
                      <Badge variant="outline">{po.code}</Badge>
                      <p>{po.statement}</p>
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
                            {level ?? "—"}
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
          <p>Reviewed draft</p>
          <h2 id="draft-save-title">Save this as a curriculum</h2>
          <span>Saving creates curriculum version 1.0 as a draft. Generated PEOs, POs, and mappings remain unapproved for academic review.</span>
        </div>
        {savedCurriculumId ? (
          <div className="draft-save__success" role="status">
            <strong>Curriculum draft saved.</strong>
            <p>It is stored as version 1.0 in draft status; nothing was approved or published.</p>
            <Link href="/curricula">Open curriculum workspace</Link>
          </div>
        ) : (
          <form className="draft-save__form" onSubmit={saveDraft}>
            <div className="draft-save__fields">
              <label>Program<select name="program_id" required defaultValue=""><option value="" disabled>Select an existing program</option>{programs.map((program) => <option key={program.id} value={program.id}>{program.code} · {program.name}</option>)}</select></label>
              <label>Academic year<input name="academic_year" required placeholder="2026–2027" /></label>
              <label>Regulation<input name="regulation" required placeholder="R2026" /></label>
              <label>Curriculum title<input name="title" defaultValue={draft.program.name ?? ""} /></label>
            </div>
            <div className="draft-save__categories">
              <h3>Map generated course categories</h3>
              {categories.map((category) => <label key={category}>{category}<select value={courseTypeCodes[category] ?? ""} onChange={(event) => setCourseTypeCodes((current) => ({ ...current, [category]: event.target.value }))} required><option value="" disabled>Select course type</option>{courseTypes.map((type) => <option key={type.code} value={type.code}>{type.name} ({type.code})</option>)}</select></label>)}
            </div>
            {missingCreditCourses.length > 0 && <div className="draft-save__credits"><h3>Credits not provided in the draft</h3>{missingCreditCourses.map((course) => <label key={course.code}>{course.code} · {course.title}<input name={`credits:${course.code}`} type="number" min="0.5" max="30" step="0.5" defaultValue="3" required /></label>)}</div>}
            {saveError && <p className="draft-save__error" role="alert">{saveError}</p>}
            <div className="draft-save__submit"><p>The save is all-or-nothing. Existing PEO/PO codes are versioned; curriculum and generated mappings stay in draft status.</p><Button type="submit" disabled={saveBusy || !programs.length || !courseTypes.length}>{saveBusy ? <><Spinner data-icon="inline-start" /> Saving curriculum…</> : "Save as curriculum draft"}</Button></div>
            {!programs.length && <p className="draft-save__error">Create a program in the curriculum workspace before saving this draft.</p>}
          </form>
        )}
      </section>
      <p className="draft-results__note">
        Review the generated curriculum carefully. Saving requires an explicit confirmation and creates an editable draft; it does not approve or publish the proposal.
      </p>
    </div>
  );
}

export default function NewCurriculumDraftPage() {
  const [files, setFiles] = useState<File[]>([]);
  const [draft, setDraft] = useState<CurriculumDraft | null>(null);
  const [busy, setBusy] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

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
    setFiles([]);
    setBusy(false);
    setError(null);
    if (inputRef.current) inputRef.current.value = "";
  }

  async function handleGenerate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const validationError = validateFiles(files);
    if (validationError) {
      setError(validationError);
      return;
    }

    setBusy(true);
    setError(null);
    try {
      const result = await api.generateCurriculumDraft(files);
      setDraft(result);
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : "The curriculum service could not be reached. Check the backend and try again.",
      );
    } finally {
      setBusy(false);
    }
  }

  if (draft) {
    return (
      <div className="draft-studio">
        <DraftResults draft={draft} onStartOver={startOver} />
      </div>
    );
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
        <h1>Build a curriculum from your source documents.</h1>
        <p>
          Generate a semester-by-semester roadmap, course outcomes, and proposed program mappings
          for your committee to review.
        </p>
      </header>

      <div className="draft-studio__workspace">
        <section className="draft-source-panel">
          <header className="draft-section-heading">
            <span>01</span>
            <div>
              <h2>Source documents</h2>
              <p>Add the syllabi, regulations, or curriculum outlines for this program.</p>
            </div>
          </header>

          <form onSubmit={handleGenerate}>
            <FieldGroup>
              <Field data-invalid={Boolean(error)}>
                <FieldLabel htmlFor="draft-source-files">Choose curriculum files</FieldLabel>
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
                  PDF, DOCX, TXT, MD, or CSV · up to {MAX_FILES} files · {MAX_FILE_MB} MB per file
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
                  <strong>Reading your documents</strong>
                  <p>Building the curriculum roadmap and mapping course outcomes. Longer programs can take a little time.</p>
                </div>
              </div>
            ) : null}

            <div className="draft-submit-row">
              <p>The result is a preview and is not saved. Download the JSON to keep a copy.</p>
              <Button type="submit" size="lg" disabled={busy || files.length === 0 || Boolean(error)}>
                {busy ? (
                  <>
                    <Spinner data-icon="inline-start" />
                    Generating draft
                  </>
                ) : (
                  <>
                    <Sparkles data-icon="inline-start" />
                    Generate curriculum draft
                  </>
                )}
              </Button>
            </div>
          </form>
        </section>

        <aside className="draft-guide">
          <div className="draft-guide__label">THE REVIEW</div>
          <h2>One draft, ready for academic review.</h2>
          <p className="draft-guide__intro">
            The generated plan stays a proposal. Your committee decides what belongs in the curriculum.
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
          </ol>
          <div className="draft-guide__foot">
            <GraduationCap aria-hidden="true" />
            <p>Review the source-derived content before using or sharing the draft.</p>
          </div>
        </aside>
      </div>
    </div>
  );
}
