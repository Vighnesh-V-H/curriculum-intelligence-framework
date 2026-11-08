# Implementation Backlog

This file tracks work still needed to complete the Curriculum Intelligence and Verification Framework. It is separated by backend, frontend, and cross-cutting work so the scope can be reviewed before implementation.

## Backend

### 1. Knowledge graph
- [x] Define and document the graph model for curriculum entities and relationships (`docs/lld/knowledge-graph.md`).
- [x] Implement version-scoped Neo4j snapshot persistence and read queries through the authenticated graph API.
- [x] Define the relational/graph consistency and version-history strategy in the graph LLD.
- [x] Add a durable transactional outbox, retrying projection worker, and graph freshness metadata (`graph_projection_jobs`).

### 2. Curriculum verification
- Extend verification beyond prerequisite checks to include:
  - CO–PO mapping evidence and program-outcome coverage.
  - Curriculum structure, semester/credit distribution, and progression checks.
  - Topic overlap, redundancy, and progression analysis.
  - Skills and competency coverage.
  - Configured OBE/accreditation and industry-reference comparisons.
- Persist findings with evidence, confidence, severity, recommendations, and traceable references.
- Keep analysis advisory and require human review; do not automatically approve or modify curricula.

### 3. Finding review and reports
- [x] Add authorized API operations to record finding review decisions and comments (accept, reject, or modify).
- [x] Preserve reviewer identity, timestamps, and audit history.
- Provide report-oriented API responses that group findings and summarize results by category and severity.

### 4. Document-to-curriculum workflow
- [ ] Complete the workflow from uploaded document and extracted content to a validated, editable curriculum draft.
- [x] Add an explicit save action that persists the preview as curriculum/version 1.0 with courses, outcomes, PEOs, POs, and draft mappings.
- [ ] Add in-place editing of generated draft content before save; currently users review the preview and supply curriculum metadata/category mapping.
- Define handling for unsupported or scanned documents; OCR is currently unsupported.
- Ensure ingestion and draft-generation failures are traceable and can be retried safely.

### 5. Backend validation and tests
- Add tests for each new analysis module, graph behavior, review permissions, and failure cases.
- Add integration tests for document-to-draft-to-curriculum and verification/report workflows.
- Establish evaluation datasets and measures for extraction quality, analysis accuracy, and false positives.

## Frontend

### 1. Curriculum management
- [x] Add a test workspace for curriculum creation, course/course-outcome management, version status, and comparisons.
- [ ] Complete curriculum metadata editing and expose all course-outcome update/remove operations.
- [ ] Respect backend authorization and version-state rules; the frontend must not be the authority for access control (API enforcement remains authoritative).

### 2. Outcomes and mappings
- [x] Add UI to create POs/PEOs, advance outcome versions through review, and create/review CO–PO mappings.
- [ ] Add outcome metadata/status editing and mapping-level update/removal controls.

### 3. Verification experience
- Build a verification-run workflow and display run status and summaries.
- Display findings with category, severity, confidence, evidence, related curriculum entities, and recommendations.
- [x] Add authorized finding review actions and show the current review status/comment.
- Provide a readable report view with filtering and grouping.

### 4. Curriculum exploration
- Add an interactive curriculum/dependency visualization and course details view, once the backend graph/query contract is defined.
- Provide accessible alternatives to visual-only information, including lists or tables.

### 5. Document and draft workflow
- Complete the UI for uploading documents, tracking processing status, viewing extracted/analysis results, and handling failures.
- Add a draft review/edit screen and an explicit save-to-curriculum flow; generated drafts must not be treated as saved curricula until confirmed.

## Cross-cutting

- Update the relevant requirements, LLDs, API contracts, and project status documentation as features are designed and implemented.
- Add end-to-end tests covering the main user workflows across frontend and backend.
- Define and run domain/expert validation for verification findings and recommendations.
- Add production deployment/containerization configuration, operational documentation, and secure environment configuration.

## Current baseline

The repository already has authentication, relational curriculum/version management, course outcomes, Program Outcome/PEO and CO–PO management, prerequisite management and prerequisite verification, document upload/LLM processing, and AI-assisted curriculum draft generation. The frontend now includes authentication, documents, draft generation, verification review, and an initial curriculum/outcomes/mappings/prerequisites workspace. The workspace enables interactive testing of common backend paths but does not yet cover every backend operation. This backlog lists remaining work.
