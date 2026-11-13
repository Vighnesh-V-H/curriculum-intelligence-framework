# FR-08: Program Outcome Management

> **Current workflow override:** POs are created and edited immediately by
> authorized administrators, committee members, and faculty. No draft/proposed/
> approval gate or user-visible PO version history is required. Older approval
> and versioning clauses below are retired for the current product behavior.

## Description

The Program Outcome Management module shall allow authorized users
to create, view, update, deactivate, and manage the version of
Program Outcomes (POs) associated with an academic program.

Program Outcomes define the knowledge, skills, and competencies
that students are expected to attain upon completion of an
academic program.

The managed Program Outcomes shall be available for use in
curriculum design, Course Outcome (CO) to Program Outcome (PO)
mapping, and curriculum verification.

---

## Actors

### Primary Actors

- **Admin** — Creates, updates, deactivates, and manages Program Outcomes.
- **Curriculum Committee Member** — Reviews and approves Program Outcome changes.

### Secondary Actors

- **Faculty / Instructor** — Views Program Outcomes and uses them for
  curriculum and CO-PO mapping.
- **Reviewer** — Views Program Outcomes during curriculum verification.

---

## Functional Requirements

### FR-08-01: Create Program Outcome

The system shall allow an authorized user to create a Program Outcome
for an academic program.

The user shall provide:

- PO identifier
- PO description
- Associated academic program

The system shall validate the provided information before creating
the Program Outcome.

---

### FR-08-02: View Program Outcomes

The system shall allow authorized users to view Program Outcomes
associated with an academic program.

The system shall support:

- Viewing all Program Outcomes for a program
- Viewing details of an individual Program Outcome
- Viewing the current status of a Program Outcome

---

### FR-08-03: Update Program Outcome

The system shall allow authorized users to update permitted
attributes of an existing Program Outcome.

The system shall maintain the history of changes made to the
Program Outcome.

---

### FR-08-04: Deactivate Program Outcome

The system shall allow authorized users to deactivate a Program
Outcome that is no longer applicable to new curriculum versions.

Deactivation shall not remove the Program Outcome from historical
curriculum records or existing mappings.

---

### FR-08-05: Manage Program Outcome Versions

The system shall maintain versions of Program Outcomes when
changes affect an existing curriculum or academic program.

Each version shall maintain:

- Version identifier
- PO details
- Effective date
- Status
- Created or modified information

Historical curriculum versions shall continue to reference the
appropriate Program Outcome version.

---

### FR-08-06: Review Program Outcome Changes

The system shall allow authorized Curriculum Committee Members
to review proposed changes to Program Outcomes.

A reviewer shall be able to:

- Review the proposed changes
- Approve the changes
- Reject the changes
- Provide review comments

Only approved changes shall become effective where approval is
required by the configured workflow.

---

## Business Rules

### BR-PO-01: Unique Identifier

Each Program Outcome shall have a unique identifier within its
associated academic program.

### BR-PO-02: Required Information

A Program Outcome shall have:

- A valid identifier
- A non-empty description
- An associated academic program

### BR-PO-03: Authorization

Only users with the required permissions shall be allowed to
create, update, deactivate, or approve Program Outcomes.

### BR-PO-04: Historical Data

A Program Outcome shall not be physically deleted if it is
referenced by an existing curriculum, course outcome mapping,
verification result, or other historical record.

### BR-PO-05: Deactivated Outcomes

A deactivated Program Outcome shall not be available for new
curriculum mappings unless explicitly permitted by the system.

### BR-PO-06: Version Integrity

Changes to a Program Outcome that affect an existing curriculum
version shall not alter the historical PO information associated
with that curriculum version.

### BR-PO-07: Auditability

Creation, modification, deactivation, approval, and rejection
of Program Outcomes shall be recorded in the audit history.

---

## Preconditions

For creating or modifying a Program Outcome:

- The user must be authenticated.
- The user must have the required permission.
- The associated academic program must exist.
- Required PO information must be provided.

---

## Postconditions

### On Successful Creation

- A new Program Outcome is stored.
- The PO is associated with the selected academic program.
- The creation action is recorded in the audit history.

### On Successful Update

- The permitted PO information is updated.
- The previous state is preserved where versioning is applicable.
- The update is recorded in the audit history.

### On Deactivation

- The PO status is changed to inactive/deactivated.
- Historical references remain valid.
- The deactivation is recorded in the audit history.

### On Approval

- The proposed PO change becomes approved.
- The approved version becomes effective according to the workflow.
- The approval action is recorded.

---

## Dependencies

This requirement depends on:

- User and Role Management
- Academic Program Management
- Curriculum Management

Program Outcomes shall be used by:

- Course Outcome Management
- CO-PO Mapping
- Curriculum Verification
- Verification Reporting

---

## Validation Rules

### VR-PO-01: PO Identifier Validation

- The PO identifier shall be mandatory.
- The PO identifier shall be unique within the associated academic program.
- The PO identifier shall follow the configured naming format.

### VR-PO-02: PO Description Validation

- The PO description shall be mandatory.
- The PO description shall not be empty or contain only whitespace.
- The PO description shall comply with the configured length constraints.

### VR-PO-03: Academic Program Validation

- An academic program shall be selected for every Program Outcome.
- The selected academic program must exist in the system.
- The academic program must be active when creating a new Program Outcome.

### VR-PO-04: Update Validation

- The Program Outcome must exist before it can be updated.
- Only permitted attributes shall be modified.
- Updates shall not invalidate existing curriculum or mapping references.

### VR-PO-05: Deactivation Validation

- The Program Outcome must exist before it can be deactivated.
- A Program Outcome already deactivated shall not be deactivated again.
- Deactivation shall not remove existing historical references.

### VR-PO-06: Approval Validation

- Only authorized Curriculum Committee Members shall approve or reject changes.
- A change must be in a reviewable state before approval or rejection.
- Rejected changes shall not become effective.

---

## Exceptions / Edge Cases

### EX-PO-01: Duplicate PO Identifier

If a PO identifier already exists within the same academic program, the system shall reject the creation or update operation.

### EX-PO-02: Academic Program Not Found

If the specified academic program does not exist, the system shall reject the operation.

### EX-PO-03: Unauthorized Operation

If the user does not have the required permission, the system shall reject the operation and record the authorization failure where applicable.

### EX-PO-04: PO Referenced by Existing Data

If a Program Outcome is referenced by an existing curriculum, CO-PO mapping, verification result, or historical record, the system shall prevent physical deletion.

### EX-PO-05: Deactivated PO Used in New Mapping

If a user attempts to use a deactivated Program Outcome in a new curriculum or CO-PO mapping, the system shall reject the operation unless explicitly permitted by the system.

### EX-PO-06: Concurrent Modification

If multiple users attempt to modify the same Program Outcome simultaneously, the system shall prevent unintended overwriting of changes.

### EX-PO-07: Invalid PO Version

If a requested Program Outcome version does not exist or is not valid for the requested curriculum version, the system shall reject the operation.

### EX-PO-08: Invalid Approval

If an approval request does not satisfy the required validation or workflow conditions, the system shall prevent the change from becoming effective.

---

## Outcome

Upon successful implementation of this requirement:

- Program Outcomes shall be maintained against academic programs.
- Authorized users shall be able to create, view, update, and deactivate Program Outcomes.
- Program Outcome versions shall be maintained where required.
- Program Outcome changes shall support review and approval.
- Historical Program Outcome information shall remain preserved.
- Valid and approved Program Outcomes shall be available for curriculum design and CO-PO mapping.
- Program Outcomes shall be available to the curriculum verification process.
- Program Outcome operations shall be auditable.

## Notes

Program Outcome management shall be independent of the actual
curriculum verification process.

The verification module shall consume approved Program Outcomes
and their mappings when performing curriculum analysis.