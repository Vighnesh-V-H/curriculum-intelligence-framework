# LLD: Prerequisite Verification (FR-12)

## Scope

This document covers the prerequisite analyzer (FR-12): analyzing
prerequisite relationships and dependency chains of a curriculum
version. It runs as one analyzer within the shared verification-run
workflow, alongside the structure and outcome checks defined in
[`curriculum-verification.md`](curriculum-verification.md).

Verification is independent of prerequisite management (FR-11). It
reports detected problems; it never modifies prerequisite or
curriculum data.

## Data Model

The verification reuses the shared tables from
`alembic/sql/001_initial_schema.sql` (section 8):

- `verification_runs` — one row per execution:
  `status` (`QUEUED`, `PROCESSING`, `COMPLETED`, `FAILED`),
  `requested_at` / `started_at` / `completed_at`, `error_message`,
  and a JSON `summary` (result, `total_findings`,
  `findings_by_severity`, `findings_by_category`, analyzer statistics,
  and `input_fingerprint`).
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
| `GET` | `/api/v1/verification-runs/{run_id}/report` | Authenticated |
| `GET` | `/api/v1/verification-findings/{finding_id}` | Authenticated |
| `PATCH` | `/api/v1/verification-findings/{finding_id}/review` | `ADMIN`, `COMMITTEE_MEMBER`, `REVIEWER` |

The findings list supports `category` and `severity` query filters. The report
endpoint groups filtered findings by `category`, `severity`, or `review_status`
(`group_by`, default `category`) and returns total counts across all three
dimensions, plus the run summary. Optional `category`, `severity`, and
`review_status` filters apply before grouping.

## Analysis (FR-12-01..05)

The engine analyzes one curriculum version synchronously per run and
never mutates curriculum data.

Inputs:

- All courses of the version (excluding nothing — removed courses are
  included so that invalid references can be reported).
- All relationship rows with status `PROPOSED`, `APPROVED`, or
  `REJECTED`. Only `PROPOSED`/`APPROVED` rows form the *active* graph
  used for cycle, ordering, and coverage checks.

Checks (the stable code is the first token of every `evidence` value):

1. **Self-references** (FR-12-04) — `SELF_PREREQUISITE`, `CRITICAL`,
   one finding per offending row.
2. **Invalid references** (FR-12-04) — `MISSING_PREREQUISITE_COURSE`
   (`HIGH`) when a referenced course id is absent from the version;
   `REMOVED_PREREQUISITE_COURSE` (`MEDIUM`) when the course exists but
   is not `ACTIVE`.
3. **Duplicate relationships** (FR-12-04) — `DUPLICATE_PREREQUISITE`,
   `LOW`, when more than one analyzed row exists for the same pair (for
   example an `APPROVED` row plus a re-created `PROPOSED` row).
4. **Circular dependencies** (FR-12-03) — `CIRCULAR_PREREQUISITE`,
   `CRITICAL`. For each active edge, a BFS checks whether the target can
   reach the prerequisite without reusing that edge; each unique cycle is
   reported with the full chain in `evidence`. Cycles are canonicalized so
   rotations of the same loop report once.
5. **Course ordering** (FR-12-05) — `PREREQUISITE_OUT_OF_ORDER`,
   `MEDIUM`, when the target course is scheduled in an *earlier*
   semester than its prerequisite; `PREREQUISITE_SAME_SEMESTER`, `LOW`,
   when both are scheduled in the same semester.
6. **Potential missing prerequisites** (FR-12-02) —
   `MISSING_PREREQUISITE_CANDIDATE`, `INFO` heuristic: an active course
   with outgoing prerequisite edges but no incoming edge, in a discipline
   (course-code letter prefix) that has earlier prerequisite-participating
   courses. Deterministic, evidence-cited, flagged for human review.
7. **Transitive redundant edges** — `TRANSITIVE_PREREQUISITE`, `INFO`.
   For each direct active edge, the analyzer searches for an alternative
   path from the prerequisite to the target without using that edge. When
   found, the direct edge is redundant and the finding records both the
   direct edge and the full alternative path. The recommendation is
   advisory: keep the edge only if an explicit placement or validation rule
   requires it.

Every check is deterministic and read-only. No check auto-corrects a
relationship.

### Chain summary

`_analyze_prerequisite_chains()` also returns graph statistics used by the
verification summary:

- `edge_count`;
- `root_courses` (no incoming active edge);
- `leaf_courses` (no outgoing active edge);
- `isolated_courses` (neither incoming nor outgoing);
- `longest_chain`, `longest_chain_length`, and `longest_chain_semesters`
  computed with cycle-safe depth-first traversal;
- `transitive_redundant_edges` count.

These values are descriptive. `longest_chain` reports the first longest path
found; it is not a uniqueness claim.

### Cycle prevention vs detection

Cycle avoidance during prerequisite creation lives in FR-11 (creation is
rejected), so cycle findings in verification mostly indicate data corrupted
outside the API or legacy imports. Verification still detects them because it
must analyze historical and imported versions independently.

## Run Lifecycle (FR-12-06)

1. `POST` creates the run in `PROCESSING` with `started_at` and one
   audit entry (`entity_type=verification_run`, `action=CREATE`).
2. The analyzer loads a version snapshot and produces in-memory
   finding drafts. The snapshot computes a SHA-256 input fingerprint.
3. Findings and references are persisted; the run becomes
   `COMPLETED`, stores `completed_at` and the JSON summary, including
   `input_fingerprint` and `input_fingerprint_version`.
4. If analysis raises, the run becomes `FAILED` with
   `error_message`, a commit preserves the failure for traceability
   (EX-PV-09), and the error re-raises (HTTP 500). Partial findings
   are not persisted.
5. If no findings are produced, the summary records `result=PASSED`
   with `total_findings=0` (EX-PV-01: the run still completes and is
   audited).

Runs are recorded per `curriculum_version` (BR-PV-01, BR-PV-06:
historical versions are verified against their own stored
relationships), satisfying BR-PV-07 traceability.

## Staleness

The run response exposes `input_fingerprint` and `is_stale`. The service
recomputes the fingerprint of the current snapshot when listing or reading
runs. A completed run is stale when its stored fingerprint differs from the
current inputs. Staleness is informational: the earlier run and its findings
remain immutable, and the user starts a new run to analyze the changed data.

Fingerprint inputs for the prerequisite analyzer include all analyzed
prerequisite rows (`PROPOSED`, `APPROVED`, `REJECTED`), their statuses and
review comments, and the courses/semesters they reference. A curriculum change
that does not affect any fingerprint input does not mark a run stale.

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
