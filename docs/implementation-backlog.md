# Implementation Backlog

This file tracks work still needed to complete the Curriculum Intelligence and Verification Framework. It is separated by backend, frontend, and cross-cutting work so the scope can be reviewed before implementation.

## Backend

### 1. Knowledge graph
- [x] Define and document the graph model for curriculum entities and relationships (`docs/lld/knowledge-graph.md`).
- [x] Implement version-scoped Neo4j snapshot persistence and read queries through the authenticated graph API.
- [x] Define the relational/graph consistency and version-history strategy in the graph LLD.
- [x] Add a durable transactional outbox, retrying projection worker, and graph freshness metadata (`graph_projection_jobs`).

### 2. Curriculum verification
- [x] Add deterministic course/semester structure checks, CO–PO coverage checks, semester credit summaries, and prerequisite analysis in one version-scoped run (FR-12/FR-14).
- [x] Persist findings with evidence, confidence, severity, recommendations, and traceable references; require human review and never automatically modify curricula.
- [ ] Add topic overlap/progression, skills/competency, configurable balance thresholds, and OBE/accreditation/industry comparisons after their reference data and rules are specified.

### 3. Finding review and reports
- [x] Add authorized API operations to record finding review decisions and comments (accept, reject, or modify).
- [x] Preserve reviewer identity, timestamps, and audit history.
- [x] Provide report API responses grouped by category, severity, or review status, with filtered counts.

### 4. Document-to-curriculum workflow
- [x] Complete the workflow from uploaded document and extracted content to a validated, editable curriculum draft.
- [x] Add an explicit save action that persists the preview as curriculum/version 1.0 with courses, outcomes, PEOs, POs, and draft mappings.
- [x] Add in-place editing of semester/course/CO/PEO/PO content and CO–PO mapping strength before save; backend validation remains authoritative.
- [x] Define handling for unsupported or scanned documents; OCR is intentionally unsupported and files without extractable text fail with a clear error.
- [x] Ensure ingestion and draft-generation failures are traceable and can be retried safely.

### 5. Backend validation and tests
- [x] Add tests for each new analysis module, graph behavior, review permissions, and failure cases.
- [x] Add integration tests for document-to-draft-to-curriculum and verification/report workflows.
- [ ] Establish evaluation datasets and measures for extraction quality, analysis accuracy, and false positives (blocked: requires domain-owned labelled data).

## Frontend

### 1. Curriculum management
- [x] Add a test workspace for curriculum creation, course/course-outcome management, version status, and comparisons.
- [x] Complete curriculum metadata editing and expose all course-outcome update/remove operations.
- [x] Respect backend authorization and version-state rules; the frontend must not be the authority for access control (API enforcement remains authoritative).

### 2. Outcomes and mappings
- [x] Add UI to create POs/PEOs, advance outcome versions through review, and create/review CO–PO mappings.
- [x] Add outcome metadata/status editing and mapping-level update/removal controls.

### 3. Verification experience
- [x] Build a verification-run workflow and display run status and summaries.
- [x] Display findings with category, severity, confidence, evidence, related curriculum entities, and recommendations.
- [x] Add authorized finding review actions and show the current review status/comment.
- [x] Provide a readable report view with filtering and grouping.

### 4. Curriculum exploration
- [x] Add an interactive curriculum/dependency visualization and course details view using the relational curriculum contract.
- [x] Provide accessible alternatives to visual-only information, including lists or tables.

### 5. Document and draft workflow
- [x] Complete the UI for uploading documents, tracking processing status, viewing extracted/analysis results, and handling failures.
- [x] Add a draft review/edit screen and an explicit save-to-curriculum flow; generated drafts must not be treated as saved curricula until confirmed.

## Cross-cutting

- [x] Update the relevant requirements, LLDs, API contracts, and project status documentation as features are designed and implemented.
- [ ] Add end-to-end tests covering the main user workflows across frontend and backend (backend integration coverage exists; browser-level tests are not yet set up).
- [ ] Define and run domain/expert validation for verification findings and recommendations (blocked: requires domain-expert reviewers and agreed evaluation criteria).
- [ ] Add production deployment/containerization configuration, operational documentation, and secure environment configuration (separate infrastructure decision).

## Blocked or deferred

- Extended FR-14 verification (topic overlap/progression, skills/competency, configurable balance thresholds, and OBE/accreditation/industry comparisons) is deferred until institutional rules and governed reference datasets are defined.
- Extraction-quality and analysis-accuracy evaluation requires labelled datasets reviewed by domain experts.
- OCR for scanned documents is explicitly out of scope; such files fail with a clear "no extractable text" error.
- Browser-level end-to-end tests and production deployment remain separate follow-up work.

## Current baseline

The repository already has authentication, relational curriculum/version management, course outcomes, Program Outcome/PEO and CO–PO management, prerequisite management and prerequisite verification, document upload/LLM processing, and AI-assisted curriculum draft generation. The frontend covers authentication, documents with processing status and retry, draft generation and review, verification review with grouped reports, and a curriculum workspace with metadata/CO/PO/PEO/mapping editing, structure summaries, and accessible dependency exploration. Backend tests cover curriculum editing, mapping lifecycle rules, prerequisite removal, document retry, and the document-to-draft-to-saved-curriculum-to-verification-report flow. This backlog lists remaining work.
