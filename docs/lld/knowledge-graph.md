# LLD: Curriculum Knowledge Graph

## Purpose and authority

PostgreSQL remains the authoritative store for curriculum content, version
history, authorization, and audit records. Neo4j is a derived, query-oriented
projection used for dependency and outcome-coverage exploration. The graph is
rebuildable from PostgreSQL and must never be used to approve, edit, or replace
relational curriculum data.

Each graph projection is isolated by one `curriculum_version_id`. Historical
versions are projected independently; a graph query for one version must never
mix nodes or relationships from another version. PostgreSQL UUIDs are the
stable graph identifiers. No graph entity receives an independent identity.

## Graph contract

Every node has `id` (the PostgreSQL UUID as a string) and
`curriculum_version_id` (except program-level identity nodes where noted).
Version-scoped nodes are keyed by `(id, curriculum_version_id)`. Mutable display
properties are projections, not identity: refreshes update them from the
relational source.

| Label | Relational source | Projected properties |
| --- | --- | --- |
| `Program` | `programs` | `id`, `code`, `name` |
| `Curriculum` | `curricula` | `id`, `program_id`, `regulation`, `academic_year`, `title` |
| `CurriculumVersion` | `curriculum_versions` | `id`, `curriculum_id`, `version_label`, `status` |
| `Semester` | `semesters` | `id`, `curriculum_version_id`, `semester_number`, `name` |
| `Course` | `courses` | `id`, `curriculum_version_id`, `course_code`, `course_name`, `credits`, `status` |
| `CourseOutcome` | `course_outcomes` | `id`, `curriculum_version_id`, `co_code`, `description`, `status` |
| `ProgramOutcome` | `program_outcomes` plus the version pinned by `curriculum_version_program_outcomes` | `id`, `program_id`, `curriculum_version_id`, `po_code`, `description`, `outcome_version_id` |
| `PEO` | `program_educational_objectives` plus the version pinned by `curriculum_version_peos` | `id`, `program_id`, `curriculum_version_id`, `peo_code`, `description`, `outcome_version_id` |

`ProgramOutcome` and `PEO` properties reflect the exact content version pinned
by the curriculum version, never whichever outcome version happens to be
currently approved. Keeping their identity IDs stable while carrying the pinned
version ID makes historical graph projections reproducible.

| Relationship | Relational source | Direction / properties |
| --- | --- | --- |
| `HAS_VERSION` | curriculum/version | `Curriculum -> CurriculumVersion` |
| `FOR_PROGRAM` | curriculum/program | `Curriculum -> Program` |
| `HAS_SEMESTER` | version/semester | `CurriculumVersion -> Semester` |
| `HAS_COURSE` | version/course | `CurriculumVersion -> Course` |
| `SCHEDULED_IN` | course/semester | `Course -> Semester` |
| `HAS_OUTCOME` | course/course outcome | `Course -> CourseOutcome` |
| `PREREQUISITE_OF` | `course_prerequisites` | prerequisite course `->` target course; `id`, `status` |
| `CONTRIBUTES_TO` | `co_po_mappings` and current mapping version | `CourseOutcome -> ProgramOutcome`; `id`, `status`, `mapping_version_id`, `level_code`, `level_value` |
| `USES_PO` | curriculum version/PO pin | `CurriculumVersion -> ProgramOutcome` |
| `USES_PEO` | curriculum version/PEO pin | `CurriculumVersion -> PEO` |

No `ProgramOutcome -> PEO` support edge is projected: the relational model has
no PO-to-PEO mapping entity or requirement. Likewise, topics, skills,
accreditation references, and document-derived concepts are out of scope until
their requirements and authoritative relational entities exist.

## Inclusion and status semantics

A projection includes every course and course outcome belonging to the selected
version, including removed/inactive records, so that status and historical
references remain inspectable. It includes the version's pinned PO/PEO
versions, including their exact descriptions. Course prerequisites with
`PROPOSED`, `APPROVED`, or `REJECTED` statuses and mappings with their current
version are represented with status properties. Queries that calculate active
dependency or coverage must explicitly filter to `PROPOSED`/`APPROVED` rows and
active source/target entities. `REJECTED`, `REMOVED`, and inactive records may
remain visible for traceability but must not count as active edges or coverage.

The graph is a snapshot for a curriculum version, not a cross-version merge.
`previous_version_id` can be used to identify the corresponding predecessor
version; the projection should not connect courses between versions unless a
future use case defines reliable identity matching (course codes alone are not
stable identities).

## Projection consistency and rebuild

PostgreSQL is the source of truth. Graph writes must be idempotent and keyed by
source UUIDs. The initial synchronization contract is **version-level
replace-and-rebuild**:

1. Read a consistent relational snapshot for the requested version.
2. Build the complete projection payload in memory.
3. In a Neo4j transaction, delete only graph data scoped to that version and
   write the replacement nodes and relationships.
4. Mark that version's projection as current only after the Neo4j transaction
   succeeds. A failed projection must remain retryable and must not affect
   PostgreSQL writes or other curriculum versions.

For changes initiated through the API, enqueue or invoke projection refresh
only after the PostgreSQL transaction commits. If the graph is unavailable,
the curriculum write still succeeds; the graph is marked stale and refreshed
on retry. Do not hold a PostgreSQL transaction open while performing network
I/O to Neo4j. Reconciliation must also support full rebuilds from PostgreSQL,
so missed refreshes and manual graph loss can be repaired.

The first implementation may use a durable projection-status/outbox table in
PostgreSQL to record version ID, source revision/updated timestamp, projection
status, attempt count, and last error. Status transitions and outbox creation
must commit atomically with the source mutation. A worker retries projection
idempotently; it marks the projection current only if the source version has
not changed since the snapshot was read, otherwise it schedules another
refresh. Direct request-time Neo4j writes without a durable retry mechanism are
not sufficient for consistency.

Reads requiring correctness must query PostgreSQL or verify the projection is
current first. Graph results are advisory and must be labeled with the
curriculum version and projection freshness. Verification remains read-only
and human review remains required.

## Constraints and indexes

Create uniqueness constraints for node labels on `(id, curriculum_version_id)`
for version-scoped labels. `Program` and `Curriculum` use unique `id`. Add
indexes for `curriculum_version_id`, `status`, and relationship traversal
patterns used by the query contract. Constraints/index setup is idempotent and
runs as graph service initialization or a deployment migration, not as a side
effect of ordinary API requests.

## API and current synchronization status

The authenticated endpoints are:

| Method | Path | Access | Behavior |
| --- | --- | --- | --- |
| `POST` | `/api/v1/curricula/{curriculum_id}/versions/{version_id}/graph/rebuild` | curriculum writers | Replace the graph projection from a relational snapshot |
| `GET` | `/api/v1/curricula/{curriculum_id}/versions/{version_id}/graph?limit=1000` | authenticated users | Return version-scoped nodes and relationships; `limit` is bounded to 1–5,000 |

`NEO4J_URI` enables graph operations. `NEO4J_USERNAME`, `NEO4J_PASSWORD`,
and `NEO4J_DATABASE` configure the driver. If Neo4j is not configured, graph
requests return `503 graph_unavailable`; the application can still serve
relational API requests.

Curriculum-affecting ORM writes enqueue a `graph_projection_jobs` row in the
same PostgreSQL transaction through session flush hooks. The outbox covers
curricula, versions, semesters, courses, course outcomes, prerequisites,
CO–PO mappings, and pinned PO/PEO identities and versions. A failure to persist
the job therefore rolls back the source write as well.

Run the retrying worker with `uv run python -m app.workers.graph_projection`;
`--once` processes one batch. It claims jobs with row locks, retries failures
up to five times, and stores only the exception type (not connection details)
in the job record. Neo4j replacement is idempotent. If the worker crashes
while a job is processing, it becomes eligible for reclaim after five minutes.

The rebuild endpoint remains available for manual repair. The graph GET
response includes `projection_status` and `is_current`; it is not current while
any pending or processing job exists or if the latest projection job failed.
Reads requiring authoritative, fresh data must still query PostgreSQL. A
completed rebuild can race with an in-flight relational transaction, but that
transaction's committed outbox job will keep the projection marked stale and
be processed by the worker.

## Frontend integration

The curriculum workspace exposes a **Knowledge graph** tab for the selected
curriculum version. It calls the authenticated graph GET operation when the tab
or version changes and renders the returned `nodes` and `relationships` without
transforming the source contract.

- The view is labeled with `projection_status` and `is_current`; a non-current
  snapshot is shown as stale rather than presented as authoritative.
- Nodes are grouped by label and can be filtered by label, searched, selected
  for one-hop relationship inspection, and opened in an accessible node and
  relationship table.
- Curriculum writers can trigger the rebuild endpoint and refresh the snapshot.
  Readers can refresh but cannot rebuild.
- A `503 graph_unavailable` response is rendered as explicit Neo4j setup
  guidance; the relational curriculum remains usable.
- Neo4j is optional at runtime. The frontend never uses the knowledge graph as
  the source of truth for curriculum edits, authorization, verification, or
  reports.

## Query contract (initial)

The read-only graph API is version-scoped, supporting:

- list courses with semester and prerequisite adjacency;
- dependency traversal with a bounded depth and cycle-safe query behavior;
- list each course outcome's active PO contribution and mapping strength;
- summary counts for courses, semesters, prerequisites, and outcome mappings.

Queries must enforce caller authorization using the same authenticated API
boundary as relational endpoints. Neo4j credentials are server-side only. Bound
traversal depth and result size; do not expose arbitrary Cypher to clients.

## Operational and security requirements

Neo4j is optional during development and can be disabled when its URI is not
configured. When enabled, use TLS-capable connection settings and a dedicated
least-privilege application account. Do not log credentials, raw syllabus
content, or sensitive document text. Health checks distinguish graph
unavailability from PostgreSQL health. Projection errors are observable and
retryable; they must not silently be treated as synchronized.
