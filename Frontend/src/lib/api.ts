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
  description: string | null;
  duration_years: number;
  status: string;
  latest_version: { id: string; version_label: string; status: string } | null;
};

export type Department = { id: string; code: string; name: string };

export type Program = {
  id: string;
  department_id: string;
  code: string;
  name: string;
  degree_type: string | null;
  duration_years: number;
};

export type CourseType = { code: string; name: string };

export type CurriculumVersion = {
  id: string;
  curriculum_id: string;
  version_label: string;
  status: string;
  semesters: { id: string; semester_number: number; name: string | null }[];
  courses: Course[];
};

export type Course = {
  id: string;
  curriculum_version_id: string;
  course_code: string;
  course_name: string;
  course_type_code: string;
  course_type_name: string;
  credits: number;
  semester_number: number;
  contact_hours: number | null;
  description: string | null;
  syllabus: string | null;
  status: string;
};

export type CourseOutcome = { id: string; course_id: string; co_code: string; description: string; status: string };
export type Outcome = {
  id: string;
  program_id: string;
  po_code?: string;
  peo_code?: string;
  status: string;
  current_version: { id: string; version_number: number; description: string; status: string } | null;
  versions: { id: string; version_number: number; description: string; status: string; review_comments: string | null }[];
};
export type MappingLevel = { code: string; name: string; numeric_value: number; description: string | null };
export type Mapping = {
  id: string;
  course_outcome_id: string;
  program_outcome_id: string;
  course_code: string;
  co_code: string;
  po_code: string;
  status: string;
  current_version: { id: string; mapping_level_code: string; mapping_level_name: string; numeric_value: number; status: string; review_comments: string | null } | null;
};
export type Prerequisite = {
  id: string;
  prerequisite_course_id: string;
  prerequisite_course_code: string;
  target_course_id: string;
  target_course_code: string;
  status: string;
  review_comments: string | null;
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
  listPrograms(): Promise<Program[]> {
    return request<Program[]>("/api/v1/programs");
  },
  listDepartments(): Promise<Department[]> {
    return request<Department[]>("/api/v1/departments");
  },
  createDepartment(payload: { code: string; name: string }): Promise<Department> {
    return request("/api/v1/departments", { method: "POST", body: JSON.stringify(payload) });
  },
  createProgram(payload: { department_id: string; code: string; name: string; degree_type?: string; duration_years: number }): Promise<Program> {
    return request("/api/v1/programs", { method: "POST", body: JSON.stringify(payload) });
  },
  getCurriculum(id: string): Promise<Curriculum & { versions: CurriculumVersion[] }> {
    return request(`/api/v1/curricula/${id}`);
  },
  listCourseTypes(): Promise<CourseType[]> {
    return request<{ code: string; name: string }[]>("/api/v1/course-types");
  },
  createCurriculum(payload: Record<string, unknown>): Promise<Curriculum> {
    return request<Curriculum>("/api/v1/curricula", { method: "POST", body: JSON.stringify(payload) });
  },
  updateCurriculum(id: string, payload: Record<string, unknown>): Promise<Curriculum> {
    return request<Curriculum>(`/api/v1/curricula/${id}`, { method: "PATCH", body: JSON.stringify(payload) });
  },
  getCurriculumVersions(curriculumId: string): Promise<CurriculumVersion[]> {
    return request<CurriculumVersion[]>(`/api/v1/curricula/${curriculumId}/versions`);
  },
  createCurriculumVersion(curriculumId: string, payload: { version_label?: string; change_summary?: string }): Promise<CurriculumVersion> {
    return request<CurriculumVersion>(`/api/v1/curricula/${curriculumId}/versions`, { method: "POST", body: JSON.stringify(payload) });
  },
  updateCurriculumVersionStatus(curriculumId: string, versionId: string, status: string): Promise<CurriculumVersion> {
    return request<CurriculumVersion>(`/api/v1/curricula/${curriculumId}/versions/${versionId}/status`, { method: "PATCH", body: JSON.stringify({ status }) });
  },
  compareCurriculumVersions(curriculumId: string, baseId: string, targetId: string): Promise<{ added_courses: Course[]; removed_courses: Course[]; modified_courses: { course_code: string; changes: Record<string, { before: unknown; after: unknown }> }[] }> {
    const params = new URLSearchParams({ base_version_id: baseId, target_version_id: targetId });
    return request(`/api/v1/curricula/${curriculumId}/compare?${params}`);
  },
  createCourse(curriculumId: string, versionId: string, payload: Record<string, unknown>): Promise<Course> {
    return request(`/api/v1/curricula/${curriculumId}/versions/${versionId}/courses`, { method: "POST", body: JSON.stringify(payload) });
  },
  updateCourse(curriculumId: string, versionId: string, courseId: string, payload: Record<string, unknown>): Promise<Course> {
    return request(`/api/v1/curricula/${curriculumId}/versions/${versionId}/courses/${courseId}`, { method: "PATCH", body: JSON.stringify(payload) });
  },
  removeCourse(curriculumId: string, versionId: string, courseId: string): Promise<void> {
    return request(`/api/v1/curricula/${curriculumId}/versions/${versionId}/courses/${courseId}`, { method: "DELETE" });
  },
  listCourseOutcomes(curriculumId: string, versionId: string, courseId: string): Promise<CourseOutcome[]> {
    return request(`/api/v1/curricula/${curriculumId}/versions/${versionId}/courses/${courseId}/outcomes`);
  },
  createCourseOutcome(curriculumId: string, versionId: string, courseId: string, payload: { co_code: string; description: string }): Promise<CourseOutcome> {
    return request(`/api/v1/curricula/${curriculumId}/versions/${versionId}/courses/${courseId}/outcomes`, { method: "POST", body: JSON.stringify(payload) });
  },
  updateCourseOutcome(curriculumId: string, versionId: string, courseId: string, outcomeId: string, payload: { co_code?: string; description?: string }): Promise<CourseOutcome> {
    return request(`/api/v1/curricula/${curriculumId}/versions/${versionId}/courses/${courseId}/outcomes/${outcomeId}`, { method: "PATCH", body: JSON.stringify(payload) });
  },
  removeCourseOutcome(curriculumId: string, versionId: string, courseId: string, outcomeId: string): Promise<void> {
    return request(`/api/v1/curricula/${curriculumId}/versions/${versionId}/courses/${courseId}/outcomes/${outcomeId}`, { method: "DELETE" });
  },
  reviewPrerequisite(curriculumId: string, versionId: string, prerequisiteId: string, status: "APPROVED" | "REJECTED", review_comments?: string): Promise<Prerequisite> {
    return request(`/api/v1/curricula/${curriculumId}/versions/${versionId}/prerequisites/${prerequisiteId}/status`, { method: "PATCH", body: JSON.stringify({ status, review_comments }) });
  },
  listProgramOutcomes(programId: string): Promise<Outcome[]> {
    return request(`/api/v1/programs/${programId}/program-outcomes`);
  },
  createProgramOutcome(programId: string, payload: { po_code: string; description: string }): Promise<Outcome> {
    return request(`/api/v1/programs/${programId}/program-outcomes`, { method: "POST", body: JSON.stringify(payload) });
  },
  updateProgramOutcome(outcomeId: string, payload: { po_code?: string; description?: string }): Promise<Outcome> {
    return request(`/api/v1/program-outcomes/${outcomeId}`, { method: "PATCH", body: JSON.stringify(payload) });
  },
  listPeos(programId: string): Promise<Outcome[]> {
    return request(`/api/v1/programs/${programId}/peos`);
  },
  createPeo(programId: string, payload: { peo_code: string; description: string }): Promise<Outcome> {
    return request(`/api/v1/programs/${programId}/peos`, { method: "POST", body: JSON.stringify(payload) });
  },
  updatePeo(peoId: string, payload: { peo_code?: string; description?: string }): Promise<Outcome> {
    return request(`/api/v1/peos/${peoId}`, { method: "PATCH", body: JSON.stringify(payload) });
  },
  updateOutcomeVersionStatus(kind: "po" | "peo", outcomeId: string, versionId: string, status: string, review_comments?: string): Promise<unknown> {
    const base = kind === "po" ? "program-outcomes" : "peos";
    return request(`/api/v1/${base}/${outcomeId}/versions/${versionId}/status`, { method: "PATCH", body: JSON.stringify({ status, review_comments }) });
  },
  listMappingLevels(): Promise<MappingLevel[]> {
    return request("/api/v1/mapping-levels");
  },
  listMappings(curriculumId: string, versionId: string): Promise<Mapping[]> {
    return request(`/api/v1/curricula/${curriculumId}/versions/${versionId}/mappings`);
  },
  createMapping(curriculumId: string, versionId: string, payload: { course_outcome_id: string; program_outcome_id: string; mapping_level_code: string }): Promise<Mapping> {
    return request(`/api/v1/curricula/${curriculumId}/versions/${versionId}/mappings`, { method: "POST", body: JSON.stringify(payload) });
  },
  updateMapping(mappingId: string, payload: { mapping_level_code: string }): Promise<Mapping> {
    return request(`/api/v1/mappings/${mappingId}`, { method: "PATCH", body: JSON.stringify(payload) });
  },
  updateMappingVersionStatus(mappingId: string, versionId: string, status: string, review_comments?: string): Promise<Mapping> {
    return request(`/api/v1/mappings/${mappingId}/versions/${versionId}/status`, { method: "PATCH", body: JSON.stringify({ status, review_comments }) });
  },
  removeMapping(mappingId: string): Promise<void> {
    return request(`/api/v1/mappings/${mappingId}`, { method: "DELETE" });
  },
  listPrerequisites(curriculumId: string, versionId: string): Promise<Prerequisite[]> {
    return request(`/api/v1/curricula/${curriculumId}/versions/${versionId}/prerequisites`);
  },
  createPrerequisite(curriculumId: string, versionId: string, payload: { prerequisite_course_id: string; target_course_id: string }): Promise<Prerequisite> {
    return request(`/api/v1/curricula/${curriculumId}/versions/${versionId}/prerequisites`, { method: "POST", body: JSON.stringify(payload) });
  },
  removePrerequisite(curriculumId: string, versionId: string, prerequisiteId: string): Promise<void> {
    return request(`/api/v1/curricula/${curriculumId}/versions/${versionId}/prerequisites/${prerequisiteId}`, { method: "DELETE" });
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
  saveCurriculumDraft(payload: {
    program_id: string;
    academic_year: string;
    regulation: string;
    title?: string | null;
    course_type_codes: Record<string, string>;
    credits_by_course_code: Record<string, number>;
    draft: CurriculumDraft;
  }): Promise<Curriculum & { versions: CurriculumVersion[] }> {
    return request("/api/v1/curriculum-drafts/save", {
      method: "POST",
      body: JSON.stringify(payload),
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
