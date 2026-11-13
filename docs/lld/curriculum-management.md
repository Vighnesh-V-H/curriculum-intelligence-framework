# Curriculum Management API

Covers curriculum creation and direct updates. The current product has no
user-facing draft, approval, or version-history workflow. Curriculum content
is edited in place and changes are effective immediately. The existing
`curriculum_versions` row remains an internal storage key for foreign keys,
audit, verification, and graph projection; only the current content is exposed
in the UI. PEOs, POs, COs, mappings, and prerequisites are also created as
immediately effective records.

Covers FR-02 through FR-06: curriculum creation, updates, course addition,
and course updates. FR-04 version-history behavior is retired. Historical
workflow details in the remainder of this LLD are legacy reference only; their
version creation, comparison, and approval endpoints are no longer registered.
Course, CO, mapping, prerequisite, and graph URLs still contain an internal
content key because the existing relational schema is version-scoped. Curriculum
detail returns only the current content row.

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
| `POST` | `/api/v1/departments` | Create a department (any authenticated user) |
| `GET` | `/api/v1/departments` | List departments |
| `POST` | `/api/v1/programs` | Create a program (any authenticated user) |
| `GET` | `/api/v1/programs` | List programs |
| `GET` | `/api/v1/course-types` | List active course types |

## Curriculum and Versions

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/api/v1/curricula` | Create a curriculum with initial draft version `1.0` |
| `POST` | `/api/v1/curriculum-drafts` | Generate a validated AI draft from a topic brief and/or 1-5 uploaded documents |
| `POST` | `/api/v1/curriculum-drafts/save` | Persist a generated or reviewed draft as a normalized curriculum and initial draft version; used automatically by the draft studio with a manual fallback |
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
query parameters. It reports:

- Added, removed, and modified courses, including credits, semester
  allocation, type, contact hours, description, and syllabus.
- Added and removed active prerequisite edges (`PROPOSED` or `APPROVED`).
- Added, removed, and modified active course outcomes for courses present
  in both versions.
- Added, removed, and modified pinned program outcome descriptions.
- Added, removed, and modified active CO–PO mappings, comparing the
  effective mapping level (latest approved mapping version, otherwise the
  latest mapping version).

Prerequisites, course outcomes, and mappings attached to courses that were
added or removed are not repeated in their own sections; the course-level
difference already identifies them.

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

The `/curricula` interface requires confirmation before removing a course.
It lists active prerequisite dependents in the confirmation dialog, shows
how many course outcomes and CO–PO mappings the course has, and sends
`force=true` only when the operator explicitly confirms a removal that has
prerequisite dependents.

## AI-assisted Curriculum Draft Generation

`POST /api/v1/curriculum-drafts` is available to `ADMIN`,
`COMMITTEE_MEMBER`, and `FACULTY` users. The multipart request accepts a
`topic` brief of 3-500 characters, 1-5 files from the configured document
allow-list, or both. At least one source is required; otherwise the request is
rejected with `400 missing_draft_source`. A topic outside the allowed length is
rejected with `400 invalid_topic`.

With documents, the service extracts text, prepends a `= Curriculum brief =`
section when a topic is present, limits the combined prompt to 120,000
characters, and requests a roadmap-style draft from the configured LLM. The
brief takes precedence over conflicting document details. With a topic only,
the service sends the brief to a topic-design prompt that proposes a complete,
realistic program without pretending a source document exists. Draft
completions allow up to 16,384 output tokens by default and use 32,768 for
Gemini models, avoiding truncation of larger semester, outcome, and mapping
data.

Generation returns a validated advisory draft; the generation endpoint itself
does not persist it. The primary `/generate-curriculum` flow asks the user to
select a destination program and upload 1-5 reference documents. The documents
are the generation source; the selected program provides the association for
the saved curriculum. It defaults academic year to the current academic year
and regulation to the current calendar year. Immediately after generation it maps
generated course categories to active course types, applies three credits to
any course whose generated credit value is missing or outside the accepted
`0 < credits <= 30` range, and submits the draft to
`POST /api/v1/curriculum-drafts/save` automatically. Saving creates
the curriculum, version `1.0` (`DRAFT`), semesters, courses, course outcomes,
PEO/PO versions (`DRAFT`), version pins, and CO–PO mappings with draft mapping
versions in one database transaction. The operation never approves or publishes
generated content. Existing program-level PEO/PO codes reuse an exactly matching
outcome version; changed statements create a new draft outcome version. Invalid
mappings or database conflicts reject the whole save without leaving partial
records.

If automatic saving fails, for example because no course type matches a
generated category or the backend is unavailable, the flow reports the error
on the program-selection page and allows the user to retry; it does not require
a manual-save or approval step. The
returned draft is advisory; if uploaded material omits PEOs or POs, the LLM
proposes baseline suggestions for human review, not claims about the source.
Every course outcome must have at least one valid CO–PO mapping. If the first
response fails consistency validation, the service sends the validator error
and the rejected draft back to the LLM once for a complete corrected response.
A draft that is still invalid after that repair attempt is reported as
`503 llm_draft_failed`; provider transport failures are not repaired. Transient
provider statuses, including 503 overload responses, are retried up to five
times with bounded exponential backoff and jitter before that error is returned.

## Direct curriculum generation

The primary `/generate-curriculum` experience asks the user to select a
program and upload 1-5 reference documents. The uploaded documents drive
generation; the program selection determines where the result is saved. The
flow defaults academic year to the current academic year and regulation to the
current calendar year, and maps generated course categories to configured
course types. Every successful generation is immediately saved as a separate, editable
curriculum. There is no separate manual-save, draft review, or approval step.
The relational compatibility row is created internally; its version label and
status are not shown in the product. Multiple curricula may share the same
program and regulation.
On success, the user is redirected to `/curricula/{id}`. Errors
remain on the selection page so the user can retry. The former detailed studio
code remains but is not part of the normal user flow.

## Frontend test workspace

The authenticated `/curricula` page lists all saved curricula and each list
item links to its selected curriculum in the workspace. The detail workspace
shows only current curriculum content and provides no version selector, history,
comparison, draft status, or approval controls. Authorized writers can manage
courses and course
outcomes, creating/reviewing program outcomes and CO–PO mappings, proposing and
reviewing prerequisites, changing version status, and comparing versions.
Actions are shown according to the current user's role; the API remains
authoritative for authorization and validation. AI-generated curricula and
outcomes are available immediately after generation, without a review step.

Departments and programs are managed through an academic setup panel that is
available to administrators and committee members at all times, rather than
only when the database is empty. The panel starts expanded when either list is
empty so first-time setup remains discoverable.

Version comparison renders the API result as separate sections for courses,
prerequisites, course outcomes, program outcomes, and CO–PO mappings. Each
modified row shows the previous and new value. Changes inside added or removed
courses are reported with the course itself rather than repeated in the
outcome, prerequisite, and mapping sections.

## Audit Trail

Curriculum, version, and course writes append to `audit_logs` with the
actor, old values, new values, affected curriculum version, and action.
Audit entries are not deleted when content changes.
