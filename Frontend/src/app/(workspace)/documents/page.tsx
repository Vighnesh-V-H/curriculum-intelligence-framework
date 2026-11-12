"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { RotateCw } from "lucide-react";
import {
  ApiError,
  Document,
  DocumentStatus,
  User,
  api,
  clearStoredToken,
  getStoredToken,
} from "@/lib/api";

const ALLOWED_EXTENSIONS = [".pdf", ".docx", ".txt", ".md", ".csv"];
const MAX_FILE_MB = 20;
const WRITER_ROLES = new Set(["ADMIN", "COMMITTEE_MEMBER", "FACULTY"]);

const STATUS_BADGES: Record<DocumentStatus, string> = {
  UPLOADED: "border-warning/35 bg-warning/10 text-warning",
  PROCESSING: "border-ring/35 bg-ring/10 text-ring",
  COMPLETED: "border-success/35 bg-success/10 text-success",
  FAILED: "border-destructive/35 bg-destructive/10 text-destructive",
};

const STATUS_LABELS: Record<DocumentStatus, string> = {
  UPLOADED: "Uploaded",
  PROCESSING: "Processing",
  COMPLETED: "Analyzed",
  FAILED: "Failed",
};

function formatBytes(size: number): string {
  if (size < 1024) {
    return `${size} B`;
  }
  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1)} KB`;
  }
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(value: string | null): string {
  if (!value) {
    return "Not yet";
  }
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function fileExtension(filename: string): string {
  const dot = filename.lastIndexOf(".");
  if (dot <= 0) {
    return "";
  }
  return filename.slice(dot).toLowerCase();
}

function errorBelongsTo(caught: unknown): string {
  return caught instanceof ApiError
    ? caught.message
    : "Unable to reach the curriculum service.";
}

export default function DocumentsPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [documents, setDocuments] = useState<Document[] | null>(null);
  const [listError, setListError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [ingestingId, setIngestingId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const canWrite = user
    ? user.roles.some((role) => WRITER_ROLES.has(role))
    : false;

  const refreshDocuments = useCallback(async () => {
    setRefreshing(true);
    try {
      const docs = await api.listDocuments();
      setDocuments(docs);
    } catch (caught) {
      setActionError(errorBelongsTo(caught));
    } finally {
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    if (!documents?.some((document) => document.status === "PROCESSING")) {
      return;
    }
    const timer = window.setInterval(() => {
      void refreshDocuments();
    }, 4000);
    return () => window.clearInterval(timer);
  }, [documents, refreshDocuments]);

  useEffect(() => {
    let cancelled = false;

    async function loadWorkspace() {
      if (!getStoredToken()) {
        router.replace("/login");
        return;
      }
      try {
        const [currentUser, docs] = await Promise.all([
          api.me(),
          api.listDocuments(),
        ]);
        if (!cancelled) {
          setUser(currentUser);
          setDocuments(docs);
        }
      } catch (caught) {
        if (caught instanceof ApiError && caught.status === 401) {
          clearStoredToken();
          router.replace("/login");
          return;
        }
        if (!cancelled) {
          setListError(errorBelongsTo(caught));
          setDocuments([]);
        }
      }
    }

    loadWorkspace();
    return () => {
      cancelled = true;
    };
  }, [router]);

  function replaceDocument(next: Document) {
    setDocuments((current) =>
      current
        ? [next, ...current.filter((item) => item.id !== next.id)]
        : [next],
    );
    setSelectedId(next.id);
  }

  async function handleUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setActionError(null);
    setUploadError(null);

    if (!uploadFile) {
      setUploadError("Choose a file first.");
      return;
    }
    const extension = fileExtension(uploadFile.name);
    if (!ALLOWED_EXTENSIONS.includes(extension)) {
      setUploadError(
        `Unsupported file type. Allowed: ${ALLOWED_EXTENSIONS.join(", ")}`,
      );
      return;
    }
    if (uploadFile.size === 0) {
      setUploadError("The selected file is empty.");
      return;
    }
    if (uploadFile.size > MAX_FILE_MB * 1024 * 1024) {
      setUploadError(`File exceeds the ${MAX_FILE_MB} MB upload limit.`);
      return;
    }

    setUploading(true);
    try {
      const uploaded = await api.uploadDocument(uploadFile);
      setUploadFile(null);
      const form = event.currentTarget;
      form.reset();
      replaceDocument(uploaded);
    } catch (caught) {
      setUploadError(errorBelongsTo(caught));
    } finally {
      setUploading(false);
    }
  }

  async function handleIngest(documentId: string) {
    setActionError(null);
    setIngestingId(documentId);
    setDocuments((current) =>
      current?.map((item) =>
        item.id === documentId
          ? { ...item, status: "PROCESSING" as DocumentStatus, error_message: null }
          : item,
      ) ?? current,
    );
    try {
      const updated = await api.ingestDocument(documentId);
      replaceDocument(updated);
    } catch (caught) {
      setActionError(errorBelongsTo(caught));
      await refreshDocuments();
    } finally {
      setIngestingId(null);
    }
  }

  function handleSignOut() {
    clearStoredToken();
    router.replace("/login");
  }

  if (!user) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-background text-sm text-muted-foreground">
        {listError ? (
          <div className="rounded-xl border border-destructive/30 bg-card p-6 shadow-sm">
            <p className="text-destructive">{listError}</p>
            <button
              onClick={handleSignOut}
              className="mt-4 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground"
            >
              Return to sign in
            </button>
          </div>
        ) : (
          "Loading documents…"
        )}
      </main>
    );
  }

  return (
      <div className="mx-auto max-w-5xl">
        <header className="page-heading flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-primary">
              Curriculum Intelligence
            </p>
            <h1 className="mt-2 text-3xl font-semibold text-foreground">
              Document processing
            </h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Upload curriculum files, ingest them, and review the AI
              analysis.
            </p>
          </div>
          <button
            type="button"
            onClick={() => void refreshDocuments()}
            disabled={refreshing}
            className="inline-flex min-h-10 items-center gap-2 rounded-lg border border-border bg-card px-4 text-sm font-semibold text-foreground transition hover:bg-muted disabled:cursor-not-allowed disabled:opacity-60"
          >
            <RotateCw
              aria-hidden="true"
              className={refreshing ? "h-4 w-4 animate-spin" : "h-4 w-4"}
            />
            {refreshing ? "Refreshing…" : "Refresh"}
          </button>
        </header>

        {canWrite ? (
          <section className="mt-8">
            <form
              onSubmit={handleUpload}
              className="upload-panel rounded-xl border border-border bg-card p-5 shadow-sm"
            >
              <h2 className="text-sm font-semibold text-foreground">
                Upload a document
              </h2>
              <p className="mt-1 text-xs text-muted-foreground">
                PDF, DOCX, TXT, MD or CSV up to {MAX_FILE_MB} MB. Files upload
                to secure cloud storage — the transfer can take a few seconds.
              </p>
              <div className="mt-4 flex flex-wrap items-center gap-3">
                <input
                  type="file"
                  accept={ALLOWED_EXTENSIONS.join(",")}
                  onChange={(event) => {
                    setUploadFile(event.target.files?.[0] ?? null);
                    setUploadError(null);
                  }}
                  className="block w-full max-w-sm text-sm text-foreground file:mr-3 file:rounded-lg file:border-0 file:bg-primary file:px-4 file:py-2 file:text-sm file:font-semibold file:text-primary-foreground hover:file:bg-primary/90"
                />
                <button
                  type="submit"
                  disabled={uploading || !uploadFile}
                  className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground transition hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {uploading ? "Uploading…" : "Upload"}
                </button>
              </div>
              {uploadError ? (
                <p
                  role="alert"
                  className="mt-3 rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive"
                >
                  {uploadError}
                </p>
              ) : null}
            </form>
          </section>
        ) : null}

        {actionError ? (
          <p
            role="alert"
            className="mt-6 rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive"
          >
            {actionError}
          </p>
        ) : null}

        <section className="mt-10">
          <h2 className="text-lg font-semibold text-foreground">Documents</h2>
          {!documents ? (
            <p className="mt-3 text-sm text-muted-foreground">Loading documents…</p>
          ) : documents.length === 0 ? (
            <div className="mt-4 rounded-xl border border-dashed border-border bg-muted/50 p-8 text-center">
              <p className="text-sm text-muted-foreground">
                No documents uploaded yet.
                {canWrite
                  ? " Start by uploading a curriculum file above."
                  : " Faculty and committee members can upload curriculum files."}
              </p>
            </div>
          ) : (
            <div className="mt-4 space-y-3">
              {documents.map((document) => (
                <article
                  key={document.id}
                  className={
                    document.id === selectedId
                      ? "docs-card rounded-xl border border-primary/40 bg-primary/5 p-5 shadow-sm"
                      : "docs-card rounded-xl border border-border bg-card p-5 shadow-sm"
                  }
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <button
                      onClick={() =>
                        setSelectedId(
                          selectedId === document.id ? null : document.id,
                        )
                      }
                      className="text-left"
                    >
                      <h3 className="text-sm font-semibold text-foreground">
                        {document.original_filename}
                      </h3>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {formatBytes(document.size_bytes)} · uploaded{" "}
                        {formatDate(document.uploaded_at)}
                      </p>
                    </button>
                    <div className="flex items-center gap-2">
                      <span
                        className={`rounded-full border px-3 py-1 text-xs font-semibold ${
                          STATUS_BADGES[document.status]
                        }`}
                      >
                        {STATUS_LABELS[document.status]}
                      </span>
                      {canWrite && document.status !== "PROCESSING" ? (
                        <button
                          onClick={() => handleIngest(document.id)}
                          disabled={ingestingId !== null}
                          className="rounded-lg border border-primary/25 bg-primary/10 px-3 py-1.5 text-xs font-semibold text-primary transition hover:bg-primary/20 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          {ingestingId === document.id
                            ? "Analyzing…"
                            : document.status === "FAILED"
                              ? "Retry"
                              : document.status === "COMPLETED"
                                ? "Re-analyze"
                                : "Analyze"}
                        </button>
                      ) : null}
                    </div>
                  </div>

                  {document.status === "FAILED" && document.error_message ? (
                    <p
                      role="status"
                      className="mt-3 rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive"
                    >
                      {document.error_message}
                    </p>
                  ) : null}

                  {document.id === selectedId ? (
                    <div className="docs-detail mt-4 grid gap-4 border-t border-border pt-4 md:grid-cols-2">
                      <dl className="space-y-2 text-xs text-foreground">
                        <div className="flex gap-2">
                          <dt className="font-semibold text-muted-foreground w-32 shrink-0">
                            Type
                          </dt>
                          <dd>
                            {document.file_extension}
                            {document.content_type
                              ? ` · ${document.content_type}`
                              : ""}
                          </dd>
                        </div>
                        <div className="flex gap-2">
                          <dt className="font-semibold text-muted-foreground w-32 shrink-0">
                            Checksum
                          </dt>
                          <dd className="font-mono break-all">
                            {document.checksum_sha256.slice(0, 16)}…
                          </dd>
                        </div>
                        <div className="flex gap-2">
                          <dt className="font-semibold text-muted-foreground w-32 shrink-0">
                            LLM model
                          </dt>
                          <dd>{document.llm_model ?? "—"}</dd>
                        </div>
                        <div className="flex gap-2">
                          <dt className="font-semibold text-muted-foreground w-32 shrink-0">
                            Processed at
                          </dt>
                          <dd>{formatDate(document.processed_at)}</dd>
                        </div>
                      </dl>
                      {document.error_message ? (
                        <p className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">
                          {document.error_message}
                        </p>
                      ) : null}
                      {document.extracted_text ? (
                        <div className="md:col-span-2">
                          <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                            Extracted text
                          </h4>
                          <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap rounded-lg bg-muted p-3 text-xs text-foreground">
                            {document.extracted_text}
                          </pre>
                        </div>
                      ) : null}
                      {document.llm_analysis ? (
                        <div className="md:col-span-2">
                          <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                            AI analysis
                          </h4>
                          <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap rounded-lg bg-muted p-3 text-xs text-foreground">
                            {JSON.stringify(document.llm_analysis, null, 2)}
                          </pre>
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                </article>
              ))}
            </div>
          )}
        </section>
      </div>
  );
}
