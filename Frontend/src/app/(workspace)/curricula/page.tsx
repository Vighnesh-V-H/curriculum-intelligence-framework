"use client";

import "./curricula.css";
import { FormEvent, ReactNode, useCallback, useEffect, useState } from "react";
import { CurriculumGraph } from "@/components/curriculum-graph";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { ApiError, api, Course, CourseOutcome, CourseOutcomeChange, CourseType, Curriculum, CurriculumVersion, Department, Mapping, MappingChange, MappingLevel, ModifiedCourseOutcome, ModifiedMapping, ModifiedProgramOutcome, Outcome, Prerequisite, PrerequisiteChange, Program, ProgramOutcomeChange, VersionComparison } from "@/lib/api";

const WRITERS = new Set(["ADMIN", "COMMITTEE_MEMBER", "FACULTY"]);
const REVIEWERS = new Set(["ADMIN", "COMMITTEE_MEMBER"]);
type Detail = Curriculum & { versions: CurriculumVersion[] };
type Tab = "courses" | "structure" | "outcomes" | "mappings" | "prerequisites" | "versions";

function message(error: unknown) {
  return error instanceof ApiError ? error.message : "The request could not be completed.";
}

export default function CurriculaPage() {
  const [userRoles, setUserRoles] = useState<string[]>([]);
  const [programs, setPrograms] = useState<Program[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [courseTypes, setCourseTypes] = useState<CourseType[]>([]);
  const [curricula, setCurricula] = useState<Curriculum[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [detail, setDetail] = useState<Detail | null>(null);
  const [versionId, setVersionId] = useState("");
  const [tab, setTab] = useState<Tab>("courses");
  const [createOpen, setCreateOpen] = useState(false);
  const [setupOpen, setSetupOpen] = useState(false);
  const [comparison, setComparison] = useState("");
  const [comparisonResult, setComparisonResult] = useState<VersionComparison | null>(null);
  const [comparisonLoading, setComparisonLoading] = useState(false);
  const [removalTarget, setRemovalTarget] = useState<Course | null>(null);
  const [courseOutcomes, setCourseOutcomes] = useState<Record<string, CourseOutcome[]>>({});
  const [programOutcomes, setProgramOutcomes] = useState<Outcome[]>([]);
  const [peos, setPeos] = useState<Outcome[]>([]);
  const [levels, setLevels] = useState<MappingLevel[]>([]);
  const [mappings, setMappings] = useState<Mapping[]>([]);
  const [prerequisites, setPrerequisites] = useState<Prerequisite[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const canWrite = userRoles.some((role) => WRITERS.has(role));
  const canReview = userRoles.some((role) => REVIEWERS.has(role));
  const selectedVersion = detail?.versions.find((version) => version.id === versionId) ?? null;
  const editable = canWrite && selectedVersion?.status === "DRAFT";
  const removalDependencies = removalTarget
    ? prerequisites.filter((item) => item.prerequisite_course_id === removalTarget.id && ["PROPOSED", "APPROVED"].includes(item.status))
    : [];
  const removalMappingCount = removalTarget
    ? mappings.filter((item) => item.course_code === removalTarget.course_code).length
    : 0;
  const removalOutcomeCount = removalTarget ? (courseOutcomes[removalTarget.id] ?? []).length : 0;

  const refreshCurricula = useCallback(async (selectId?: string) => {
    const rows = await api.listCurricula();
    setCurricula(rows);
    const nextId = selectId ?? selectedId;
    if (nextId !== selectedId) { setComparisonResult(null); setComparison(""); }
    if (nextId && rows.some((row) => row.id === nextId)) setSelectedId(nextId);
    else if (rows[0]) setSelectedId(rows[0].id);
    else setSelectedId("");
  }, [selectedId]);

  useEffect(() => {
    let cancelled = false;
    Promise.all([api.me(), api.listPrograms(), api.listDepartments(), api.listCourseTypes(), api.listCurricula(), api.listMappingLevels()])
      .then(([me, progs, depts, types, rows, mapLevels]) => {
        if (cancelled) return;
        setUserRoles(me.roles);
        setPrograms(progs);
        setDepartments(depts);
        setSetupOpen(!depts.length || !progs.length);
        setCourseTypes(types);
        setCurricula(rows);
        setLevels(mapLevels);
        setSelectedId(rows[0]?.id ?? "");
      })
      .catch((caught) => { if (!cancelled) setError(message(caught)); });
    return () => { cancelled = true; };
  }, []);

  const loadDetail = useCallback(async () => {
    if (!selectedId) { setDetail(null); return; }
    try {
      setError("");
      const data = await api.getCurriculum(selectedId);
      setDetail(data);
      const preferred = data.versions[data.versions.length - 1]?.id ?? "";
      setVersionId((current) => data.versions.some((version) => version.id === current) ? current : preferred);
    } catch (caught) { setError(message(caught)); }
  }, [selectedId]);

  useEffect(() => {
    async function syncCurriculum() { await loadDetail(); }
    void syncCurriculum();
  }, [loadDetail]);

  const loadVersionData = useCallback(async () => {
    if (!detail || !versionId) return;
    try {
      const current = detail.versions.find((version) => version.id === versionId);
      const [mapRows, preRows, poRows, peoRows] = await Promise.all([
        api.listMappings(detail.id, versionId),
        api.listPrerequisites(detail.id, versionId),
        api.listProgramOutcomes(detail.program_id),
        api.listPeos(detail.program_id),
      ]);
      setMappings(mapRows); setPrerequisites(preRows); setProgramOutcomes(poRows); setPeos(peoRows);
      if (current) {
        const outcomes = await Promise.all(current.courses.map((course) => api.listCourseOutcomes(detail.id, versionId, course.id)));
        setCourseOutcomes(Object.fromEntries(current.courses.map((course, index) => [course.id, outcomes[index]])));
      }
    } catch (caught) { setError(message(caught)); }
  }, [detail, versionId]);

  useEffect(() => {
    async function syncVersion() { await loadVersionData(); }
    void syncVersion();
  }, [loadVersionData]);

  async function run(action: () => Promise<unknown>, success: string) {
    setBusy(true); setError(""); setNotice(""); setComparisonResult(null);
    try { await action(); setNotice(success); await loadDetail(); await loadVersionData(); return true; }
    catch (caught) { setError(message(caught)); return false; }
    finally { setBusy(false); }
  }

  async function removeSelectedCourse() {
    if (!detail || !versionId || !removalTarget) return;
    const removed = await run(
      () => api.removeCourse(detail.id, versionId, removalTarget.id, removalDependencies.length > 0),
      "Course removed.",
    );
    if (removed) setRemovalTarget(null);
  }

  async function updateCurriculumMeta(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!detail) return;
    const form = new FormData(event.currentTarget);
    await run(() => api.updateCurriculum(detail.id, {
      academic_year: String(form.get("academic_year")),
      regulation: String(form.get("regulation")),
      title: String(form.get("title") || "") || null,
      description: String(form.get("description") || "") || null,
      duration_years: Number(form.get("duration_years")),
    }), "Curriculum metadata updated.");
  }

  async function updateCourseOutcome(event: FormEvent<HTMLFormElement>, courseId: string, outcomeId: string) {
    event.preventDefault(); if (!detail || !versionId) return;
    const form = new FormData(event.currentTarget);
    await run(() => api.updateCourseOutcome(detail.id, versionId, courseId, outcomeId, {
      co_code: String(form.get("co_code")),
      description: String(form.get("description")),
    }), "Course outcome updated.");
  }

  async function removeCourseOutcome(courseId: string, outcomeId: string) {
    if (!detail || !versionId) return;
    await run(() => api.removeCourseOutcome(detail.id, versionId, courseId, outcomeId), "Course outcome removed.");
  }

  async function updateOutcome(kind: "po" | "peo", outcomeId: string, event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const description = String(form.get("description") || "").trim();
    const code = String(form.get("code") || "").trim();
    if (!description || !code) return;
    await run(
      () => kind === "po"
        ? api.updateProgramOutcome(outcomeId, { po_code: code, description })
        : api.updatePeo(outcomeId, { peo_code: code, description }),
      `${kind.toUpperCase()} updated.`,
    );
  }

  async function updateMappingLevel(event: FormEvent<HTMLFormElement>, mappingId: string) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await run(() => api.updateMapping(mappingId, { mapping_level_code: String(form.get("level")) }), "Mapping level updated.");
  }

  async function removeMapping(mappingId: string) {
    await run(() => api.removeMapping(mappingId), "Mapping removed.");
  }

  async function removePrerequisite(prerequisiteId: string) {
    if (!detail || !versionId) return;
    await run(() => api.removePrerequisite(detail.id, versionId, prerequisiteId), "Prerequisite removed.");
  }

  async function createDepartment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    setBusy(true); setError(""); setNotice("");
    try { const created = await api.createDepartment({ code: String(form.get("code")), name: String(form.get("name")) }); setDepartments((items) => [...items, created]); setNotice("Department created."); formElement.reset(); }
    catch (caught) { setError(message(caught)); } finally { setBusy(false); }
  }

  async function createProgram(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    setBusy(true); setError(""); setNotice("");
    try { const created = await api.createProgram({ department_id: String(form.get("department_id")), code: String(form.get("code")), name: String(form.get("name")), degree_type: String(form.get("degree_type")) || undefined, duration_years: Number(form.get("duration_years")) }); setPrograms((items) => [...items, created]); setNotice("Program created."); formElement.reset(); }
    catch (caught) { setError(message(caught)); } finally { setBusy(false); }
  }

  async function createCurriculum(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const count = Math.max(1, Math.min(30, Number(form.get("semester_count")) || 1));
    const duration = Number(form.get("duration_years"));
    const payload = {
      program_id: String(form.get("program_id")), academic_year: String(form.get("academic_year")),
      regulation: String(form.get("regulation")), title: String(form.get("title") || "") || null,
      duration_years: duration, semesters: Array.from({ length: count }, (_, i) => ({ semester_number: i + 1, name: `Semester ${i + 1}` })), courses: [],
    };
    await run(async () => {
      const created = await api.createCurriculum(payload);
      await refreshCurricula((created as Curriculum).id);
      setCreateOpen(false);
    }, "Curriculum created as draft version 1.0.");
    event.currentTarget.reset();
  }

  async function updateCourse(event: FormEvent<HTMLFormElement>, courseId: string) {
    event.preventDefault(); if (!detail || !versionId) return;
    const form = new FormData(event.currentTarget);
    await run(() => api.updateCourse(detail.id, versionId, courseId, { course_name: form.get("course_name"), course_type_code: form.get("course_type_code"), credits: Number(form.get("credits")), semester_number: Number(form.get("semester_number")), description: form.get("description") || null }), "Course updated.");
  }

  async function createCourseOutcome(event: FormEvent<HTMLFormElement>, courseId: string) {
    event.preventDefault(); if (!detail || !versionId) return;
    const form = new FormData(event.currentTarget);
    await run(() => api.createCourseOutcome(detail.id, versionId, courseId, { co_code: String(form.get("co_code")), description: String(form.get("description")) }), "Course outcome added.");
    event.currentTarget.reset();
  }

  async function createCourse(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!detail || !versionId) return;
    const form = new FormData(event.currentTarget);
    await run(async () => {
      await api.createCourse(detail.id, versionId, {
        course_code: form.get("course_code"), course_name: form.get("course_name"),
        course_type_code: form.get("course_type_code"), credits: Number(form.get("credits")),
        semester_number: Number(form.get("semester_number")), contact_hours: form.get("contact_hours") ? Number(form.get("contact_hours")) : null,
        description: form.get("description") || null,
      });
    }, "Course added to this draft version.");
    event.currentTarget.reset();
  }

  async function createOutcome(event: FormEvent<HTMLFormElement>, kind: "po" | "peo") {
    event.preventDefault(); if (!detail) return;
    const form = new FormData(event.currentTarget);
    await run(async () => {
      if (kind === "po") await api.createProgramOutcome(detail.program_id, { po_code: String(form.get("code")), description: String(form.get("description")) });
      else await api.createPeo(detail.program_id, { peo_code: String(form.get("code")), description: String(form.get("description")) });
    }, `${kind.toUpperCase()} created.`);
    event.currentTarget.reset();
  }

  async function createCoPoMapping(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!detail || !versionId) return;
    const form = new FormData(event.currentTarget);
    await run(() => api.createMapping(detail.id, versionId, {
      course_outcome_id: String(form.get("co_id")), program_outcome_id: String(form.get("po_id")), mapping_level_code: String(form.get("level")),
    }), "CO–PO mapping added.");
    event.currentTarget.reset();
  }

  async function createPrerequisite(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!detail || !versionId) return;
    const form = new FormData(event.currentTarget);
    await run(() => api.createPrerequisite(detail.id, versionId, {
      prerequisite_course_id: String(form.get("prerequisite")), target_course_id: String(form.get("target")),
    }), "Prerequisite added as proposed.");
    event.currentTarget.reset();
  }

  async function createVersion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!detail) return;
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    await run(() => api.createCurriculumVersion(detail.id, { version_label: String(form.get("version_label")) || undefined, change_summary: String(form.get("change_summary")) || undefined }), "New draft version created.");
    formElement.reset();
  }

  async function compareVersions() {
    if (!detail || !comparison || !versionId) return;
    setComparisonLoading(true); setError(""); setNotice("");
    try {
      const result = await api.compareCurriculumVersions(detail.id, comparison, versionId);
      setComparisonResult(result);
    } catch (caught) {
      setError(message(caught));
    } finally {
      setComparisonLoading(false);
    }
  }

  const courses = selectedVersion?.courses ?? [];
  const allOutcomes = courses.flatMap((course) => (courseOutcomes[course.id] ?? []).map((outcome) => ({ ...outcome, course_code: course.course_code })));
  const tabs: { id: Tab; label: string }[] = [
    { id: "courses", label: "Courses & COs" }, { id: "structure", label: "Structure & dependencies" },
    { id: "outcomes", label: "Program outcomes" },
    { id: "mappings", label: "CO–PO mappings" }, { id: "prerequisites", label: "Prerequisites" }, { id: "versions", label: "Versions" },
  ];

  return <main className="academic-page">
    <header className="academic-heading"><div><p>Academic structure</p><h1>Curricula</h1><span>Manage draft versions, courses, outcomes and relationships.</span></div>
      <div className="academic-heading-actions"><label className="academic-picker">Curriculum<select value={selectedId} onChange={(event) => { setSelectedId(event.target.value); setComparison(""); setComparisonResult(null); }}><option value="">Select a curriculum</option>{curricula.map((item) => <option key={item.id} value={item.id}>{item.program_code} · {item.regulation} · {item.academic_year}</option>)}</select></label>{canWrite && <button type="button" onClick={() => setCreateOpen((open) => !open)}>{createOpen ? "Close form" : "New curriculum"}</button>}</div>
    </header>
    {error && <p className="academic-alert academic-alert--error" role="alert">{error}</p>}
    {notice && <p className="academic-alert" role="status">{notice}</p>}
    {canReview && <details className="academic-setup" open={setupOpen} onToggle={(event) => setSetupOpen(event.currentTarget.open)}>
      <summary>Departments and programs</summary>
      <div className="academic-workspace academic-bootstrap">
        <form className="academic-panel" onSubmit={createDepartment}>
          <h2>Add a department</h2>
          <p>Departments group the programs that curricula belong to.</p>
          <div className="academic-fields academic-fields--one">
            <label>Department code<input name="code" required /></label>
            <label>Department name<input name="name" required /></label>
          </div>
          <button disabled={busy}>Create department</button>
        </form>
        <form className="academic-panel" onSubmit={createProgram}>
          <h2>Add a program</h2>
          {departments.length ? <>
            <p>Programs provide the academic context for a curriculum.</p>
            <div className="academic-fields academic-fields--one">
              <label>Department<select name="department_id">{departments.map((department) => <option key={department.id} value={department.id}>{department.code} · {department.name}</option>)}</select></label>
              <label>Program code<input name="code" required /></label>
              <label>Program name<input name="name" required /></label>
              <label>Degree type<input name="degree_type" /></label>
              <label>Duration (years)<input name="duration_years" type="number" min="0.5" max="10" step="0.5" defaultValue="4" required /></label>
            </div>
            <button disabled={busy}>Create program</button>
          </> : <p className="academic-empty">Create a department first, then add its programs here.</p>}
        </form>
      </div>
    </details>}
    {canWrite && (createOpen || !curricula.length) && <form className="academic-panel academic-create-form" onSubmit={createCurriculum}>
      <h2>New curriculum</h2><div className="academic-fields">
        <label>Program<select name="program_id" required defaultValue=""><option value="" disabled>Choose a program</option>{programs.map((item) => <option key={item.id} value={item.id}>{item.code} — {item.name}</option>)}</select></label>
        <label>Academic year<input name="academic_year" required placeholder="2025–2026" /></label>
        <label>Regulation<input name="regulation" required placeholder="R2025" /></label>
        <label>Title<input name="title" placeholder="Curriculum title" /></label>
        <label>Duration (years)<input name="duration_years" type="number" min="0.5" max="10" step="0.5" defaultValue="4" required /></label>
        <label>Semesters<input name="semester_count" type="number" min="1" max="30" defaultValue="8" required /></label>
      </div><button disabled={busy || !programs.length}>{busy ? "Saving…" : "Create draft curriculum"}</button>
      {!programs.length && <small>{canReview ? "Use Academic setup to create a department and program first." : "Ask a committee member or administrator to create a department and program first."}</small>}
    </form>}
    {detail && <>
      <section className="academic-summary"><div><small>Program</small><strong>{detail.program_code} · {detail.program_name}</strong></div><div><small>Regulation</small><strong>{detail.regulation}</strong></div><div><small>Academic year</small><strong>{detail.academic_year}</strong></div>
        <label>Version<select value={versionId} onChange={(event) => { setVersionId(event.target.value); setComparisonResult(null); }}>{detail.versions.map((version) => <option key={version.id} value={version.id}>{version.version_label} · {version.status.replaceAll("_", " ")}</option>)}</select></label>
      </section>
      {canWrite && detail.latest_version?.status === "DRAFT" && <details className="academic-meta-edit">
        <summary>Edit curriculum metadata</summary>
        <form onSubmit={updateCurriculumMeta}>
          <div className="academic-fields">
            <label>Academic year<input name="academic_year" defaultValue={detail.academic_year} required /></label>
            <label>Regulation<input name="regulation" defaultValue={detail.regulation} required /></label>
            <label>Title<input name="title" defaultValue={detail.title ?? ""} /></label>
            <label>Duration (years)<input name="duration_years" type="number" min="0.5" max="10" step="0.5" defaultValue={detail.duration_years} required /></label>
            <label className="academic-meta-description">Description<textarea name="description" defaultValue={detail.description ?? ""} rows={2} /></label>
          </div>
          <button disabled={busy}>{busy ? "Saving…" : "Save metadata"}</button>
        </form>
      </details>}
      <nav className="academic-tabs" aria-label="Curriculum sections">{tabs.map((item) => <button type="button" key={item.id} className={tab === item.id ? "is-active" : ""} onClick={() => setTab(item.id)}>{item.label}</button>)}</nav>
      {!editable && <p className="academic-readonly">This version is {selectedVersion?.status.toLowerCase() ?? "not selected"}. Select an editable draft to make changes.</p>}
      {tab === "courses" && <section className="academic-workspace"><div className="academic-panel"><h2>Courses in {selectedVersion?.version_label}</h2>{courses.length ? <div className="academic-list">{courses.map((course) => <article key={course.id} className="academic-row"><div><strong>{course.course_code} · {course.course_name}</strong><p>{course.course_type_name} · {course.credits} credits · Semester {course.semester_number}</p><small>{course.description}</small><div className="co-list">{(courseOutcomes[course.id] ?? []).map((co) => <span key={co.id}><b>{co.co_code}</b> {co.description}</span>)}</div></div>{editable && <div className="academic-course-actions"><details className="academic-edit-course"><summary>Edit</summary><form onSubmit={(event) => updateCourse(event, course.id)}><label>Title<input name="course_name" defaultValue={course.course_name} required /></label><label>Type<select name="course_type_code" defaultValue={course.course_type_code}>{courseTypes.map((type) => <option key={type.code} value={type.code}>{type.name}</option>)}</select></label><label>Semester<select name="semester_number" defaultValue={course.semester_number}>{selectedVersion?.semesters.map((semester) => <option key={semester.id} value={semester.semester_number}>{semester.name ?? `Semester ${semester.semester_number}`}</option>)}</select></label><label>Credits<input name="credits" type="number" min="0.1" max="30" step="0.5" defaultValue={course.credits} required /></label><label>Description<textarea name="description" defaultValue={course.description ?? ""} rows={2} /></label><button disabled={busy}>Save course</button></form></details><form className="academic-co-form" onSubmit={(event) => createCourseOutcome(event, course.id)}><input name="co_code" aria-label="Course outcome code" placeholder="CO code" required /><input name="description" aria-label="Course outcome description" placeholder="Outcome statement" required /><button disabled={busy}>Add CO</button></form><details className="academic-co-manage"><summary>Manage COs</summary>{(courseOutcomes[course.id] ?? []).length ? (courseOutcomes[course.id] ?? []).map((co) => <div className="academic-co-edit" key={co.id}><form onSubmit={(event) => updateCourseOutcome(event, course.id, co.id)}><label>CO code<input name="co_code" defaultValue={co.co_code} required /></label><label>Description<textarea name="description" defaultValue={co.description} rows={2} required /></label><button disabled={busy}>Save CO</button></form><button className="academic-danger" type="button" disabled={busy} onClick={() => void removeCourseOutcome(course.id, co.id)}>Remove CO</button></div>) : <p className="academic-empty">No course outcomes yet.</p>}</details><button className="academic-danger" type="button" disabled={busy} onClick={() => setRemovalTarget(course)}>Remove</button></div>}</article>)}</div> : <p className="academic-empty">No courses in this version yet.</p>}</div>
        {editable && <form className="academic-panel" onSubmit={createCourse}><h2>Add a course</h2><div className="academic-fields academic-fields--one"><label>Course code<input name="course_code" required /></label><label>Course title<input name="course_name" required /></label><label>Course type<select name="course_type_code" required>{courseTypes.map((type) => <option key={type.code} value={type.code}>{type.name}</option>)}</select></label><label>Semester<select name="semester_number" required>{selectedVersion?.semesters.map((semester) => <option key={semester.id} value={semester.semester_number}>{semester.name ?? `Semester ${semester.semester_number}`}</option>)}</select></label><label>Credits<input name="credits" type="number" min="0.1" max="30" step="0.5" defaultValue="3" required /></label><label>Contact hours<input name="contact_hours" type="number" min="0" /></label><label>Description<textarea name="description" rows={2} /></label></div><button disabled={busy}>Add course</button></form>}
      </section>}
      {tab === "structure" && <section className="academic-workspace academic-workspace--stacked">
        <div className="academic-panel">
          <h2>Semester map</h2>
          <p>Credit totals and course details for {selectedVersion?.version_label}.</p>
          <div className="academic-semester-map">
            {selectedVersion?.semesters.map((semester) => {
              const semesterCourses = courses.filter((course) => course.semester_number === semester.semester_number);
              const credits = semesterCourses.reduce((total, course) => total + Number(course.credits), 0);
              return <article className="academic-semester" key={semester.id}>
                <header><strong>{semester.name ?? `Semester ${semester.semester_number}`}</strong><span>{semesterCourses.length} courses · {credits} credits</span></header>
                {semesterCourses.length ? semesterCourses.map((course) => <details className="academic-course-detail" id={`course-${course.id}`} key={course.id}>
                  <summary><span>{course.course_code} · {course.course_name}</span><small>{course.credits} credits</small></summary>
                  <div>
                    <p>{course.description ?? "No description."}</p>
                    {course.syllabus ? <pre>{course.syllabus}</pre> : null}
                    <strong>Course outcomes</strong>
                    <div className="co-list">{(courseOutcomes[course.id] ?? []).length ? (courseOutcomes[course.id] ?? []).map((outcome) => <span key={outcome.id}><b>{outcome.co_code}</b> {outcome.description}</span>) : <span>No course outcomes.</span>}</div>
                  </div>
                </details>) : <p className="academic-empty">No courses in this semester.</p>}
              </article>;
            })}
          </div>
        </div>
        <div className="academic-panel">
          <h2>Dependency graph</h2>
          <CurriculumGraph courses={courses} prerequisites={prerequisites} courseOutcomes={courseOutcomes} />
        </div>
      </section>}
      {tab === "outcomes" && <section className="academic-workspace"><div className="academic-panel"><h2>Program outcomes</h2><OutcomeList title="POs" rows={programOutcomes} codeKey="po_code" canReview={canReview} busy={busy} onUpdate={(event, row) => void updateOutcome("po", row.id, event)} onStatus={(row, status) => void run(() => api.updateOutcomeVersionStatus("po", row.id, row.current_version!.id, status), `PO ${status.toLowerCase()}.`)} /><OutcomeList title="PEOs" rows={peos} codeKey="peo_code" canReview={canReview} busy={busy} onUpdate={(event, row) => void updateOutcome("peo", row.id, event)} onStatus={(row, status) => void run(() => api.updateOutcomeVersionStatus("peo", row.id, row.current_version!.id, status), `PEO ${status.toLowerCase()}.`)} /></div>{canReview && <div className="academic-panel"><h2>Add outcomes</h2><OutcomeForm title="Program outcome" codeLabel="PO code" onSubmit={(event) => createOutcome(event, "po")} busy={busy} /><OutcomeForm title="Program educational objective" codeLabel="PEO code" onSubmit={(event) => createOutcome(event, "peo")} busy={busy} /></div>}</section>}
      {tab === "mappings" && <section className="academic-workspace"><div className="academic-panel"><h2>CO–PO mappings</h2>{mappings.length ? <div className="academic-list">{mappings.map((mapping) => <article className="academic-row" key={mapping.id}><div><strong>{mapping.course_code} · {mapping.co_code} → {mapping.po_code}</strong><p>{mapping.current_version?.mapping_level_name ?? "No level"} · {mapping.status.toLowerCase()} · {mapping.current_version?.status.toLowerCase()}</p></div>{canReview && mapping.current_version && mapping.current_version.status !== "APPROVED" && <select aria-label={`Review mapping ${mapping.co_code} to ${mapping.po_code}`} value="" onChange={(event) => void run(() => api.updateMappingVersionStatus(mapping.id, mapping.current_version!.id, event.target.value), `Mapping ${event.target.value.toLowerCase()}.`)}><option value="" disabled>Change status</option>{mapping.current_version.status === "DRAFT" && <option value="PROPOSED">Propose</option>}{mapping.current_version.status === "PROPOSED" && <><option value="APPROVED">Approve</option><option value="REJECTED">Reject</option></>}</select>}</article>)}</div> : <p className="academic-empty">No mappings for this version.</p>}{editable && mappings.length ? <details className="academic-manage-list"><summary>Manage mapping levels</summary>{mappings.filter((mapping) => mapping.status === "ACTIVE").map((mapping) => <div className="academic-manage-row" key={mapping.id}><span>{mapping.course_code} · {mapping.co_code} → {mapping.po_code}</span><form onSubmit={(event) => updateMappingLevel(event, mapping.id)}><select name="level" defaultValue={mapping.current_version?.mapping_level_code ?? levels[0]?.code}>{levels.map((level) => <option key={level.code} value={level.code}>{level.name}</option>)}</select><button disabled={busy || mapping.current_version?.status === "PROPOSED"}>Update</button></form><button className="academic-danger" type="button" disabled={busy} onClick={() => void removeMapping(mapping.id)}>Remove</button></div>)}</details> : null}</div>{editable && <form className="academic-panel" onSubmit={createCoPoMapping}><h2>Add mapping</h2><div className="academic-fields academic-fields--one"><label>Course outcome<select name="co_id" required>{allOutcomes.map((co) => <option key={co.id} value={co.id}>{co.course_code} · {co.co_code}</option>)}</select></label><label>Program outcome<select name="po_id" required>{programOutcomes.filter((po) => po.status === "ACTIVE").map((po) => <option key={po.id} value={po.id}>{po.po_code} · {po.current_version?.description}</option>)}</select></label><label>Mapping level<select name="level" required>{levels.map((level) => <option key={level.code} value={level.code}>{level.name} ({level.numeric_value})</option>)}</select></label></div><button disabled={busy || !allOutcomes.length || !programOutcomes.length}>Create mapping</button></form>}</section>}
      {tab === "prerequisites" && <section className="academic-workspace"><div className="academic-panel"><h2>Prerequisite relationships</h2>{prerequisites.length ? <div className="academic-list">{prerequisites.map((item) => <article className="academic-row" key={item.id}><div><strong>{item.prerequisite_course_code} is required before {item.target_course_code}</strong><p>{item.status.replaceAll("_", " ")}{item.review_comments ? ` · ${item.review_comments}` : ""}</p></div>{((canReview && item.status === "PROPOSED") || editable) && <div className="academic-actions">{canReview && item.status === "PROPOSED" && <><button type="button" onClick={() => void run(() => api.reviewPrerequisite(detail.id, versionId, item.id, "APPROVED"), "Prerequisite approved.")}>Approve</button><button className="academic-danger" type="button" onClick={() => void run(() => api.reviewPrerequisite(detail.id, versionId, item.id, "REJECTED"), "Prerequisite rejected.")}>Reject</button></>}{editable && <button className="academic-danger" type="button" disabled={busy} onClick={() => void removePrerequisite(item.id)}>Remove</button>}</div>}</article>)}</div> : <p className="academic-empty">No prerequisites in this version.</p>}</div>{editable && <form className="academic-panel" onSubmit={createPrerequisite}><h2>Propose prerequisite</h2><div className="academic-fields academic-fields--one"><label>Required course<select name="prerequisite" required>{courses.map((course) => <option key={course.id} value={course.id}>{course.course_code} · {course.course_name}</option>)}</select></label><label>Course that requires it<select name="target" required>{courses.map((course) => <option key={course.id} value={course.id}>{course.course_code} · {course.course_name}</option>)}</select></label></div><button disabled={busy || courses.length < 2}>Add prerequisite</button></form>}</section>}
      {tab === "versions" && <section className="academic-workspace"><div className="academic-panel"><h2>Version history</h2><div className="academic-list">{detail.versions.map((version) => <article className="academic-row" key={version.id}><div><strong>Version {version.version_label}</strong><p>{version.status.replaceAll("_", " ")} · {version.courses.length} courses · {version.semesters.length} semesters</p></div>{canWrite && ["DRAFT", "UNDER_REVIEW", "APPROVED", "PUBLISHED"].includes(version.status) && <select aria-label={`Set version ${version.version_label} status`} defaultValue="" onChange={(event) => void run(() => api.updateCurriculumVersionStatus(detail.id, version.id, event.target.value), "Version status updated.")}><option value="" disabled>Change status</option>{version.status === "DRAFT" && <option value="UNDER_REVIEW">Under review</option>}{version.status === "UNDER_REVIEW" && <><option value="DRAFT">Return to draft</option><option value="APPROVED">Approve</option></>}{version.status === "APPROVED" && <option value="PUBLISHED">Publish</option>}{version.status === "PUBLISHED" && <option value="ARCHIVED">Archive</option>}</select>}</article>)}</div></div><div className={comparisonResult ? "academic-panel academic-compare-panel is-expanded" : "academic-panel academic-compare-panel"}><h2>Compare versions</h2><div className="academic-fields academic-fields--one"><label>Compare against<select value={comparison} onChange={(event) => { setComparison(event.target.value); setComparisonResult(null); }}><option value="">Choose version</option>{detail.versions.filter((version) => version.id !== versionId).map((version) => <option key={version.id} value={version.id}>{version.version_label} · {version.status.toLowerCase()}</option>)}</select></label></div><button type="button" disabled={!comparison || !versionId || comparisonLoading} onClick={() => void compareVersions()}>{comparisonLoading ? "Comparing…" : "Compare with selected version"}</button>{comparisonResult ? <ComparisonReport result={comparisonResult} /> : null}</div>{canWrite && <form className="academic-panel" onSubmit={createVersion}><h2>Create next version</h2><p>Available when the latest version is approved or published.</p><div className="academic-fields academic-fields--one"><label>Version label<input name="version_label" placeholder="Auto-increment" pattern="[0-9]+\\.[0-9]+" /></label><label>Change summary<input name="change_summary" /></label></div><button disabled={busy}>Create draft version</button></form>}</section>}
    </>}
    <RemoveCourseDialog course={removalTarget} versionLabel={selectedVersion?.version_label} dependencies={removalDependencies} outcomeCount={removalOutcomeCount} mappingCount={removalMappingCount} busy={busy} onCancel={() => setRemovalTarget(null)} onConfirm={() => void removeSelectedCourse()} />
  </main>;
}

const COMPARISON_FIELDS: Record<string, string> = {
  course_name: "Title",
  course_type_code: "Course type",
  credits: "Credits",
  semester_number: "Semester",
  contact_hours: "Contact hours",
  description: "Description",
  syllabus: "Syllabus",
};

function comparisonValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  return String(value);
}

function ComparisonCourseTable({ courses }: { courses: Course[] }) {
  return <div className="academic-comparison__table"><table>
    <thead><tr><th scope="col">Course</th><th scope="col">Title</th><th scope="col">Type</th><th scope="col">Credits</th><th scope="col">Semester</th></tr></thead>
    <tbody>{courses.map((course) => <tr key={course.id}>
      <th scope="row">{course.course_code}</th>
      <td>{course.course_name}</td>
      <td>{course.course_type_name}</td>
      <td>{course.credits}</td>
      <td>{course.semester_number}</td>
    </tr>)}</tbody>
  </table></div>;
}

function ComparisonTable({ headers, rows, compact = false }: { headers: string[]; rows: ReactNode; compact?: boolean }) {
  return <div className={compact ? "academic-comparison__table academic-comparison__table--compact" : "academic-comparison__table"}><table>
    <thead><tr>{headers.map((header) => <th key={header} scope="col">{header}</th>)}</tr></thead>
    <tbody>{rows}</tbody>
  </table></div>;
}

function ComparisonPrerequisiteTable({ rows }: { rows: PrerequisiteChange[] }) {
  return <ComparisonTable compact headers={["Prerequisite", "Target course"]} rows={rows.map((row) => <tr key={`${row.prerequisite_course_code}-${row.target_course_code}`}>
    <th scope="row">{row.prerequisite_course_code}</th>
    <td>{row.target_course_code}</td>
  </tr>)} />;
}

function ComparisonCourseOutcomeTable({ rows }: { rows: CourseOutcomeChange[] }) {
  return <ComparisonTable headers={["Course", "CO", "Description"]} rows={rows.map((row) => <tr key={`${row.course_code}-${row.co_code}`}>
    <th scope="row">{row.course_code}</th>
    <td>{row.co_code}</td>
    <td>{row.description}</td>
  </tr>)} />;
}

function ComparisonModifiedCourseOutcomeTable({ rows }: { rows: ModifiedCourseOutcome[] }) {
  return <ComparisonTable headers={["Course", "CO", "Before", "After"]} rows={rows.map((row) => <tr key={`${row.course_code}-${row.co_code}`}>
    <th scope="row">{row.course_code}</th>
    <td>{row.co_code}</td>
    <td>{row.before_description}</td>
    <td>{row.after_description}</td>
  </tr>)} />;
}

function ComparisonProgramOutcomeTable({ rows }: { rows: ProgramOutcomeChange[] }) {
  return <ComparisonTable compact headers={["PO", "Description"]} rows={rows.map((row) => <tr key={row.po_code}>
    <th scope="row">{row.po_code}</th>
    <td>{comparisonValue(row.description)}</td>
  </tr>)} />;
}

function ComparisonModifiedProgramOutcomeTable({ rows }: { rows: ModifiedProgramOutcome[] }) {
  return <ComparisonTable headers={["PO", "Before", "After"]} rows={rows.map((row) => <tr key={row.po_code}>
    <th scope="row">{row.po_code}</th>
    <td>{comparisonValue(row.before_description)}</td>
    <td>{comparisonValue(row.after_description)}</td>
  </tr>)} />;
}

function ComparisonMappingTable({ rows }: { rows: MappingChange[] }) {
  return <ComparisonTable headers={["Course", "CO", "PO", "Level"]} rows={rows.map((row) => <tr key={`${row.course_code}-${row.co_code}-${row.po_code}`}>
    <th scope="row">{row.course_code}</th>
    <td>{row.co_code}</td>
    <td>{row.po_code}</td>
    <td>{comparisonValue(row.mapping_level_code)}</td>
  </tr>)} />;
}

function ComparisonModifiedMappingTable({ rows }: { rows: ModifiedMapping[] }) {
  return <ComparisonTable headers={["Course", "CO", "PO", "Before level", "After level"]} rows={rows.map((row) => <tr key={`${row.course_code}-${row.co_code}-${row.po_code}`}>
    <th scope="row">{row.course_code}</th>
    <td>{row.co_code}</td>
    <td>{row.po_code}</td>
    <td>{comparisonValue(row.before_mapping_level_code)}</td>
    <td>{comparisonValue(row.after_mapping_level_code)}</td>
  </tr>)} />;
}

function ComparisonReport({ result }: { result: VersionComparison }) {
  const changeRows = result.modified_courses.flatMap((course) =>
    Object.entries(course.changes).map(([field, change]) => ({ course, field, change })),
  );
  const courseTotal = result.added_courses.length + result.removed_courses.length + result.modified_courses.length;
  const relatedTotal = result.added_prerequisites.length + result.removed_prerequisites.length
    + result.added_course_outcomes.length + result.removed_course_outcomes.length + result.modified_course_outcomes.length
    + result.added_program_outcomes.length + result.removed_program_outcomes.length + result.modified_program_outcomes.length
    + result.added_mappings.length + result.removed_mappings.length + result.modified_mappings.length;
  return <div className="academic-comparison" aria-live="polite">
    <div className="academic-comparison__summary">
      <div><small>Compared</small><strong>{result.base_version.version_label} → {result.target_version.version_label}</strong></div>
      <div><small>Added courses</small><strong>{result.added_courses.length}</strong></div>
      <div><small>Removed courses</small><strong>{result.removed_courses.length}</strong></div>
      <div><small>Modified courses</small><strong>{result.modified_courses.length}</strong></div>
      <div><small>Related changes</small><strong>{relatedTotal}</strong></div>
    </div>
    {courseTotal + relatedTotal === 0 ? <p className="academic-empty">No differences between these versions.</p> : null}
    {result.added_courses.length > 0 ? <section className="academic-comparison__group"><h3>Added courses <span>{result.added_courses.length}</span></h3><ComparisonCourseTable courses={result.added_courses} /></section> : null}
    {result.removed_courses.length > 0 ? <section className="academic-comparison__group"><h3>Removed courses <span>{result.removed_courses.length}</span></h3><ComparisonCourseTable courses={result.removed_courses} /></section> : null}
    {changeRows.length > 0 ? <section className="academic-comparison__group"><h3>Modified courses <span>{result.modified_courses.length}</span></h3><div className="academic-comparison__table"><table>
      <thead><tr><th scope="col">Course</th><th scope="col">Field</th><th scope="col">Before</th><th scope="col">After</th></tr></thead>
      <tbody>{changeRows.map(({ course, field, change }) => <tr key={`${course.course_code}-${field}`}>
        <th scope="row">{course.course_code}<small>{course.course_name}</small></th>
        <td>{COMPARISON_FIELDS[field] ?? field}</td>
        <td>{comparisonValue(change.before)}</td>
        <td>{comparisonValue(change.after)}</td>
      </tr>)}</tbody>
    </table></div></section> : null}
    {result.added_prerequisites.length > 0 ? <section className="academic-comparison__group"><h3>Added prerequisites <span>{result.added_prerequisites.length}</span></h3><ComparisonPrerequisiteTable rows={result.added_prerequisites} /></section> : null}
    {result.removed_prerequisites.length > 0 ? <section className="academic-comparison__group"><h3>Removed prerequisites <span>{result.removed_prerequisites.length}</span></h3><ComparisonPrerequisiteTable rows={result.removed_prerequisites} /></section> : null}
    {result.added_course_outcomes.length > 0 ? <section className="academic-comparison__group"><h3>Added course outcomes <span>{result.added_course_outcomes.length}</span></h3><ComparisonCourseOutcomeTable rows={result.added_course_outcomes} /></section> : null}
    {result.removed_course_outcomes.length > 0 ? <section className="academic-comparison__group"><h3>Removed course outcomes <span>{result.removed_course_outcomes.length}</span></h3><ComparisonCourseOutcomeTable rows={result.removed_course_outcomes} /></section> : null}
    {result.modified_course_outcomes.length > 0 ? <section className="academic-comparison__group"><h3>Modified course outcomes <span>{result.modified_course_outcomes.length}</span></h3><ComparisonModifiedCourseOutcomeTable rows={result.modified_course_outcomes} /></section> : null}
    {result.added_program_outcomes.length > 0 ? <section className="academic-comparison__group"><h3>Added program outcomes <span>{result.added_program_outcomes.length}</span></h3><ComparisonProgramOutcomeTable rows={result.added_program_outcomes} /></section> : null}
    {result.removed_program_outcomes.length > 0 ? <section className="academic-comparison__group"><h3>Removed program outcomes <span>{result.removed_program_outcomes.length}</span></h3><ComparisonProgramOutcomeTable rows={result.removed_program_outcomes} /></section> : null}
    {result.modified_program_outcomes.length > 0 ? <section className="academic-comparison__group"><h3>Modified program outcomes <span>{result.modified_program_outcomes.length}</span></h3><ComparisonModifiedProgramOutcomeTable rows={result.modified_program_outcomes} /></section> : null}
    {result.added_mappings.length > 0 ? <section className="academic-comparison__group"><h3>Added CO–PO mappings <span>{result.added_mappings.length}</span></h3><ComparisonMappingTable rows={result.added_mappings} /></section> : null}
    {result.removed_mappings.length > 0 ? <section className="academic-comparison__group"><h3>Removed CO–PO mappings <span>{result.removed_mappings.length}</span></h3><ComparisonMappingTable rows={result.removed_mappings} /></section> : null}
    {result.modified_mappings.length > 0 ? <section className="academic-comparison__group"><h3>Modified CO–PO mappings <span>{result.modified_mappings.length}</span></h3><ComparisonModifiedMappingTable rows={result.modified_mappings} /></section> : null}
    <p className="academic-comparison__scope">Compares active courses, active prerequisite edges, active course outcomes for courses present in both versions, pinned program outcome descriptions, and active CO–PO mappings. Changes inside added or removed courses are reported with the course itself.</p>
  </div>;
}

function RemoveCourseDialog({ course, versionLabel, dependencies, outcomeCount, mappingCount, busy, onCancel, onConfirm }: {
  course: Course | null;
  versionLabel: string | undefined;
  dependencies: Prerequisite[];
  outcomeCount: number;
  mappingCount: number;
  busy: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  return <Dialog open={Boolean(course)} onOpenChange={(open) => { if (!open) onCancel(); }}>
    <DialogContent className="curriculum-dialog sm:max-w-lg">
      {course ? <>
        <DialogHeader>
          <DialogTitle>Remove {course.course_code}?</DialogTitle>
          <DialogDescription>{course.course_code} · {course.course_name} will be marked as removed from version {versionLabel ?? "the selected version"}.</DialogDescription>
        </DialogHeader>
        <div className="academic-remove-summary">
          {dependencies.length > 0 ? <>
            <p><strong>This course is a prerequisite for:</strong></p>
            <ul>{dependencies.map((item) => <li key={item.id}>{item.target_course_code}</li>)}</ul>
            <p>Those prerequisite relationships will be left unresolved. Review the dependent courses before continuing.</p>
          </> : <p>No active prerequisite dependency was found for this course.</p>}
          {(outcomeCount > 0 || mappingCount > 0) ? <p className="academic-remove-note">This version also contains {outcomeCount} course outcome{outcomeCount === 1 ? "" : "s"} and {mappingCount} active CO–PO mapping{mappingCount === 1 ? "" : "s"} for this course. They are retained for history.</p> : null}
        </div>
        <DialogFooter>
          <button type="button" onClick={onCancel} disabled={busy}>Cancel</button>
          <button className="academic-danger" type="button" onClick={onConfirm} disabled={busy}>{busy ? "Removing…" : dependencies.length > 0 ? "Remove course anyway" : "Remove course"}</button>
        </DialogFooter>
      </> : null}
    </DialogContent>
  </Dialog>;
}

function OutcomeList({ title, rows, codeKey, canReview, busy, onUpdate, onStatus }: { title: string; rows: Outcome[]; codeKey: "po_code" | "peo_code"; canReview: boolean; busy: boolean; onUpdate: (event: FormEvent<HTMLFormElement>, row: Outcome) => void; onStatus: (row: Outcome, status: string) => void }) {
  return <section className="academic-outcomes"><h3>{title}</h3>{rows.length ? rows.map((row) => {
    const current = row.current_version;
    const options = current?.status === "DRAFT" ? ["PROPOSED"] : current?.status === "PROPOSED" ? ["APPROVED", "REJECTED"] : current?.status === "REJECTED" ? ["DRAFT"] : [];
    return <article className="academic-row" key={row.id}>
      <div><strong>{row[codeKey]} · {current?.description ?? "No description"}</strong><p>{row.status.toLowerCase()} · v{current?.version_number ?? 1} · {current?.status.toLowerCase()}</p></div>
      <div className="academic-outcome-actions">
        {canReview && current && options.length > 0 && <select aria-label={`Update ${row[codeKey]} status`} value="" onChange={(event) => onStatus(row, event.target.value)}><option value="" disabled>Change status</option>{options.map((status) => <option key={status} value={status}>{status.toLowerCase()}</option>)}</select>}
        {canReview && current ? <details className="academic-outcome-edit"><summary>Edit</summary><form onSubmit={(event) => onUpdate(event, row)}><label>Code<input name="code" defaultValue={row[codeKey]} required /></label><label>Description<textarea name="description" defaultValue={current.description} rows={2} required /></label><button disabled={busy}>Save</button></form></details> : null}
      </div>
    </article>;
  }) : <p className="academic-empty">No {title} defined.</p>}</section>;
}

function OutcomeForm({ title, codeLabel, onSubmit, busy }: { title: string; codeLabel: string; onSubmit: (event: FormEvent<HTMLFormElement>) => void; busy: boolean }) {
  return <form className="academic-inline-form" onSubmit={onSubmit}><h3>{title}</h3><label>{codeLabel}<input name="code" required /></label><label>Description<textarea name="description" rows={2} required /></label><button disabled={busy}>Add {codeLabel}</button></form>;
}
