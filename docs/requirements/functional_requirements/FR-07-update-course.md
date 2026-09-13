# FR-07: Update Course

## Description

The system shall allow an authorized user to modify the information of an existing course within an editable curriculum version.

## Actors

- Faculty / Instructor

## Preconditions

- The user must be authenticated.
- The user must have permission to modify the curriculum.
- The course must exist in the selected curriculum version.
- The curriculum version must be editable.

## Functional Behavior

The system shall:

- Allow authorized users to select an existing course.
- Allow users to modify applicable course information.
- Validate the modified information before saving.
- Preserve the association between the course and its curriculum version.
- Record the changes made to the course.
- Reflect the updated course information in the current editable curriculum version.

## Course Information

The course may contain information such as:

- Course Name
- Course Type
- Credits
- Semester
- Hours
- Description
- Syllabus
- Other applicable course information

The following shall be managed through separate functional requirements:

- Prerequisites
- Corequisites
- Course Outcomes (COs)
- CO-PO Mapping

## Business Rules

- Only authorized users shall be allowed to modify a course.
- Required course information shall remain valid after modification.
- Course code shall remain unchanged unless the system explicitly supports course-code changes.
- A published curriculum version shall not be modified directly.
- Changes to a published curriculum shall be made through a new curriculum version.
- Previous finalized or published versions shall remain unchanged.
- All modifications shall be recorded for traceability.

## Validation Rules

- Modified course information shall satisfy the applicable curriculum rules.
- Credits shall be valid according to the applicable rules.
- Semester allocation shall be valid for the curriculum.
- Required information shall not be empty.
- The updated course shall not create an invalid curriculum state.

## Exceptions / Edge Cases

- If the course does not exist, the system shall reject the operation.
- If the curriculum version is not editable, the system shall prevent the modification.
- If the user does not have permission, the system shall reject the operation.
- If the modified information is invalid, the system shall request correction.
- If the modification affects a finalized or published curriculum, the system shall create or require a new curriculum version.

## Outcome

The course shall be updated successfully in the applicable editable curriculum version, and the modification shall be recorded for future reference.
