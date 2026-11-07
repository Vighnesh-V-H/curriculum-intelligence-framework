const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export const TOKEN_KEY = "curriculum_access_token";

export type User = {
  id: string;
  username: string;
  email: string;
  full_name: string;
  status: "ACTIVE" | "INACTIVE" | "LOCKED";
  roles: string[];
  last_login_at: string | null;
  created_at: string;
};

export type AuthResponse = {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
};

export type DocumentStatus = "UPLOADED" | "PROCESSING" | "COMPLETED" | "FAILED";

export type Curriculum = {
  id: string;
  program_id: string;
  program_code: string;
  program_name: string;
  academic_year: string;
  regulation: string;
  title: string | null;
  duration_years: number;
  status: string;
  latest_version: { id: string; version_label: string; status: string } | null;
};

export type CurriculumVersion = {
  id: string;
  curriculum_id: string;
  version_label: string;
  status: string;
  semesters: { id: string; semester_number: number; name: string | null }[];
  courses: { id: string; course_code: string; course_name: string }[];
};

export type VerificationRun = {
  id: string;
  curriculum_version_id: string;
  status: string;
  requested_at: string;
  completed_at: string | null;
  summary: { result?: string; total_findings?: number; findings_by_severity?: Record<string, number> } | null;
};

export type VerificationFinding = {
  id: string;
  verification_run_id: string;
  category: string;
  severity: string;
  confidence: number | null;
  title: string;
  description: string | null;
  evidence: string | null;
  recommendation: string | null;
  requires_human_review: boolean;
  review_status: string;
  reviewed_by: string | null;
  reviewed_at: string | null;
  review_comments: string | null;
  references: { id: string; entity_type: string; entity_id: string; note: string | null }[];
};

export type DraftOutcome = {
  code: string;
  statement: string;
};

export type DraftProgram = {
  name: string | null;
  degree: string | null;
  duration_years: number | null;
  summary: string;
};

export type DraftCourse = {
  code: string;
  title: string;
  credits: number | null;
  category: string;
  summary: string;
  outcomes: DraftOutcome[];
};

export type DraftSemester = {
  semester_number: number;
  semester_name: string;
  focus: string;
  courses: DraftCourse[];
};

export type DraftMapping = {
  course_code: string;
  course_outcome_code: string;
  program_outcome_code: string;
  level: 1 | 2 | 3;
};

export type CurriculumDraft = {
  program: DraftProgram;
  semesters: DraftSemester[];
  peos: DraftOutcome[];
  pos: DraftOutcome[];
  mappings: DraftMapping[];
};

export type Document = {
  id: string;
  original_filename: string;
  file_extension: string;
  content_type: string | null;
  size_bytes: number;
  checksum_sha256: string;
  status: DocumentStatus;
  llm_model: string | null;
  extracted_text: string | null;
  llm_analysis: Record<string, unknown> | null;
  error_message: string | null;
  uploaded_by: string;
  uploaded_at: string;
  processed_at: string | null;
};

type ApiErrorBody = {
  error?: {
    code?: string;
    message?: string;
  };
};

export class ApiError extends Error {
  status: number;
  code: string;

  constructor(message: string, status: number, code: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);

  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  if (typeof window !== "undefined") {
    const token = window.localStorage.getItem(TOKEN_KEY);
    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }
  }

  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, { ...init, headers });
  } catch (caught) {
    const cause = caught instanceof Error ? caught.message : String(caught);
    throw new ApiError(
      `Could not reach the backend — ${cause}. Check that the backend is running at ${API_URL}.`,
      0,
      "network_error",
    );
  }

  if (!response.ok) {
    let body: ApiErrorBody = {};
    try {
      body = (await response.json()) as ApiErrorBody;
    } catch {
      body = {};
    }
    throw new ApiError(
      body.error?.message ?? `Request failed with status ${response.status}`,
      response.status,
      body.error?.code ?? "request_failed",
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }

  let payload: T;
  try {
    payload = (await response.json()) as T;
  } catch {
    throw new ApiError(
      "Backend returned an unreadable response body.",
      response.status,
      "invalid_response",
    );
  }
  return payload as T;
}

export const api = {
  register(payload: {
    username: string;
    email: string;
    password: string;
    full_name: string;
  }): Promise<User> {
    return request<User>("/api/v1/auth/register", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  login(username: string, password: string): Promise<AuthResponse> {
    return request<AuthResponse>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    });
  },
  me(): Promise<User> {
    return request<User>("/api/v1/auth/me");
  },
  listUsers(): Promise<User[]> {
    return request<User[]>("/api/v1/users");
  },
  listCurricula(): Promise<Curriculum[]> {
    return request<Curriculum[]>("/api/v1/curricula");
  },
  getCurriculumVersions(curriculumId: string): Promise<CurriculumVersion[]> {
    return request<CurriculumVersion[]>(`/api/v1/curricula/${curriculumId}/versions`);
  },
  listVerificationRuns(curriculumId: string, versionId: string): Promise<VerificationRun[]> {
    return request<VerificationRun[]>(
      `/api/v1/curricula/${curriculumId}/versions/${versionId}/verification-runs`,
    );
  },
  startVerification(curriculumId: string, versionId: string): Promise<VerificationRun> {
    return request<VerificationRun>(
      `/api/v1/curricula/${curriculumId}/versions/${versionId}/verification-runs`,
      { method: "POST" },
    );
  },
  listVerificationFindings(runId: string): Promise<VerificationFinding[]> {
    return request<VerificationFinding[]>(`/api/v1/verification-runs/${runId}/findings`);
  },
  reviewVerificationFinding(
    findingId: string,
    reviewStatus: "ACCEPTED" | "REJECTED" | "MODIFIED",
    reviewComments: string,
  ): Promise<VerificationFinding> {
    return request<VerificationFinding>(`/api/v1/verification-findings/${findingId}/review`, {
      method: "PATCH",
      body: JSON.stringify({ review_status: reviewStatus, review_comments: reviewComments || null }),
    });
  },
  uploadDocument(file: File): Promise<Document> {
    const form = new FormData();
    form.append("file", file);
    return request<Document>("/api/v1/documents", {
      method: "POST",
      body: form,
    });
  },
  listDocuments(): Promise<Document[]> {
    return request<Document[]>("/api/v1/documents");
  },
  getDocument(documentId: string): Promise<Document> {
    return request<Document>(`/api/v1/documents/${documentId}`);
  },
  ingestDocument(documentId: string): Promise<Document> {
    return request<Document>(`/api/v1/documents/${documentId}/ingest`, {
      method: "POST",
    });
  },
  generateCurriculumDraft(files: File[]): Promise<CurriculumDraft> {
    const form = new FormData();
    for (const file of files) {
      form.append("files", file);
    }
    return request<CurriculumDraft>("/api/v1/curriculum-drafts", {
      method: "POST",
      body: form,
    });
  },
};

export function getStoredToken(): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  return window.localStorage.getItem(TOKEN_KEY);
}

export function storeToken(token: string): void {
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearStoredToken(): void {
  if (typeof window !== "undefined") {
    window.localStorage.removeItem(TOKEN_KEY);
  }
}
