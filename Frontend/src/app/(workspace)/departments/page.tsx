"use client";

import "./departments.css";
import { FormEvent, useEffect, useState } from "react";
import { ApiError, api, Department } from "@/lib/api";

function errorMessage(error: unknown) {
  return error instanceof ApiError ? error.message : "The request could not be completed.";
}

export default function DepartmentsPage() {
  const [departments, setDepartments] = useState<Department[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    let cancelled = false;
    api.listDepartments()
      .then((rows) => { if (!cancelled) setDepartments(rows); })
      .catch((caught) => { if (!cancelled) setError(errorMessage(caught)); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  async function createDepartment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const created = await api.createDepartment({ code: String(form.get("code")), name: String(form.get("name")) });
      setDepartments((current) => [created, ...current]);
      formElement.reset();
      setNotice(`${created.code} · ${created.name} was created.`);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="departments-page">
      <header className="departments-heading">
        <div><h1>Departments</h1><p>Organize academic programs into departments.</p></div>
        <span className="departments-count">{departments.length} {departments.length === 1 ? "department" : "departments"}</span>
      </header>
      <section className="departments-layout" aria-label="Manage departments">
        <form className="departments-form" onSubmit={createDepartment}>
          <h2>Add a department</h2>
          <p>Departments group related academic programs across your institution.</p>
          {error && <p className="departments-message departments-message--error" role="alert">{error}</p>}
          {notice && <p className="departments-message departments-message--success" role="status">{notice}</p>}
          <label>Department name<input name="name" required maxLength={200} placeholder="Computer Science and Engineering" /></label>
          <label>Department code<input name="code" required maxLength={20} pattern="[A-Za-z0-9_-]+" placeholder="CSE" /></label>
          <button type="submit" disabled={busy}>{busy ? "Creating…" : "Create department"}</button>
        </form>
        <section className="departments-list" aria-labelledby="department-list-title">
          <div className="departments-list-heading"><h2 id="department-list-title">Institution departments</h2><span>{departments.length}</span></div>
          {loading ? <p className="departments-empty" role="status">Loading departments…</p> : departments.length ? (
            <ul>{departments.map((department) => <li key={department.id}><div><strong>{department.name}</strong><span>{department.code}</span></div></li>)}</ul>
          ) : <p className="departments-empty">No departments yet. Add the first one using the form.</p>}
        </section>
      </section>
    </main>
  );
}
