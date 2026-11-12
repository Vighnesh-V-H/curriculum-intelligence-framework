# Curriculum Management API

Covers FR-02 through FR-06: curriculum creation, updates, versioning,
course addition, and course updates.

## Authorization

All endpoints require a JWT bearer token.

| Operation | Allowed roles |
| --- | --- |
| Read academic structure, curricula, versions, comparisons | Any authenticated user |
| Create/update curriculum, versions, statuses, courses | `ADMIN`, `COMMITTEE_MEMBER`, `FACULTY` |

`REVIEWER` is read-only.

## Academic Structure

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/api/v1/departments` | Create a department (`ADMIN`, `COMMITTEE_MEMBER`) |
| `GET` | `/api/v1/departments` | List departments |
| `POST` | `/api/v1/programs` | Create a program (`ADMIN`, `COMMITTEE_MEMBER`) |
| `GET` | `/api/v1/programs` | List programs |
| `GET` | `/api/v1/course-types` | List active course types |

## Curriculum and Versions

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/api/v1/curricula` | Create a curriculum with initial draft version `1.0` |
| `POST` | `/api/v1/curriculum-drafts` | Generate an AI draft from 1-5 uploaded documents (preview only) |
| `POST` | `/api/v1/curriculum-drafts/save` | Explicitly save a reviewed draft as a normalized curriculum and initial draft version |
| `GET` | `/api/v1/curricula` | List curricula with latest version summary |
| `GET` | `/api/v1/curricula/{curriculum_id}` | Get curriculum with all versions |
| `PATCH` | `/api/v1/curricula/{curriculum_id}` | Update curriculum metadata |
| `GET` | `/api/v1/curricula/{curriculum_id}/versions` | List versions |
| `POST` | `/api/v1/curricula/{curriculum_id}/versions` | Create a new draft version from the latest finalized version |
| `GET` | `/api/v1/curricula/{curriculum_id}/versions/{version_id}` | Get a single version |
| `PATCH` | `/api/v1/curricula/{curriculum_id}/versions/{version_id}/status` | Change version status |
| `GET` | `/api/v1/curricula/{curriculum_id}/compare` | Compare two versions |

Version status lifecycle:

```text
DRAFT -> UNDER_REVIEW -> APPROVED -> PUBLISHED -> ARCHIVED
```

- `UNDER_REVIEW -> DRAFT` sends a version back for changes.
- Only `DRAFT` versions accept curriculum metadata and course changes.
- Publishing a version archives any previously published version of the
  same curriculum.
- Creating a new version copies semesters and active courses from the
  latest approved or published version. The default label increments the
  minor component (`1.0 -> 1.1`); `previous_version_id` preserves the
  chain.

Version comparison accepts `base_version_id` and `target_version_id`
query parameters. It reports added courses, removed courses, and
modified course fields, including credits, semester allocation, type,
contact hours, description, and syllabus.

## Courses

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/api/v1/curricula/{curriculum_id}/versions/{version_id}/courses` | Add a course to a draft version |
| `PATCH` | `/api/v1/curricula/{curriculum_id}/versions/{version_id}/courses/{course_id}` | Update a course in a draft version |
| `DELETE` | `/api/v1/curricula/{curriculum_id}/versions/{version_id}/courses/{course_id}` | Soft-remove a course from a draft version |

Course codes are unique among active courses of a version. A course's
semester must belong to the same version. Course codes cannot be changed
through the update endpoint.

Removal is a soft delete (`status = REMOVED`) so historical versions and
audit records remain intact. Before removing a course, the service checks
for active prerequisite relationships that reference it. If any exist,
the request is rejected with `course_has_dependencies` unless `force=true`
is supplied. A removed course code may be reused within the same draft.

## AI-assisted Curriculum Draft Preview

`POST /api/v1/curriculum-drafts` is available to `ADMIN`,
`COMMITTEE_MEMBER`, and `FACULTY` users. The multipart request accepts
1-5 files from the configured document allow-list. The service extracts
text, limits the combined prompt to 120,000 characters, and requests a
roadmap-style draft from the configured LLM. Draft completions allow up to
16,384 output tokens by default and use 32,768 for Gemini 2.5 models, avoiding
truncation of larger semester, outcome, and mapping data.

Generation returns an advisory preview and does not persist it. A separate
explicit save action accepts the reviewed draft, selected program, academic
year, regulation, title, and a mapping from generated course categories to
active course types. Saving creates the curriculum, version `1.0` (`DRAFT`),
semesters, courses, course outcomes, PEO/PO versions (`DRAFT`), version pins,
and CO–PO mappings with draft mapping versions in one database transaction.
The operation never approves or publishes generated content. Existing
program-level PEO/PO codes reuse an exactly matching outcome version; changed
statements create a new draft outcome version. Invalid mappings or database
conflicts reject the whole save without leaving partial records. Courses whose
credit count is absent from the generated payload require a user-provided value. The returned draft is advisory; if uploaded material
omits PEOs or POs, the LLM proposes baseline suggestions for human review, not
claims about the source. Every course outcome must have at least one valid
CO–PO mapping. Invalid or incomplete LLM output is reported as
`503 llm_draft_failed` rather than as a client request error.

## Draft preview editing

The `/curriculum-drafts/new` preview includes an explicit edit mode before
save. It supports edits to semester name/focus, course title/category/credits/
summary, course-outcome statements, PEO/PO statements, and CO–PO mapping
strengths. Course and outcome codes remain fixed to protect mapping references.
Changing course categories requires selecting a course type for the new
category. Removing the last mapping for any course outcome blocks save; the
backend performs full schema/consistency validation and remains authoritative.
The edited preview is submitted through the existing explicit save endpoint,
which still persists all records transactionally as draft and never approves
or publishes generated content.

## Frontend test workspace

The authenticated `/curricula` page provides an operator-facing interface for
creating curricula from existing programs, adding departments/programs when the
account has the required role, selecting versions, managing courses and course
outcomes, creating/reviewing program outcomes and CO–PO mappings, proposing and
reviewing prerequisites, changing version status, and comparing versions.
Actions are shown according to the current user's role and draft state; the API
remains authoritative for authorization and transition validation. AI-generated
draft output remains a preview and is not saved by this page.

Departments and programs are managed through an academic setup panel that is
available to administrators and committee members at all times, rather than
only when the database is empty. The panel starts expanded when either list is
empty so first-time setup remains discoverable.

Version comparison renders the API result as separate added, removed, and
modified course sections. Each modified row shows the field, its previous value,
and its new value. The comparison contract currently covers course records only;
prerequisite, course outcome, and outcome-mapping differences required by FR-04
are not returned by the comparison service yet and remain tracked in the
implementation backlog.

## Audit Trail

Curriculum, version, and course writes append to `audit_logs` with the
actor, old values, new values, affected curriculum version, and action.
Audit entries are not deleted when content changes.
