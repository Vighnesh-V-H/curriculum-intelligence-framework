
# FR-12: Prerequisite Verification

## Description

The Prerequisite Verification module shall analyze prerequisite
relationships and course dependency chains within an academic
program and curriculum.

The system shall identify invalid, inconsistent, or problematic
prerequisite relationships that may affect the logical progression
of courses.

The verification results shall be available for curriculum
review and curriculum verification reporting. FR-12 defines only
prerequisite checks; curriculum structure and outcome-coverage checks
are defined separately in FR-14.

---

## Actors

### Primary Actors

- **Reviewer** — Reviews prerequisite verification results and identified problems.
- **Curriculum Committee Member** — Reviews prerequisite issues and
  determines whether corrective changes are required.

### Secondary Actors

- **Admin** — Views prerequisite verification results and manages
  prerequisite-related configuration where permitted.
- **Faculty / Instructor** — Views prerequisite verification results
  for courses within their scope.

---

## Functional Requirements

### FR-12-01: Analyze Prerequisite Chains

The system shall analyze prerequisite relationships within a
selected curriculum version.

The system shall construct and evaluate the dependency chain
between courses.

The analysis shall consider:

- Direct prerequisites
- Indirect prerequisites
- Course dependency chains
- Course ordering
- Circular dependencies

---

### FR-12-02: Detect Missing Prerequisites

The system shall identify potential missing prerequisites where
a course requires knowledge or a preceding course that is not
defined as a prerequisite.

The system shall record the identified issue as a verification
finding.

---

### FR-12-03: Detect Circular Prerequisites

The system shall detect circular dependencies in prerequisite
relationships.

For example:

```text
Course A
   ↓
Course B
   ↓
Course C
   ↓
Course A
```

The system shall report the courses involved in the circular
dependency.

---

### FR-12-04: Detect Invalid Prerequisite Relationships

The system shall identify invalid prerequisite relationships,
including:

- Self-referencing prerequisites
- References to non-existent courses
- References to courses outside the applicable curriculum
- Duplicate prerequisite relationships
- Relationships involving inactive courses where not permitted

---

### FR-12-05: Verify Course Ordering

The system shall analyze whether prerequisite courses are
positioned appropriately within the curriculum.

The system shall identify cases where a target course is scheduled
before its required prerequisite course.

---

### FR-12-06: Generate Prerequisite Verification Results

The system shall generate a verification result containing:

- Verification status
- Identified issues
- Courses involved
- Prerequisite relationships involved
- Issue type
- Issue severity where configured
- Explanation of the detected problem
- Verification timestamp

---

### FR-12-07: View Prerequisite Verification Results

The system shall allow authorized users to view prerequisite
verification results for a selected curriculum version.

The system shall support:

- Viewing all prerequisite issues
- Viewing individual issue details
- Filtering issues by type
- Filtering issues by severity where configured
- Viewing the affected course dependency chain

---

## Business Rules

### BR-PV-01: Valid Curriculum

Prerequisite verification shall be performed against a valid
academic program and curriculum version.

### BR-PV-02: Course Existence

Every course referenced in a prerequisite relationship must exist
within the applicable curriculum context.

### BR-PV-03: No Self-Dependency

A course shall not be considered a valid prerequisite for itself.

### BR-PV-04: No Circular Dependency

A valid prerequisite chain shall not contain a circular dependency.

### BR-PV-05: Course Ordering

A prerequisite course should be available before the dependent
course within the applicable curriculum structure.

### BR-PV-06: Historical Integrity

Verification of a historical curriculum version shall use the
prerequisite relationships applicable to that version.

Changes to current prerequisite relationships shall not modify
historical verification results.

### BR-PV-07: Verification Traceability

Each verification result shall identify the curriculum version
and prerequisite relationships used during the analysis.

### BR-PV-08: Auditability

Prerequisite verification executions and generated results shall
be recorded for audit and traceability purposes.

---

## Preconditions

For performing prerequisite verification:

- The user must be authenticated.
- The user must have the required permission.
- The academic program must exist.
- The curriculum version must exist.
- The selected curriculum must contain the relevant courses.
- Prerequisite relationships must be available for analysis where
  applicable.

---

## Postconditions

### On Successful Verification

- The prerequisite relationships are analyzed.
- Dependency chains are evaluated.
- Detected prerequisite problems are recorded.
- A verification result is generated.
- The verification execution is recorded in the audit history.

### On No Problems Found

- The system shall record a successful prerequisite verification.
- No prerequisite issues shall be reported for the analyzed
  curriculum version.

### On Problems Found

- Each detected issue shall be recorded.
- The affected courses and relationships shall be identified.
- The verification result shall indicate that prerequisite
  problems were detected.

---

## Dependencies

This requirement depends on:

- User and Role Management
- Academic Program Management
- Course Management
- Curriculum Management
- Prerequisite Management

Prerequisite Verification shall be used by:

- Curriculum Verification
- Verification Reporting
- Curriculum Review
- Accreditation Analysis

---

## Validation Rules

### VR-PV-01: Curriculum Validation

- The selected academic program must exist.
- The selected curriculum version must exist.
- The curriculum version must contain the courses being analyzed.

### VR-PV-02: Prerequisite Reference Validation

- The prerequisite course must exist.
- The target course must exist.
- Both courses must be valid within the applicable curriculum
  context.

### VR-PV-03: Self-Reference Validation

The system shall identify a prerequisite relationship where the
prerequisite course and target course are the same.

### VR-PV-04: Circular Dependency Validation

The system shall identify cycles within the prerequisite dependency
graph.

### VR-PV-05: Course Ordering Validation

The system shall identify cases where a prerequisite course is
scheduled after the course that depends on it.

### VR-PV-06: Historical Version Validation

The verification process shall use the prerequisite relationships
applicable to the selected curriculum version.

### VR-PV-07: Verification Result Validation

Each verification finding shall contain sufficient information to
identify the affected course and prerequisite relationship.

---

## Exceptions / Edge Cases

### EX-PV-01: No Prerequisites Defined

If no prerequisite relationships are defined for the selected
curriculum, the system shall complete the verification and report
that no prerequisite relationships were available for analysis.

### EX-PV-02: Missing Course Reference

If a prerequisite relationship references a course that does not
exist, the system shall report the relationship as an invalid
prerequisite.

### EX-PV-03: Self-Prerequisite

If a course is defined as its own prerequisite, the system shall
report a self-dependency issue.

### EX-PV-04: Circular Dependency

If the prerequisite graph contains a cycle, the system shall
report the courses involved in the circular dependency.

### EX-PV-05: Incorrect Course Ordering

If a prerequisite course is scheduled after its dependent course,
the system shall report a course ordering issue.

### EX-PV-06: Inactive Course

If a prerequisite relationship references an inactive course,
the system shall report the relationship according to the
configured verification rules.

### EX-PV-07: Historical Curriculum

If verification is performed on a historical curriculum version,
the system shall use the prerequisite relationships associated
with that version rather than the current relationships.

### EX-PV-08: Incomplete Curriculum Data

If required curriculum or course information is unavailable,
the system shall mark the verification as incomplete and identify
the missing information.

### EX-PV-09: Verification Execution Failure

If the verification process cannot be completed because of a
system or data-processing error, the system shall record the
failure and provide an appropriate error status.

---

## Outcome

Upon successful implementation of this requirement:

- Prerequisite relationships shall be analyzed for the selected
  curriculum version.
- Direct and indirect prerequisite chains shall be evaluated.
- Missing or invalid prerequisite relationships shall be identified
  where applicable.
- Circular prerequisite dependencies shall be detected.
- Incorrect course ordering shall be identified.
- Verification findings shall identify the affected courses and
  prerequisite relationships.
- Verification results shall be available to authorized users.
- Historical curriculum versions shall be verified using their
  applicable prerequisite relationships.
- Prerequisite verification executions and results shall be
  traceable and auditable.

## Notes

Prerequisite Verification shall be independent of Prerequisite
Management.

Prerequisite Management is responsible for defining and maintaining
prerequisite relationships, while Prerequisite Verification is
responsible for analyzing those relationships and identifying
potential problems.

Example:

```text
Programming Fundamentals
          ↓
     Data Structures
          ↓
       Algorithms
          ↓
   Advanced Algorithms
```

The verification process shall analyze the dependency chain and
identify problems such as:

```text
Circular Dependency:

Course A
   ↓
Course B
   ↓
Course C
   ↓
Course A
```

The verification module shall report detected problems rather than
automatically modifying prerequisite relationships.

```
```