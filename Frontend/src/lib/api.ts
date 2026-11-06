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
