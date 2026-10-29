# LLD: Course Outcomes and CO-PO Mapping (FR-10)

## Scope

This document describes Course Outcome (CO) management and CO-PO
mapping for curriculum versions, including mapping version history,
review workflow, and audit behavior.

Course Outcomes are edited as part of the curriculum version that
owns the course. CO-PO mappings link a CO to an approved Program
Outcome using a configured mapping level.

## Data Model

### `course_outcomes`

| Column | Notes |
| --- | --- |
| `id` | UUID primary key |
| `course_id` | FK to `courses.id` |
| `curriculum_version_id` | FK to `curriculum_versions.id` |
| `co_code` | Institutional CO identifier, unique per active course |
| `description` | CO statement |
| `status` | `ACTIVE` or `INACTIVE` |
| `created_by`, `updated_by` | User references |
| `created_at`, `updated_at` | Timestamps |

Removal is a soft transition to `INACTIVE`; rows are never physically
deleted. An inactive code may be reused by a new CO.

### `mapping_levels`

Configured institutional scale (`HIGH`, `MEDIUM`, `LOW` in seed data).
Each level has a code, display name, numeric value, sort order, and
active flag. The scale is not hard-coded.

### `curriculum_version_program_outcomes`

Pins the approved Program Outcome version used by a curriculum
version. The primary key is
`(curriculum_version_id, program_outcome_id)`.

The pin is created automatically when the first mapping for a PO is
created in a draft curriculum version. If the PO has a newer approved
version before the curriculum version leaves draft, the pin is
refreshed to the latest approved version.

### `co_po_mappings`

Identity and lifecycle of the CO-PO relationship within a curriculum
version. An active mapping is unique per
`(curriculum_version_id, course_outcome_id, program_outcome_id)`.

### `co_po_mapping_versions`

Historical mapping content: version number, mapping level, effective
date, status, review comments, creator, approver, and approval time.

## API Endpoints

### Course Outcomes

| Method | Path | Access |
| --- | --- | --- |
| `GET` | `/api/v1/curricula/{curriculum_id}/versions/{version_id}/courses/{course_id}/outcomes` | Authenticated |
| `POST` | same path | `ADMIN`, `COMMITTEE_MEMBER`, `FACULTY` |
| `PATCH` | same path plus `/{outcome_id}` | `ADMIN`, `COMMITTEE_MEMBER`, `FACULTY` |
| `DELETE` | same path plus `/{outcome_id}` | `ADMIN`, `COMMITTEE_MEMBER`, `FACULTY` |

CO writes require a `DRAFT` curriculum version and an active course in
that version. CO codes are normalized to uppercase and must be unique
among active COs of the course. `DELETE` sets the CO to `INACTIVE`.

### CO-PO Mappings

| Method | Path | Access |
| --- | --- | --- |
| `GET` | `/api/v1/mapping-levels` | Authenticated |
| `GET` | `/api/v1/curricula/{curriculum_id}/versions/{version_id}/mappings` | Authenticated |
| `POST` | same path | `ADMIN`, `COMMITTEE_MEMBER`, `FACULTY` |
| `GET` | `/api/v1/mappings/{mapping_id}` | Authenticated |
| `PATCH` | `/api/v1/mappings/{mapping_id}` | `ADMIN`, `COMMITTEE_MEMBER`, `FACULTY` |
| `DELETE` | `/api/v1/mappings/{mapping_id}` | `ADMIN`, `COMMITTEE_MEMBER`, `FACULTY` |
| `GET` | `/api/v1/mappings/{mapping_id}/versions` | Authenticated |
| `PATCH` | `/api/v1/mappings/{mapping_id}/versions/{version_id}/status` | `ADMIN`, `COMMITTEE_MEMBER` |

The mapping list supports optional `course_outcome_id` and
`program_outcome_id` query filters. `DELETE` deactivates the mapping
identity; version history is retained.

## Validation Rules

Creating a mapping requires:

1. A `DRAFT` curriculum version.
2. An active CO belonging to that curriculum version.
3. An active PO belonging to the curriculum's program.
4. An `APPROVED` version of that PO.
5. An active mapping level.
6. No existing active mapping for the same CO and PO.

Updates require a `DRAFT` curriculum version and an active mapping.
While the latest mapping version is `PROPOSED`, edits are rejected.
Edits to `DRAFT` or `REJECTED` versions are applied in place; edits to
`APPROVED` or `SUPERSEDED` versions create a new `DRAFT` version.

## Version Workflow

```text
DRAFT -> PROPOSED -> APPROVED
                  -> REJECTED -> DRAFT
```

- Only `PROPOSED` versions can be approved or rejected.
- Approving a version supersedes the previously approved version of the
  same mapping.
- Approval records the approver and time and defaults `effective_date`
  to the current date when none is set.
- Rejection preserves review comments and allows the mapping owner to
  return the version to `DRAFT` for revision.

## Audit Trail

The following operations write `audit_logs` entries:

- Course Outcome create, update, and remove.
- Mapping create, update, and remove.
- Mapping version create and status change.
- Superseded mapping versions.

Mapping entries include `curriculum_version_id` so they can be traced
to the curriculum version that owns them.

## Historical Integrity

- Current mappings are resolved from the latest `APPROVED` mapping
  version, falling back to the latest version when none is approved.
- Superseded versions remain queryable.
- Inactive mappings and COs remain stored.
- Non-draft curriculum versions cannot be modified, preserving the
  mapping data attached to historical versions.
