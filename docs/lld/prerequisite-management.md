# LLD: Prerequisite Management (FR-11)

## Scope

This document covers prerequisite relationship management between
courses inside a curriculum version: definition, viewing, review,
and removal, including circular-dependency prevention and audit
behavior.

A prerequisite edge states that the *prerequisite* course is expected
before the *target* course. Edges are directed
(`prerequisite -> target`) exactly as required by FR-11:

```text
CS101 -> CS201 -> CS301 -> CS401
```

## Design Note (FR-11-03)

The requirement asks for history "where versioning is applicable".
The adopted database schema (`alembic/sql/001_initial_schema.sql`,
section 7) models a prerequisite as a single identity row with a
status workflow (`PROPOSED`, `APPROVED`, `REJECTED`, `REMOVED`) and no
separate version table. Consequently:

- The only updatable attribute is review state (`review_comments`,
  status) through the review endpoint.
- Changing which course is a prerequisite is modeled as remove plus
  re-create, each step audited.
- Full change history is preserved in `audit_logs`.

## Data Model

### `course_prerequisites`

| Column | Notes |
| --- | --- |
| `id` | UUID primary key |
| `curriculum_version_id` | FK to `curriculum_versions.id` |
| `prerequisite_course_id` | FK to `courses.id` (same version) |
| `target_course_id` | FK to `courses.id` (same version) |
| `status` | `PROPOSED`, `APPROVED`, `REJECTED`, `REMOVED` |
| `review_comments` | Committee review comments |
| `created_by`, `approved_by` | User references |
| `created_at`, `updated_at`, `approved_at` | Timestamps |

- Removal is a transition to `REMOVED`; rows are never physically
  deleted (BR-PR-06/07).
- An active relationship is `PROPOSED` or `APPROVED`. The same pair of
  courses may have only one active relationship per version.

## API Endpoints

| Method | Path | Access |
| --- | --- | --- |
| `GET` | `/api/v1/curricula/{curriculum_id}/versions/{version_id}/prerequisites` | Authenticated |
| `POST` | same path | `ADMIN`, `COMMITTEE_MEMBER`, `FACULTY` |
| `GET` | same path plus `/{prerequisite_id}` | Authenticated |
| `PATCH` | same path plus `/{prerequisite_id}/status` | `ADMIN`, `COMMITTEE_MEMBER` |
| `DELETE` | same path plus `/{prerequisite_id}` | `ADMIN`, `COMMITTEE_MEMBER`, `FACULTY` |

The list endpoint accepts an optional `course_id` filter with a
`direction` query parameter:

- `incoming` — edges where the course is the target (its prerequisites)
- `outgoing` — edges where the course is the prerequisite (its dependents)
- `both` (default) — either side

All writes require a `DRAFT` curriculum version.

## Validation Rules

Creating a prerequisite requires:

1. A `DRAFT` curriculum version.
2. Both courses active in that curriculum version.
3. Prerequisite course and target course differ (VR-PR-02).
4. No existing active relationship for the pair (VR-PR-03).
5. The new edge must not create a cycle (VR-PR-04).

### Cycle Detection

All active edges (`PROPOSED` or `APPROVED`) for the version are loaded
as an adjacency list over `prerequisite -> dependent`. A cycle exists
when the target course can reach the proposed prerequisite course by
traversal. The check runs before insert, so circular dependencies are
rejected, not merely detected after the fact.

## Review Workflow

```text
PROPOSED -> APPROVED
         -> REJECTED
```

- Only `PROPOSED` relationships can be approved or rejected
  (VR-PR-07).
- Approval records `approved_by` and `approved_at`; review comments
  may be attached to either decision.
- `REJECTED` is terminal; the relationship stays visible in the
  version for traceability but is inactive for verification use.
- Re-defining a rejected pair creates a fresh `PROPOSED` row because
  rejected relationships are not active.

## Exceptions

| Code | HTTP | Meaning |
| --- | --- | --- |
| `self_prerequisite` | 400 | A course was set as its own prerequisite |
| `prerequisite_exists` | 409 | Duplicate active relationship |
| `circular_prerequisite` | 409 | Edge would close a dependency cycle |
| `invalid_prerequisite_status` | 400 | Target status not APPROVED/REJECTED |
| `invalid_prerequisite_transition` | 409 | Illegal status transition |
| `curriculum_version_not_editable` | 409 | Version is not DRAFT |
| `prerequisite_conflict` | 409 | Integrity violation on insert |

## Audit Trail

All lifecycle actions write `audit_logs` entries with
`curriculum_version_id` context:

- `CREATE` on definition
- `STATUS_CHANGE` on approval or rejection
- `REMOVE` on soft removal

## Historical Integrity

- Non-draft versions cannot gain, change, or lose prerequisite edges.
- Removed rows remain stored, and previously generated verification
  results continue to reference the version they were run against.
