# FR-10: CO-PO Mapping

## Description

The CO-PO Mapping module shall allow authorized users to create,
view, update, and manage mappings between Course Outcomes (COs)
and Program Outcomes (POs) for a curriculum.

CO-PO mapping represents the relationship between the outcomes
defined for a course and the Program Outcomes that the course
contributes to.

The managed CO-PO mappings shall be available for curriculum
verification, outcome coverage analysis, and accreditation
reporting.

---

## Actors

### Primary Actors

- **Admin** — Creates, updates, and manages CO-PO mappings.
- **Faculty / Instructor** — Creates and updates mappings for
  courses assigned to them, where permitted.
- **Curriculum Committee Member** — Reviews and approves CO-PO
  mapping changes.

### Secondary Actors

- **Reviewer** — Views CO-PO mappings during curriculum verification.
- **Academic Program / Curriculum Coordinator** — Views and
  manages mappings within the scope of the academic program.

---

## Functional Requirements

### FR-10-01: Create CO-PO Mapping

The system shall allow an authorized user to create a mapping
between a Course Outcome and a Program Outcome.

The user shall provide:

- Associated course
- Course Outcome
- Program Outcome
- Mapping level or strength

The system shall validate the provided information before
creating the mapping.

---

### FR-10-02: View CO-PO Mappings

The system shall allow authorized users to view CO-PO mappings
associated with a course or academic program.

The system shall support:

- Viewing all mappings for a course
- Viewing mappings for an individual Course Outcome
- Viewing mappings for an individual Program Outcome
- Viewing the mapping level or strength

---

### FR-10-03: Update CO-PO Mapping

The system shall allow authorized users to update permitted
attributes of an existing CO-PO mapping.

The system shall maintain the history of changes made to the
mapping where versioning is applicable.

---

### FR-10-04: Remove CO-PO Mapping

The system shall allow authorized users to remove a CO-PO mapping
when it is no longer applicable to a new curriculum version.

Removal shall not invalidate historical curriculum records or
previous verification results.

---

### FR-10-05: Manage CO-PO Mapping Versions

The system shall maintain versions of CO-PO mappings when changes
affect an existing curriculum version.

Each mapping version shall maintain:

- Version identifier
- Course Outcome reference
- Program Outcome reference
- Mapping level or strength
- Effective date
- Status
- Created or modified information

Historical curriculum versions shall continue to reference the
appropriate CO-PO mapping version.

---

### FR-10-06: Review CO-PO Mapping Changes

The system shall allow authorized Curriculum Committee Members
to review proposed CO-PO mapping changes.

A reviewer shall be able to:

- Review the proposed mappings
- Approve the changes
- Reject the changes
- Provide review comments

Only approved changes shall become effective where approval is
required by the configured workflow.

---

## Business Rules

### BR-COPO-01: Valid Course Outcome

A CO-PO mapping shall reference an existing Course Outcome
associated with the selected course.

### BR-COPO-02: Valid Program Outcome

A CO-PO mapping shall reference an existing approved Program
Outcome associated with the relevant academic program.

### BR-COPO-03: Unique Mapping

The same Course Outcome and Program Outcome shall not have
duplicate active mappings within the same curriculum version.

### BR-COPO-04: Mapping Level

Each CO-PO mapping shall have a valid mapping level or strength
according to the configured institutional scale.

### BR-COPO-05: Authorization

Only users with the required permissions shall be allowed to
create, update, remove, or approve CO-PO mappings.

### BR-COPO-06: Historical Data

A CO-PO mapping shall not be physically removed if it is referenced
by an existing curriculum version, verification result, or other
historical record.

### BR-COPO-07: Version Integrity

Changes to a CO-PO mapping shall not alter the mapping information
associated with a historical curriculum version.

### BR-COPO-08: Auditability

Creation, modification, removal, approval, and rejection of
CO-PO mappings shall be recorded in the audit history.

---

## Preconditions

For creating or modifying a CO-PO mapping:

- The user must be authenticated.
- The user must have the required permission.
- The associated course must exist.
- The Course Outcome must exist and belong to the selected course.
- The Program Outcome must exist and belong to the relevant
  academic program.
- Required mapping information must be provided.

---

## Postconditions

### On Successful Creation

- A new CO-PO mapping is stored.
- The mapping is associated with the selected Course Outcome and
  Program Outcome.
- The mapping level or strength is stored.
- The creation action is recorded in the audit history.

### On Successful Update

- The permitted mapping information is updated.
- The previous state is preserved where versioning is applicable.
- The update is recorded in the audit history.

### On Removal

- The mapping is removed from active use.
- Historical references remain valid.
- The removal action is recorded in the audit history.

### On Approval

- The proposed CO-PO mapping change becomes approved.
- The approved mapping becomes effective according to the workflow.
- The approval action is recorded.

---

## Dependencies

This requirement depends on:

- User and Role Management
- Academic Program Management
- Course Management
- Course Outcome Management
- Program Outcome Management
- Curriculum Management

CO-PO mappings shall be used by:

- Curriculum Verification
- Outcome Coverage Analysis
- Accreditation Analysis
- Verification Reporting

---

## Validation Rules

### VR-COPO-01: Course Outcome Validation

- The Course Outcome must exist.
- The Course Outcome must belong to the selected course.
- The Course Outcome must be valid for the selected curriculum
  version.

### VR-COPO-02: Program Outcome Validation

- The Program Outcome must exist.
- The Program Outcome must belong to the relevant academic program.
- The Program Outcome must be approved and active for new mappings.

### VR-COPO-03: Duplicate Mapping Validation

- A duplicate active mapping between the same CO and PO shall not
  be allowed within the same curriculum version.

### VR-COPO-04: Mapping Level Validation

- The mapping level shall be mandatory.
- The mapping level shall conform to the configured institutional
  scale.
- Invalid or unsupported mapping levels shall be rejected.

### VR-COPO-05: Curriculum Validation

- The associated curriculum version must exist.
- The course must belong to the selected curriculum.
- The CO and PO must be valid for the selected curriculum context.

### VR-COPO-06: Update Validation

- The CO-PO mapping must exist before it can be updated.
- Only permitted attributes shall be modified.
- Updates shall not invalidate historical curriculum records.

### VR-COPO-07: Approval Validation

- Only authorized Curriculum Committee Members shall approve or
  reject mapping changes.
- A mapping change must be in a reviewable state before approval
  or rejection.
- Rejected mappings shall not become effective.

---

## Exceptions / Edge Cases

### EX-COPO-01: Course Outcome Not Found

If the specified Course Outcome does not exist, the system shall
reject the mapping operation.

### EX-COPO-02: Program Outcome Not Found

If the specified Program Outcome does not exist, the system shall
reject the mapping operation.

### EX-COPO-03: Invalid CO-Course Association

If the Course Outcome does not belong to the selected course,
the system shall reject the operation.

### EX-COPO-04: Duplicate CO-PO Mapping

If the same CO-PO mapping already exists for the curriculum
version, the system shall reject the creation of a duplicate
active mapping.

### EX-COPO-05: Invalid Mapping Level

If the provided mapping level is not supported by the configured
institutional scale, the system shall reject the operation.

### EX-COPO-06: Inactive Program Outcome

If a user attempts to create a new mapping using an inactive
Program Outcome, the system shall reject the operation unless
explicitly permitted by the system.

### EX-COPO-07: Historical Mapping

If a mapping is referenced by a historical curriculum or
verification result, the system shall prevent physical deletion
and preserve the historical mapping.

### EX-COPO-08: Concurrent Modification

If multiple users attempt to modify the same CO-PO mapping
simultaneously, the system shall prevent unintended overwriting
of changes.

### EX-COPO-09: Invalid Curriculum Context

If the course, CO, or PO does not belong to the selected
curriculum context, the system shall reject the mapping operation.

### EX-COPO-10: Invalid Approval

If an approval request does not satisfy the required validation
or workflow conditions, the system shall prevent the mapping
change from becoming effective.

---

## Outcome

Upon successful implementation of this requirement:

- CO-PO mappings shall be maintained for curriculum versions.
- Authorized users shall be able to create, view, update, and
  remove CO-PO mappings.
- Each mapping shall reference valid Course Outcomes and
  Program Outcomes.
- Mapping levels or strengths shall be maintained according to
  the configured institutional scale.
- CO-PO mapping changes shall support review and approval.
- Historical CO-PO mappings shall remain preserved.
- Valid and approved mappings shall be available for curriculum
  verification and outcome coverage analysis.
- CO-PO mapping operations shall be auditable.

## Notes

CO-PO Mapping shall be independent of the actual curriculum
verification process.

The verification module shall consume approved CO-PO mappings
when performing curriculum analysis, outcome coverage analysis,
and accreditation checks.

The mapping scale shall be configurable and shall not be hard-coded
to a specific institutional standard.