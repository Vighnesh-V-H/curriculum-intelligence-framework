# FR-14: Curriculum Structure and Outcome Verification

## Description

The system shall provide advisory, version-scoped verification of a curriculum.
A single verification run shall combine prerequisite analysis (FR-12) with
curriculum structure, semester and credit distribution, topic overlap and
progression, outcome coverage, and comparison against governed OBE,
accreditation, industry, and institutional references.

The verifier shall not modify curriculum, course, outcome, prerequisite,
mapping, or reference data. Every finding is advisory, carries evidence and a
confidence value, and requires human review.

---

## Actors

### Primary Actors

- **Curriculum Committee Member** — runs verification and reviews findings.
- **Reviewer** — reviews verification results and decides whether corrective
  action is required.

### Secondary Actors

- **Admin** — manages governed verification references and views results.
- **Faculty / Instructor** — views verification results for curriculum versions
  within their scope.

---

## Functional Requirements

### FR-14-01: Run Version-Scoped Verification

The system shall run verification against a selected curriculum version and
analyze only records belonging to that version, including the exact outcome and
mapping versions pinned to it.

Prerequisite verification from FR-12 shall execute as part of the same run.
The run shall record its status, requesting user, timestamps, summary, and any
failure message.

### FR-14-02: Verify Prerequisite Chains and Sequencing

The system shall analyze direct and transitive prerequisite chains, including:

- Self-referencing prerequisites.
- References to missing or removed courses.
- Duplicate prerequisite relationships.
- Circular dependencies.
- Courses scheduled before their prerequisite or in the same semester.
- Potential missing prerequisites.
- Redundant direct edges already implied by a longer prerequisite path.
- Root, leaf, isolated, and longest prerequisite chains.

Detailed prerequisite behavior and acceptance criteria remain defined in FR-12.

### FR-14-03: Analyze Semester Structure and Credit Distribution

The system shall evaluate the curriculum structure and report:

- Semesters with no active courses.
- Gaps in the semester sequence.
- Curriculum versions with no active courses.
- Courses with invalid credit values.
- Total credits, credits per semester, and credits by course type.
- Course counts per semester and per course type.
- Average and range of semester credit loads.

Credit and distribution findings that require an institutional target shall be
evaluated only when a governed institutional reference defines that target.

### FR-14-04: Detect Topic Overlap and Distinguish Progression

The system shall compare active courses using deterministic evidence from course
names, descriptions, syllabi, and active course outcomes.

The system shall distinguish:

- **Redundancy** — courses with substantial topic and title overlap that are not
  connected by a prerequisite path.
- **Progression** — courses in later semesters where the earlier course is a
  transitive prerequisite of the later course.
- **Unverified progression** — same-discipline or higher-level courses with
  topic overlap but no prerequisite path. These shall be reported at
  `INFO` severity for human confirmation.
- **Cross-discipline overlap** — overlapping content across course-code
  disciplines, reported only when the evidence is strong enough to warrant
  review.

Redundancy findings shall not be raised when a legitimate prerequisite
progression already explains the overlap.

### FR-14-05: Verify Outcome Coverage

The system shall evaluate outcome-based coverage and report:

- Active courses with no active course outcomes.
- Active course outcomes with no approved active mapping to a program outcome
  pinned to the selected version.
- Pinned active program outcomes with no approved active course-outcome
  mapping.

A mapping counts toward coverage only when the mapping is active, its latest
mapping version is `APPROVED`, the course outcome is active, and the target
program outcome is active and pinned to the selected version.

### FR-14-06: Compare Governed References

The system shall compare curriculum evidence against active governed references
configured for the institution or the curriculum's program. Supported reference
types are:

- **Institutional** — total credits, semester credits, semester count, credits
  by course type, and course-type credit share.
- **OBE** — required program outcomes and PEOs, program-outcome coverage, and
  approved CO–PO mapping coverage.
- **Accreditation** — criterion-specific required program outcomes, required
  course types, program-outcome coverage, and approved mapping coverage.
- **Industry** — required skills evidenced by configured keywords in course
  names, descriptions, syllabi, and outcomes, with minimum course counts and
  overall required-skill coverage.

Reference rules shall be validated against the schema for their type. A global
reference applies institution-wide. A program-specific reference with the same
type and code overrides the global reference for that program. When multiple
versions of the same scoped reference exist, the newest effective version shall
be used.

Reference comparison shall run only when at least one applicable active
reference exists. The system shall not invent default targets.

### FR-14-07: Produce Explainable Findings

Each finding shall record:

- Category (`DEPENDENCY`, `STRUCTURAL`, `CONTENT`, `OUTCOME`,
  `INDUSTRY_ALIGNMENT`, or `ACCREDITATION_OBE`).
- Severity (`INFO`, `LOW`, `MEDIUM`, `HIGH`, or `CRITICAL`).
- Confidence between 0 and 1.
- A stable check code in its evidence.
- A human-readable description and recommendation.
- References to the affected curriculum version, courses, semesters,
  prerequisites, course outcomes, program outcomes, and governed references.
- `requires_human_review = true` and a default review status of `PENDING`.

### FR-14-08: Summarize the Run

The run summary shall report the overall result, total findings, findings by
severity and category, prerequisite graph statistics, structure and credit
statistics, topic-overlap statistics, reference-comparison results, and the
input fingerprint used to detect staleness.

### FR-14-09: Detect Stale Results

The system shall compute a deterministic fingerprint of the verification inputs.
When the current inputs differ from the fingerprint stored with a completed run,
the run shall be reported as stale and the user shall be able to start a new
run. Historical runs and their findings shall remain unchanged.

Fingerprint inputs include the curriculum version metadata, semesters, courses,
course outcomes, analyzed prerequisite rows, pinned PO/PEO versions, CO–PO
mappings and mapping versions, and applicable governed references.

### FR-14-10: Visualize Verification Results

The system shall provide an interactive, read-only visual representation of the
verified curriculum, including semester placement, course severity, prerequisite
edges, optional topic-overlap links, and selected-finding details. An accessible
table or list shall present the same information without requiring interaction
with the visualization.

### FR-14-11: Support Repeatable Verification

Authorized users shall be able to run verification again after curriculum data
or governed references change. Each run shall be stored as a separate immutable
record. A failed run shall be recorded with an error status and shall not persist
partial findings or mutate academic data.

---

## Business Rules

### BR-CV-01: Advisory Only

Findings are recommendations. The system shall not auto-approve findings,
approve mappings, change course allocation, or make any curriculum edit.

### BR-CV-02: Input Scope

The analysis shall read only records belonging to the selected curriculum
version and the outcome versions pinned by that version.

### BR-CV-03: Approved Coverage

Draft or proposed mappings remain visible to users but do not count as approved
outcome coverage. Removed courses, inactive course outcomes, inactive program
outcomes, and unpinned program outcomes do not count toward coverage.

### BR-CV-04: Governed Reference Ownership

Reference targets and keyword sets must be explicitly configured and validated.
The system shall not infer accreditation, industry, or institutional targets.

### BR-CV-05: Program Override

For the same reference type and code, a program-specific reference overrides a
global reference. The system shall not evaluate both versions in one run.

### BR-CV-06: Immutability and Historical Integrity

Completed runs, findings, and their input fingerprints are immutable snapshots.
A later curriculum edit requires a new run. Historical versions are verified
against their own data and pinned outcome/mapping versions.

### BR-CV-07: Traceability

Every finding shall contain evidence and at least one entity reference. Stable
check codes shall allow repeated runs to be compared.

### BR-CV-08: Human Review

Every finding defaults to `PENDING` review. Authorized reviewers may accept,
reject, or modify a finding and record comments; review decisions do not alter
the curriculum or the original run.

---

## Preconditions

- The user is authenticated and authorized for the curriculum version.
- The curriculum, version, and relevant academic records exist.
- Governed references are configured when reference comparison is expected.

---

## Postconditions

### On Successful Verification

- Prerequisite, structure, credit, topic, outcome, and applicable reference
  checks are evaluated.
- Findings with evidence and traceable references are persisted.
- The run summary and input fingerprint are stored.
- The execution is recorded in the audit history.

### On No Findings

- The run completes with `result = PASSED` and `total_findings = 0`.

### On Findings

- The run completes with `result = ISSUES_FOUND`.
- Findings are grouped by category and severity in the summary.

### On Failure

- The run is marked `FAILED` with an error message.
- No partial findings are persisted and academic data is unchanged.

---

## Acceptance Criteria

- A verification run records both FR-12 prerequisite findings and FR-14
  structure, topic, outcome, and reference findings in one version-scoped run.
- Every finding has evidence, a stable check code, traceable entity references,
  and defaults to `PENDING` human review.
- The run summary reports finding totals by severity and category, prerequisite
  chain statistics, credit and distribution statistics, topic-overlap counts,
  and reference-comparison results.
- Topic analysis distinguishes redundancy from legitimate prerequisite
  progression and reports unverified progression for review.
- Reference checks run only for active governed references and honor program
  overrides over global references.
- A curriculum with no prerequisites completes successfully; its structural,
  topic, outcome, and reference checks still run.
- Historical versions are analyzed against their own courses, pinned outcomes,
  mappings, prerequisites, and applicable references.
- A completed run becomes stale when its input fingerprint no longer matches the
  current version data.
- The verification map displays course and edge severity with an accessible
  table alternative.
- Analysis failure is recorded as a failed run and does not mutate academic data.

---

## Exclusions

- The verifier does not provide accreditation certification or legal compliance
  determinations; it compares evidence against configured references only.
- Topic similarity is lexical and deterministic. It does not use embedding
  models or LLM judgments, and it cannot detect conceptual overlap that shares
  no vocabulary.
- Industry skill evidence is keyword-based and depends on the quality of the
  configured keywords.
- Credit and distribution checks do not define institutional targets; they
  evaluate targets only when a governed reference provides one.
- The verifier does not modify curriculum data or resolve findings
  automatically.

## Dependencies

This requirement depends on:

- User and Role Management
- Academic Program Management
- Course and Curriculum Management
- Prerequisite Management and Verification (FR-11, FR-12)
- Course Outcome, Program Outcome, PEO, and CO–PO Mapping Management
  (FR-08, FR-09, FR-10)
- Governed verification reference management

It is used by curriculum review, verification reporting, and accreditation
analysis.
