# FR-14: Curriculum Structure and Outcome Verification

## Description

The system shall provide advisory checks on curriculum structure and outcome
coverage for a selected curriculum version. This requirement complements
FR-12, which remains responsible for prerequisite-chain verification.

## Actors

- Curriculum committee member or reviewer: runs verification and reviews findings.
- Authorized faculty: views verification results for curriculum versions they can access.

## Functional behavior

A verification run shall analyze the selected version without modifying
curriculum, course, outcome, prerequisite, or mapping records. It shall persist
findings with category, severity, confidence, explanation, evidence,
recommendation, and references to affected entities. All findings are advisory
and require human review.

The initial deterministic checks shall:

1. Identify active semesters with no active courses (`STRUCTURAL`, `INFO`).
2. Identify active courses with no active course outcomes (`OUTCOME`, `MEDIUM`).
3. Identify active course outcomes with no approved active CO–PO mapping pinned
to an active program outcome for this curriculum version (`OUTCOME`, `MEDIUM`).
4. Identify pinned active program outcomes with no approved active CO–PO
mapping from an active course outcome (`OUTCOME`, `MEDIUM`).
5. Count current credit totals by semester in the run summary, without judging
those totals against an institutional target until a target/configuration
source is defined.

Existing prerequisite checks in FR-12 shall run as part of the same
curriculum verification run. A finding must identify its analyzer/check code
in its evidence metadata or stable title so repeated runs can be compared.

## Business rules

- The analysis reads only records belonging to the selected curriculum version
  and the outcome versions pinned by that version.
- A mapping counts toward coverage only when the mapping is active, its latest
  mapping version is `APPROVED`, the course outcome is active, and the target PO
  is pinned and active for the selected version.
- Draft/proposed mappings remain visible to users but do not count as approved
  coverage.
- Removed courses, inactive course outcomes, inactive POs, and unpinned POs do
  not count toward coverage. Existing prerequisite validation may still report
  removed/invalid references under FR-12.
- The system shall not auto-approve findings, create mappings, change course
  allocation, or make other curriculum edits.
- Findings and run inputs/results are immutable snapshots; a later curriculum
  edit requires a new run.

## Deferred verification scope

Topic overlap/progression, skills and competency coverage, configurable credit
or semester balance thresholds, industry alignment, and accreditation/OBE
comparisons are not included in the initial analyzer. They require explicit
institutional rules and/or authoritative reference datasets that the current
schema does not provide. They shall be added only with defined data ownership,
validation rules, provenance, and evaluation criteria.

## Acceptance criteria

- Running verification against a valid curriculum version records both FR-12
  prerequisite findings and the deterministic structure/outcome findings.
- Every finding has evidence and traceable entity references and defaults to
  `PENDING` human review.
- The run summary reports finding totals by severity and category and credit
  totals by semester.
- A curriculum with no prerequisites completes successfully; its structural
  and outcome checks still run.
- Historical versions are analyzed against their own courses, pinned outcomes,
  and mapping versions.
- Analysis failure is recorded as a failed run and does not mutate academic data.
