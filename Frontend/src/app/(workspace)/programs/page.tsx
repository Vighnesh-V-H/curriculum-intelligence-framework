"use client";

import "./programs.css";
import { FormEvent, useEffect, useState } from "react";
import { ApiError, api, Department, Program } from "@/lib/api";

function errorMessage(error: unknown) {
  return error instanceof ApiError ? error.message : "The request could not be completed.";
}

export default function ProgramsPage() {
  const [programs, setPrograms] = useState<Program[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    let cancelled = false;
    Promise.all([api.listPrograms(), api.listDepartments()])
      .then(([programRows, departmentRows]) => {
        if (cancelled) return;
        setPrograms(programRows);
        setDepartments(departmentRows);
      })
      .catch((caught) => { if (!cancelled) setError(errorMessage(caught)); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  async function createProgram(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const created = await api.createProgram({
        department_id: String(form.get("department_id")),
        code: String(form.get("code")),
        name: String(form.get("name")),
        degree_type: String(form.get("degree_type") || ""),
        duration_years: Number(form.get("duration_years")),
      });
      setPrograms((current) => [created, ...current]);
      formElement.reset();
      setNotice(`${created.code} · ${created.name} was created.`);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="programs-page">
      <header className="programs-heading">
        <div><h1>Programs</h1><p>Set up academic programs for your institution.</p></div>
        <span className="programs-count">{programs.length} {programs.length === 1 ? "program" : "programs"}</span>
      </header>

      <section className="programs-layout" aria-label="Manage programs">
        <form className="programs-form" onSubmit={createProgram}>
          <h2>Add a program</h2>
          <p>Each program belongs to a department and can be used when creating curricula.</p>
          {error && <p className="programs-message programs-message--error" role="alert">{error}</p>}
          {notice && <p className="programs-message programs-message--success" role="status">{notice}</p>}
          <label>Department<select name="department_id" required defaultValue="" disabled={!departments.length}><option value="" disabled>Select a department</option>{departments.map((department) => <option key={department.id} value={department.id}>{department.code} · {department.name}</option>)}</select></label>
          {!departments.length && !loading && <p className="programs-hint">No departments are available. Create one from Departments in the sidebar first.</p>}
          <label>Program name<input name="name" required maxLength={200} placeholder="Computer Science and Engineering" /></label>
          <div className="programs-fields">
            <label>Program code<input name="code" required maxLength={20} pattern="[A-Za-z0-9_-]+" placeholder="BTECH-CSE" /></label>
            <label>Degree type <span className="programs-optional">Optional</span><input name="degree_type" maxLength={50} placeholder="B.Tech" /></label>
          </div>
          <label>Duration (years)<input name="duration_years" type="number" required min="0.1" max="10" step="0.1" defaultValue="4" /></label>
          <button type="submit" disabled={busy || !departments.length}>{busy ? "Creating…" : "Create program"}</button>
        </form>

        <section className="programs-list" aria-labelledby="program-list-title">
          <div className="programs-list-heading"><h2 id="program-list-title">Academic programs</h2><span>{programs.length}</span></div>
          {loading ? <p className="programs-empty" role="status">Loading programs…</p> : programs.length ? (
            <ul>{programs.map((program) => {
              const department = departments.find((item) => item.id === program.department_id);
              return <li key={program.id}><div><strong>{program.name}</strong><span>{program.code} · {department?.name ?? "Department"}</span></div><span className="programs-degree">{program.degree_type || `${program.duration_years} years`}</span></li>;
            })}</ul>
          ) : <p className="programs-empty">No programs yet. Add the first one using the form.</p>}
        </section>
      </section>
    </main>
  );
}
