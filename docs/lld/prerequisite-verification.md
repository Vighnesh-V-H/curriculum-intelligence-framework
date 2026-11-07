# LLD: Prerequisite Verification (FR-12)

## Scope

This document covers prerequisite verification: analyzing the
prerequisite relationships and dependency chains of a curriculum
version, recording findings, and exposing verification runs to
authorized users.

Verification is independent of prerequisite management (FR-11). It
reports detected problems; it never modifies prerequisite data.

## Data Model

The verification reuses the shared tables from
`alembic/sql/001_initial_schema.sql` (section 8):

- `verification_runs` — one row per execution:
  `status` (`QUEUED`, `PROCESSING`, `COMPLETED`, `FAILED`),
  `requested_at` / `started_at` / `completed_at`, `error_message`,
  and a JSON `summary` (result, `total_findings`,
  `findings_by_severity`).
- `verification_findings` — one row per issue: `category`
  (`DEPENDENCY`, `STRUCTURAL`, ...), `severity` (`INFO` ... `CRITICAL`),
  `confidence` (0–1), `title`, `description`, `evidence`,
  `recommendation`, `requires_human_review` (always `TRUE` for this
  analyzer), `review_status` (defaults `PENDING`).
- `verification_finding_references` — traceability rows pointing at
  the `CURRICULUM_VERSION`, `COURSE`, or `PREREQUISITE` entities
  involved in the finding.

The SQLAlchemy `JSON` column type is used for `summary` so the model
works identically on PostgreSQL and SQLite test databases; the schema
specifies `JSONB` on PostgreSQL.

## API Endpoints

| Method | Path | Access |
| --- | --- | --- |
| `POST` | `/api/v1/curricula/{curriculum_id}/versions/{version_id}/verification-runs` | `ADMIN`, `COMMITTEE_MEMBER`, `REVIEWER` |
| `GET` | same path | Authenticated |
| `GET` | `/api/v1/verification-runs/{run_id}` | Authenticated |
| `GET` | `/api/v1/verification-runs/{run_id}/findings` | Authenticated |
| `GET` | `/api/v1/verification-findings/{finding_id}` | Authenticated |
| `PATCH` | `/api/v1/verification-findings/{finding_id}/review` | `ADMIN`, `COMMITTEE_MEMBER`, `REVIEWER` |

The findings list supports `category` and `severity` query filters.

## Analysis (FR-12-01..05)

The engine analyzes one curriculum version synchronously per run and
never mutates curriculum data.

Inputs:

- All courses of the version (excluding nothing — removed courses are
  included so that invalid references can be reported).
- All relationship rows with status `PROPOSED`, `APPROVED`, or
  `REJECTED`. Only `PROPOSED`/`APPROVED` rows form the *active* graph
  used for cycle, ordering, and coverage checks.

Checks:

1. **Self-references** (FR-12-04) — `CRITICAL`,
   one finding per offending row.
2. **Invalid references** (FR-12-04) — `HIGH` when a referenced
   course id is absent from the version; `MEDIUM` when the course
   exists but is `REMOVED`.
3. **Duplicate relationships** (FR-12-04) — `LOW` when more than one
   non-`REMOVED` row exists for the same pair (for example an
   `APPROVED` row plus a re-created `PROPOSED` row).
4. **Circular dependencies** (FR-12-03) — for each active edge, a BFS
   checks whether the target can reach the prerequisite without
   reusing that edge; each unique cycle is reported as `CRITICAL`
   with the full chain in `evidence` (cycles are canonicalized so
   rotations of the same loop report once).
5. **Course ordering** (FR-12-05) — `MEDIUM` when the target course
   is scheduled in an *earlier* semester than its prerequisite;
   `LOW` when both are scheduled in the same semester.
6. **Potential missing prerequisites** (FR-12-02) — `INFO` heuristic:
   an active course with outgoing prerequisite edges but no incoming
   edge, in a discipline (course-code letter prefix) that has earlier
   prerequisite-participating courses. Deterministic, evidence-cited,
   flagged for human review.

Nested cycles: the fast cycle avoidance lives in FR-11 (creation
is rejected), so cycle findings in verification mostly indicate data
corrupted outside the API or legacy imports.

## Run Lifecycle (FR-12-06)

1. `POST` creates the run in `PROCESSING` with `started_at` and one
   audit entry (`entity_type=verification_run`, `action=CREATE`).
2. The analyzer produces in-memory finding drafts.
3. Findings and references are persisted; the run becomes
   `COMPLETED`, stores `completed_at` and the JSON summary.
4. If analysis raises, the run becomes `FAILED` with
   `error_message`, a commit preserves the failure for traceability
   (EX-PV-09), and the error re-raises (HTTP 500).
5. If no findings are produced, the summary records `result=PASSED`
   with `total_findings=0` (EX-PV-01: the run still completes and is
   audited).

Runs are recorded per `curriculum_version` (BR-PV-01, BR-PV-06:
historical versions are verified against their own stored
relationships), satisfying BR-PV-07 traceability.

## Historical Integrity

- Analysis reads only data belonging to the selected version.
- Runs and findings are never updated by later curriculum changes;
  re-running creates a new run.
- Findings default to `review_status=PENDING` for the committee's
  human review workflow. Authorized reviewers can set a decision to
  `ACCEPTED`, `REJECTED`, or `MODIFIED`, optionally add comments, and
  record their identity and review timestamp. Each decision is audited
  with its previous and new values. Review decisions do not alter the
  curriculum or verification run.
