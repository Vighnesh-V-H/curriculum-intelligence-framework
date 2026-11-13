const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export const TOKEN_KEY = "curriculum_access_token";

export type RoleCode = "ADMIN" | "COMMITTEE_MEMBER" | "FACULTY" | "REVIEWER";

export type UserStatus = "ACTIVE" | "INACTIVE" | "LOCKED";

export type User = {
  id: string;
  username: string;
  email: string;
  full_name: string;
  status: UserStatus;
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
  created_at: string;
  updated_at: string;
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

export type CurriculumVersionSummary = {
  id: string;
  version_label: string;
  status: string;
  previous_version_id: string | null;
  created_at: string;
  published_at: string | null;
};

export type FieldChange = { before: unknown; after: unknown };

export type ModifiedCourse = {
  course_code: string;
  course_name: string;
  changes: Record<string, FieldChange>;
};

export type PrerequisiteChange = {
  prerequisite_course_code: string;
  target_course_code: string;
};

export type CourseOutcomeChange = {
  course_code: string;
  co_code: string;
  description: string;
};

export type ModifiedCourseOutcome = {
  course_code: string;
  co_code: string;
  before_description: string;
  after_description: string;
};

export type ProgramOutcomeChange = {
  po_code: string;
  description: string | null;
};

export type ModifiedProgramOutcome = {
  po_code: string;
  before_description: string | null;
  after_description: string | null;
};

export type MappingChange = {
  course_code: string;
  co_code: string;
  po_code: string;
  mapping_level_code: string | null;
};

export type ModifiedMapping = {
  course_code: string;
  co_code: string;
  po_code: string;
  before_mapping_level_code: string | null;
  after_mapping_level_code: string | null;
};

export type VersionComparison = {
  curriculum_id: string;
  base_version: CurriculumVersionSummary;
  target_version: CurriculumVersionSummary;
  added_courses: Course[];
  removed_courses: Course[];
  modified_courses: ModifiedCourse[];
  added_prerequisites: PrerequisiteChange[];
  removed_prerequisites: PrerequisiteChange[];
  added_course_outcomes: CourseOutcomeChange[];
  removed_course_outcomes: CourseOutcomeChange[];
  modified_course_outcomes: ModifiedCourseOutcome[];
  added_program_outcomes: ProgramOutcomeChange[];
  removed_program_outcomes: ProgramOutcomeChange[];
  modified_program_outcomes: ModifiedProgramOutcome[];
  added_mappings: MappingChange[];
  removed_mappings: MappingChange[];
  modified_mappings: ModifiedMapping[];
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

export type KnowledgeGraphNode = {
  labels: string[];
  properties: Record<string, unknown>;
};

export type KnowledgeGraphRelationship = {
  type: string;
  properties: Record<string, unknown>;
  source_id: string;
  target_id: string;
};

export type KnowledgeGraph = {
  curriculum_version_id: string;
  nodes: KnowledgeGraphNode[];
  relationships: KnowledgeGraphRelationship[];
  projection_status: string;
  is_current: boolean;
};

export type KnowledgeGraphRebuild = {
  curriculum_id: string;
  curriculum_version_id: string;
  node_count: number;
  relationship_count: number;
};

export type VerificationRunSummary = {
  result?: string;
  total_findings?: number;
  findings_by_severity?: Record<string, number>;
  findings_by_category?: Record<string, number>;
  analyzers?: string[];
  prerequisite_graph?: {
    edge_count: number;
    root_courses: string[];
    leaf_courses: string[];
    isolated_courses: string[];
    longest_chain: string[];
    longest_chain_length: number;
    longest_chain_semesters: number[];
    transitive_redundant_edges: number;
  };
  structure?: {
    active_course_count: number;
    semester_count: number;
    expected_semester_count: number | null;
    total_credits: number;
    credit_totals_by_semester: Record<string, number>;
    credits_by_course_type: Record<string, number>;
    course_counts_by_semester: Record<string, number>;
    course_counts_by_course_type: Record<string, number>;
    average_semester_credits: number;
    semester_credit_range: { min: number; max: number };
  };
  credit_totals_by_semester?: Record<string, number>;
  total_credits?: number;
  credits_by_course_type?: Record<string, number>;
  topic_overlap?: {
    pairs_evaluated: number;
    candidates: number;
    redundancy_candidates: number;
    progression_candidates: number;
    unverified_progression_candidates: number;
    cross_discipline_candidates: number;
    top_overlaps: {
      course_a: string;
      course_b: string;
      semester_a: number;
      semester_b: number;
      score: number;
      title_similarity: number;
      shared_terms: string[];
      classification: string;
    }[];
  };
  reference_comparison?: {
    status: string;
    checked: boolean;
    count: number;
    references: {
      id: string;
      type: string;
      code: string;
      title: string;
      source: string;
      version_label: string;
      severity: string;
      category: string;
    }[];
    findings_by_reference: Record<string, number>;
    metrics: Record<string, unknown>;
    invalid_references: { id: string; code: string; reason: string }[];
    evidence_basis: {
      active_course_count: number;
      total_credits: number;
      credits_by_course_type: Record<string, number>;
    };
  };
  input_fingerprint?: string;
  input_fingerprint_version?: number;
};

export type VerificationRun = {
  id: string;
  curriculum_version_id: string;
  requested_by?: string;
  status: string;
  requested_at: string;
  started_at?: string | null;
  completed_at: string | null;
  error_message?: string | null;
  summary: VerificationRunSummary | null;
  input_fingerprint: string | null;
  is_stale: boolean;
};

export type VerificationReferenceType = "OBE" | "ACCREDITATION" | "INDUSTRY" | "INSTITUTIONAL";
export type VerificationReferenceStatus = "ACTIVE" | "INACTIVE";

export type VerificationNumericRange = {
  min?: number | null;
  max?: number | null;
};

export type VerificationReferenceRules = {
  total_credits?: VerificationNumericRange;
  semester_credits?: VerificationNumericRange;
  semester_count?: VerificationNumericRange;
  course_type_credits?: Record<string, VerificationNumericRange>;
  course_type_share?: Record<string, VerificationNumericRange>;
  required_po_codes?: string[];
  required_peo_codes?: string[];
  min_po_coverage_ratio?: number | null;
  min_approved_mapping_ratio?: number | null;
  criterion?: string;
  required_course_types?: string[];
  skills?: {
    code: string;
    label: string;
    keywords: string[];
    required: boolean;
    min_courses: number;
  }[];
  min_required_skill_coverage_ratio?: number | null;
};

export type VerificationReference = {
  id: string;
  program_id: string | null;
  reference_type: VerificationReferenceType;
  code: string;
  title: string;
  source: string;
  version_label: string;
  effective_date: string | null;
  severity: string;
  status: VerificationReferenceStatus;
  rules: VerificationReferenceRules;
  created_by: string;
  created_at: string;
  updated_at: string;
};

export type VerificationReferenceCreate = {
  program_id?: string | null;
  reference_type: VerificationReferenceType;
  code: string;
  title: string;
  source: string;
  version_label?: string;
  effective_date?: string | null;
  severity?: string;
  rules: VerificationReferenceRules;
};

export type VerificationReferenceUpdate = {
  title?: string;
  source?: string;
  version_label?: string;
  effective_date?: string | null;
  severity?: string;
  status?: VerificationReferenceStatus;
  rules?: VerificationReferenceRules;
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

export type VerificationReportGroup = {
  key: string;
  count: number;
  findings: VerificationFinding[];
};

export type VerificationReport = {
  run: VerificationRun;
  total_findings: number;
  groups: VerificationReportGroup[];
  counts_by_category: Record<string, number>;
  counts_by_severity: Record<string, number>;
  counts_by_review_status: Record<string, number>;
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
  createUser(payload: {
    username: string;
    email: string;
    password: string;
    full_name: string;
    roles: RoleCode[];
  }): Promise<User> {
    return request<User>("/api/v1/users", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  assignUserRoles(userId: string, roles: RoleCode[]): Promise<User> {
    return request<User>(`/api/v1/users/${userId}/roles`, {
      method: "PUT",
      body: JSON.stringify({ roles }),
    });
  },
  updateUserStatus(userId: string, status: UserStatus): Promise<User> {
    return request<User>(`/api/v1/users/${userId}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    });
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
  createCourse(curriculumId: string, versionId: string, payload: Record<string, unknown>): Promise<Course> {
    return request(`/api/v1/curricula/${curriculumId}/versions/${versionId}/courses`, { method: "POST", body: JSON.stringify(payload) });
  },
  updateCourse(curriculumId: string, versionId: string, courseId: string, payload: Record<string, unknown>): Promise<Course> {
    return request(`/api/v1/curricula/${curriculumId}/versions/${versionId}/courses/${courseId}`, { method: "PATCH", body: JSON.stringify(payload) });
  },
  removeCourse(curriculumId: string, versionId: string, courseId: string, force = false): Promise<void> {
    const query = force ? "?force=true" : "";
    return request(`/api/v1/curricula/${curriculumId}/versions/${versionId}/courses/${courseId}${query}`, { method: "DELETE" });
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
  getKnowledgeGraph(curriculumId: string, versionId: string, limit = 1000): Promise<KnowledgeGraph> {
    const params = new URLSearchParams({ limit: String(limit) });
    return request<KnowledgeGraph>(`/api/v1/curricula/${curriculumId}/versions/${versionId}/graph?${params}`);
  },
  rebuildKnowledgeGraph(curriculumId: string, versionId: string): Promise<KnowledgeGraphRebuild> {
    return request<KnowledgeGraphRebuild>(`/api/v1/curricula/${curriculumId}/versions/${versionId}/graph/rebuild`, { method: "POST" });
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
  getVerificationReport(
    runId: string,
    groupBy: "category" | "severity" | "review_status",
    filters: { category?: string; severity?: string; review_status?: string } = {},
  ): Promise<VerificationReport> {
    const params = new URLSearchParams({ group_by: groupBy });
    for (const [key, value] of Object.entries(filters)) {
      if (value) params.set(key, value);
    }
    return request<VerificationReport>(`/api/v1/verification-runs/${runId}/report?${params}`);
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
  listVerificationReferences(filters: {
    program_id?: string;
    reference_type?: VerificationReferenceType;
    include_inactive?: boolean;
  } = {}): Promise<VerificationReference[]> {
    const params = new URLSearchParams();
    if (filters.program_id) params.set("program_id", filters.program_id);
    if (filters.reference_type) params.set("reference_type", filters.reference_type);
    if (filters.include_inactive) params.set("include_inactive", "true");
    const query = params.toString();
    return request<VerificationReference[]>(
      `/api/v1/verification-references${query ? `?${query}` : ""}`,
    );
  },
  createVerificationReference(payload: VerificationReferenceCreate): Promise<VerificationReference> {
    return request<VerificationReference>("/api/v1/verification-references", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  updateVerificationReference(
    referenceId: string,
    payload: VerificationReferenceUpdate,
  ): Promise<VerificationReference> {
    return request<VerificationReference>(`/api/v1/verification-references/${referenceId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
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
  generateCurriculumDraft(files: File[], topic?: string): Promise<CurriculumDraft> {
    const form = new FormData();
    const normalizedTopic = topic?.trim();
    if (normalizedTopic) form.append("topic", normalizedTopic);
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
