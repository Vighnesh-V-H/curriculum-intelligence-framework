# FR-09: Program Educational Objective Management

## Description

The Program Educational Objective Management module shall allow
authorized users to create, view, update, deactivate, and manage
the versions of Program Educational Objectives (PEOs) associated
with an academic program.

Program Educational Objectives define the broad achievements that
graduates are expected to attain within a specified period after
completing an academic program.

The managed Program Educational Objectives shall be available for
use in curriculum design, curriculum verification, and accreditation
analysis.

---

## Actors

### Primary Actors

- **Admin** — Creates, updates, deactivates, and manages Program Educational Objectives.
- **Curriculum Committee Member** — Reviews and approves Program Educational Objective changes.

### Secondary Actors

- **Faculty / Instructor** — Views Program Educational Objectives and uses them during curriculum development.
- **Reviewer** — Views Program Educational Objectives during curriculum verification.

---

## Functional Requirements

### FR-09-01: Create Program Educational Objective

The system shall allow an authorized user to create a Program
Educational Objective for an academic program.

The user shall provide:

- PEO identifier
- PEO description
- Associated academic program

The system shall validate the provided information before creating
the Program Educational Objective.

---

### FR-09-02: View Program Educational Objectives

The system shall allow authorized users to view Program Educational
Objectives associated with an academic program.

The system shall support:

- Viewing all PEOs for a program
- Viewing details of an individual PEO
- Viewing the current status of a PEO

---

### FR-09-03: Update Program Educational Objective

The system shall allow authorized users to update permitted
attributes of an existing Program Educational Objective.

The system shall maintain the history of changes made to the
Program Educational Objective.

---

### FR-09-04: Deactivate Program Educational Objective

The system shall allow authorized users to deactivate a Program
Educational Objective that is no longer applicable to new
curriculum versions.

Deactivation shall not remove the Program Educational Objective
from historical curriculum records or existing references.

---

### FR-09-05: Manage Program Educational Objective Versions

The system shall maintain versions of Program Educational Objectives
when changes affect an existing curriculum or academic program.

Each version shall maintain:

- Version identifier
- PEO details
- Effective date
- Status
- Created or modified information

Historical curriculum versions shall continue to reference the
appropriate Program Educational Objective version.

---

### FR-09-06: Review Program Educational Objective Changes

The system shall allow authorized Curriculum Committee Members
to review proposed changes to Program Educational Objectives.

A reviewer shall be able to:

- Review the proposed changes
- Approve the changes
- Reject the changes
- Provide review comments

Only approved changes shall become effective where approval is
required by the configured workflow.

---

## Business Rules

### BR-PEO-01: Unique Identifier

Each Program Educational Objective shall have a unique identifier
within its associated academic program.

### BR-PEO-02: Required Information

A Program Educational Objective shall have:

- A valid identifier
- A non-empty description
- An associated academic program

### BR-PEO-03: Authorization

Only users with the required permissions shall be allowed to
create, update, deactivate, or approve Program Educational
Objectives.

### BR-PEO-04: Historical Data

A Program Educational Objective shall not be physically deleted
if it is referenced by an existing curriculum, verification result,
accreditation record, or other historical record.

### BR-PEO-05: Deactivated Objectives

A deactivated Program Educational Objective shall not be available
for new curriculum or accreditation mappings unless explicitly
permitted by the system.

### BR-PEO-06: Version Integrity

Changes to a Program Educational Objective that affect an existing
curriculum version shall not alter the historical PEO information
associated with that curriculum version.

### BR-PEO-07: Auditability

Creation, modification, deactivation, approval, and rejection
of Program Educational Objectives shall be recorded in the
audit history.

---

## Preconditions

For creating or modifying a Program Educational Objective:

- The user must be authenticated.
- The user must have the required permission.
- The associated academic program must exist.
- Required PEO information must be provided.

---

## Postconditions

### On Successful Creation

- A new Program Educational Objective is stored.
- The PEO is associated with the selected academic program.
- The creation action is recorded in the audit history.

### On Successful Update

- The permitted PEO information is updated.
- The previous state is preserved where versioning is applicable.
- The update is recorded in the audit history.

### On Deactivation

- The PEO status is changed to inactive/deactivated.
- Historical references remain valid.
- The deactivation is recorded in the audit history.

### On Approval

- The proposed PEO change becomes approved.
- The approved version becomes effective according to the workflow.
- The approval action is recorded.

---

## Dependencies

This requirement depends on:

- User and Role Management
- Academic Program Management
- Curriculum Management

Program Educational Objectives shall be used by:

- Curriculum Management
- Curriculum Verification
- Accreditation Analysis
- Verification Reporting

---

## Validation Rules

### VR-PEO-01: PEO Identifier Validation

- The PEO identifier shall be mandatory.
- The PEO identifier shall be unique within the associated academic program.
- The PEO identifier shall follow the configured naming format.

### VR-PEO-02: PEO Description Validation

- The PEO description shall be mandatory.
- The PEO description shall not be empty or contain only whitespace.
- The PEO description shall comply with the configured length constraints.

### VR-PEO-03: Academic Program Validation

- An academic program shall be selected for every Program Educational Objective.
- The selected academic program must exist in the system.
- The academic program must be active when creating a new Program Educational Objective.

### VR-PEO-04: Update Validation

- The Program Educational Objective must exist before it can be updated.
- Only permitted attributes shall be modified.
- Updates shall not invalidate existing curriculum or historical references.

### VR-PEO-05: Deactivation Validation

- The Program Educational Objective must exist before it can be deactivated.
- A Program Educational Objective that is already deactivated shall not be deactivated again.
- Deactivation shall not remove existing historical references.

### VR-PEO-06: Approval Validation

- Only authorized Curriculum Committee Members shall approve or reject changes.
- A change must be in a reviewable state before approval or rejection.
- Rejected changes shall not become effective.

---

## Exceptions / Edge Cases

### EX-PEO-01: Duplicate PEO Identifier

If a PEO identifier already exists within the same academic program,
the system shall reject the creation or update operation.

### EX-PEO-02: Academic Program Not Found

If the specified academic program does not exist, the system shall
reject the operation.

### EX-PEO-03: Unauthorized Operation

If the user does not have the required permission, the system shall
reject the operation and record the authorization failure where
applicable.

### EX-PEO-04: PEO Referenced by Existing Data

If a Program Educational Objective is referenced by an existing
curriculum, verification result, accreditation record, or historical
record, the system shall prevent physical deletion.

### EX-PEO-05: Deactivated PEO Used in New Data

If a user attempts to use a deactivated Program Educational
Objective in a new curriculum or accreditation-related mapping,
the system shall reject the operation unless explicitly permitted
by the system.

### EX-PEO-06: Concurrent Modification

If multiple users attempt to modify the same Program Educational
Objective simultaneously, the system shall prevent unintended
overwriting of changes.

### EX-PEO-07: Invalid PEO Version

If a requested Program Educational Objective version does not exist
or is not valid for the requested curriculum version, the system
shall reject the operation.

### EX-PEO-08: Invalid Approval

If an approval request does not satisfy the required validation or
workflow conditions, the system shall prevent the change from
becoming effective.

---

## Outcome

Upon successful implementation of this requirement:

- Program Educational Objectives shall be maintained against academic programs.
- Authorized users shall be able to create, view, update, and deactivate PEOs.
- Program Educational Objective versions shall be maintained where required.
- Program Educational Objective changes shall support review and approval.
- Historical Program Educational Objective information shall remain preserved.
- Valid and approved PEOs shall be available for curriculum design and verification.
- Program Educational Objectives shall be available to the curriculum verification process.
- Program Educational Objective operations shall be auditable.

## Notes

Program Educational Objective management shall be independent of the
actual curriculum verification process.

The verification module shall consume approved Program Educational
Objectives when performing curriculum analysis and accreditation
checks.