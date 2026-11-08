# LLD: Curriculum Structure and Outcome Verification (FR-14)

## Scope and composition

`VerificationService` runs the existing prerequisite analyzer (FR-12) and the
following deterministic curriculum checks in one run. The analyzer is
read-only and advisory; findings are persisted through the existing
`verification_runs`, `verification_findings`, and
`verification_finding_references` tables. No schema change is required for the
initial checks because the existing category and entity-reference enums
already include `STRUCTURAL`, `OUTCOME`, `SEMESTER`, `COURSE_OUTCOME`,
`PROGRAM_OUTCOME`, and `CO_PO_MAPPING`.

## Input snapshot

- The selected `CurriculumVersion`, its semesters, active and removed courses,
  and course outcomes.
- PO and PEO identities plus the exact PO/PEO versions pinned to the selected
  curriculum version. Only PO coverage is evaluated in this phase.
- CO–PO mappings for the selected version and their mapping-version history.

All reads are constrained by curriculum version. A mapping contributes only if
its logical mapping is `ACTIVE`, its latest mapping version is `APPROVED`, its
CO is `ACTIVE`, and its PO is active and pinned to the selected version.

## Checks and rules

| Check code | Condition | Category / severity | Evidence and references |
| --- | --- | --- | --- |
| `EMPTY_SEMESTER` | Active semester contains no active course | `STRUCTURAL` / `INFO` | Semester number/name and semester reference |
| `COURSE_WITHOUT_CO` | Active course has no active CO | `OUTCOME` / `MEDIUM` | Course code and course reference |
| `CO_WITHOUT_APPROVED_PO` | Active CO has no approved active mapping to a pinned active PO | `OUTCOME` / `MEDIUM` | CO code, course code, and CO/course references |
| `PO_WITHOUT_APPROVED_CO` | Pinned active PO has no incoming approved active mapping from an active CO | `OUTCOME` / `MEDIUM` | PO code and PO reference |

Severity reflects an advisory review priority, not accreditation compliance.
Evidence should include stable check codes and concrete codes/IDs, and all
findings require a human decision. The summary adds `findings_by_category`,
`credit_totals_by_semester`, and an `analyzers` list while preserving the
existing run result, total, and severity counts.

## Exclusions

No institutional credit/semester target exists, so the analyzer reports
semester credits but does not label totals compliant or noncompliant. Topic,
skill, accreditation, and industry checks are deferred because the current
relational model has no governed reference data for those concepts. PEOs are
included in the projection contract but are not used as coverage criteria
until a PO-to-PEO relationship is defined.

## Failure and history

A check failure follows the established FR-12 run failure behavior. It records
a failed run and does not persist partial findings. Repeated runs are separate
immutable records, and historical versions use their own pinned outcome and
mapping versions.
