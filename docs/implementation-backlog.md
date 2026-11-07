# Implementation Backlog

This file tracks work still needed to complete the Curriculum Intelligence and Verification Framework. It is separated by backend, frontend, and cross-cutting work so the scope can be reviewed before implementation.

## Backend

### 1. Knowledge graph
- Define and document the graph model for curriculum entities and relationships.
- Implement graph persistence and queries (the current application stores curriculum data in PostgreSQL; Neo4j is not implemented).
- Define how relational records and graph data stay consistent, including updates and version history.

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
- Complete the workflow from uploaded document and extracted content to a validated, editable curriculum draft.
- Support reviewing and editing generated draft data before saving it as a curriculum/version.
- Define handling for unsupported or scanned documents; OCR is currently unsupported.
- Ensure ingestion and draft-generation failures are traceable and can be retried safely.

### 5. Backend validation and tests
- Add tests for each new analysis module, graph behavior, review permissions, and failure cases.
- Add integration tests for document-to-draft-to-curriculum and verification/report workflows.
- Establish evaluation datasets and measures for extraction quality, analysis accuracy, and false positives.

## Frontend

### 1. Curriculum management
- Build UI workflows to create and edit curricula and versions.
- Support listing and managing courses, course outcomes, semester allocation, and curriculum version comparisons.
- Respect backend authorization and version-state rules; the frontend must not be the authority for access control.

### 2. Outcomes and mappings
- Build UI for managing and reviewing Program Outcomes and Program Educational Objectives.
- Build UI for Course Outcome–Program Outcome mappings, including mapping levels and version/review status.

### 3. Verification experience
- Build a verification-run workflow and display run status and summaries.
- Display findings with category, severity, confidence, evidence, related curriculum entities, and recommendations.
- Add authorized finding review actions and show review history/status.
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

The repository already has authentication, relational curriculum/version management, course outcomes, Program Outcome/PEO and CO–PO management, prerequisite management and prerequisite verification, document upload/LLM processing, and AI-assisted curriculum draft generation. The frontend currently provides authentication/workspace pages plus document and draft-generation pages. This backlog lists the main remaining work rather than repeating implemented capabilities.
