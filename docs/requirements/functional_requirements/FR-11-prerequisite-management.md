# FR-11: Prerequisite Management

## Description

The Prerequisite Management module shall allow authorized users
to define, view, update, and remove prerequisite relationships
between courses within an academic program and curriculum.

A prerequisite relationship specifies that a student is expected
to complete or have knowledge of one course before taking another
course.

The prerequisite relationships shall be available for curriculum
design and curriculum verification.

---

## Actors

### Primary Actors

- **Admin** — Creates, updates, and manages prerequisite relationships.
- **Faculty / Instructor** — Defines and views prerequisite relationships
  where permitted.
- **Curriculum Committee Member** — Reviews and approves prerequisite
  changes.

### Secondary Actors

- **Reviewer** — Views prerequisite relationships during curriculum
  verification.

---

## Functional Requirements

### FR-11-01: Define Prerequisites

The system shall allow an authorized user to define a prerequisite
relationship between courses.

The user shall provide:

- Prerequisite course
- Target course
- Associated academic program
- Associated curriculum version

The system shall validate the relationship before storing it.

---

### FR-11-02: View Prerequisites

The system shall allow authorized users to view prerequisite
relationships associated with courses.

The system shall support:

- Viewing prerequisites of a course
- Viewing courses that depend on a particular course
- Viewing all prerequisite relationships within a curriculum

---

### FR-11-03: Update Prerequisites

The system shall allow authorized users to update permitted
attributes of an existing prerequisite relationship.

The system shall maintain the history of changes where versioning
is applicable.

---

### FR-11-04: Remove Prerequisites

The system shall allow authorized users to remove a prerequisite
relationship that is no longer applicable.

Removal shall not alter historical curriculum versions or
historical verification records.

---

### FR-11-05: Validate Prerequisite Relationships

The system shall validate prerequisite relationships to ensure
that they do not create invalid course dependencies.

The system shall detect:

- Self-referencing prerequisites
- Circular prerequisite relationships
- Invalid course references
- Duplicate prerequisite relationships

---

### FR-11-06: Review Prerequisite Changes

The system shall allow authorized Curriculum Committee Members
to review proposed prerequisite changes.

A reviewer shall be able to:

- Review the proposed change
- Approve the change
- Reject the change
- Provide review comments

Only approved changes shall become effective where approval is
required by the configured workflow.

---

## Business Rules

### BR-PR-01: Valid Courses

Both the prerequisite course and target course must exist in the
associated curriculum.

### BR-PR-02: No Self-Prerequisite

A course shall not be allowed to be its own prerequisite.

### BR-PR-03: No Circular Dependency

The system shall not allow prerequisite relationships that create
a circular dependency between courses.

### BR-PR-04: Duplicate Relationship

The same prerequisite relationship shall not be stored more than
once within the same curriculum version.

### BR-PR-05: Curriculum Consistency

The prerequisite relationship shall belong to the same applicable
academic program and curriculum version unless cross-program
relationships are explicitly supported.

### BR-PR-06: Authorization

Only users with the required permissions shall be allowed to
create, update, remove, or approve prerequisite relationships.

### BR-PR-07: Historical Data

Removing or modifying a prerequisite shall not alter historical
curriculum versions or previously generated verification results.

### BR-PR-08: Auditability

Creation, modification, removal, approval, and rejection of
prerequisite relationships shall be recorded in the audit history.

---

## Preconditions

For creating or modifying a prerequisite relationship:

- The user must be authenticated.
- The user must have the required permission.
- The prerequisite course must exist.
- The target course must exist.
- The associated curriculum version must exist.
- Required prerequisite information must be provided.

---

## Postconditions

### On Successful Creation

- A prerequisite relationship is stored.
- The relationship is associated with the appropriate curriculum.
- The creation action is recorded in the audit history.

### On Successful Update

- The permitted prerequisite information is updated.
- Historical information is preserved where versioning is applicable.
- The update is recorded in the audit history.

### On Removal

- The prerequisite relationship is removed from active use.
- Historical references remain valid.
- The removal action is recorded in the audit history.

### On Approval

- The proposed prerequisite relationship becomes approved.
- The approved relationship becomes effective according to the
  configured workflow.
- The approval action is recorded.

---

## Dependencies

This requirement depends on:

- User and Role Management
- Academic Program Management
- Course Management
- Curriculum Management

Prerequisite relationships shall be used by:

- Curriculum Verification
- Curriculum Dependency Analysis
- Curriculum Reporting

---

## Validation Rules

### VR-PR-01: Course Validation

- The prerequisite course must exist.
- The target course must exist.
- Both courses must be valid for the selected curriculum context.

### VR-PR-02: Self-Reference Validation

The prerequisite course and target course shall not be the same
course.

### VR-PR-03: Duplicate Validation

The system shall reject a prerequisite relationship if the same
relationship already exists for the selected curriculum version.

### VR-PR-04: Circular Dependency Validation

The system shall reject a prerequisite relationship if adding it
creates a circular dependency in the course prerequisite graph.

### VR-PR-05: Curriculum Validation

The associated curriculum version must exist and be applicable
to both courses.

### VR-PR-06: Authorization Validation

Only users with the required permission shall be allowed to
create, update, remove, or approve prerequisite relationships.

---

## Exceptions / Edge Cases

### EX-PR-01: Course Not Found

If either the prerequisite course or target course does not exist,
the system shall reject the operation.

### EX-PR-02: Self-Prerequisite

If a user attempts to make a course its own prerequisite, the
system shall reject the operation.

### EX-PR-03: Circular Dependency

If adding a prerequisite creates a circular dependency, the
system shall reject the operation and identify the invalid
dependency where applicable.

### EX-PR-04: Duplicate Prerequisite

If the same prerequisite relationship already exists, the system
shall reject the duplicate relationship.

### EX-PR-05: Invalid Curriculum Context

If the courses do not belong to the selected curriculum context,
the system shall reject the operation.

### EX-PR-06: Historical Prerequisite

If a prerequisite relationship is referenced by a historical
curriculum or verification result, the system shall preserve the
historical record.

### EX-PR-07: Concurrent Modification

If multiple users attempt to modify the same prerequisite
relationship simultaneously, the system shall prevent unintended
overwriting of changes.

---

## Outcome

Upon successful implementation of this requirement:

- Authorized users shall be able to define prerequisite
  relationships between courses.
- Users shall be able to view, update, and remove prerequisite
  relationships according to their permissions.
- Invalid prerequisite relationships shall be detected and
  prevented.
- Circular and self-referencing dependencies shall be prevented.
- Historical prerequisite information shall remain preserved.
- Approved prerequisite relationships shall be available to the
  curriculum verification process.
- Prerequisite management operations shall be auditable.

## Notes

Prerequisite relationships shall be represented as directed
relationships between courses.

Example:

Programming Fundamentals
        ↓
Data Structures
        ↓
Algorithms
        ↓
Machine Learning

The prerequisite relationship shall indicate that the source
course is a prerequisite for the target course.

The system may use a graph-based representation to support
dependency analysis and circular dependency detection.