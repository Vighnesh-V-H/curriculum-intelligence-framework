# FR-02: Create Curriculum

## Description

The system shall allow an authorized user to create a curriculum
for a program.

## Actors

- Curriculum Committee Member
- Authorized Faculty

## Inputs

- Program
- Department
- Academic Year
- Regulation
- Duration
- Semesters
- Courses
- PEOs
- POs

## Functional Behavior

The system shall:

- Allow an authorized user to generate a curriculum by selecting an existing program and uploading 1-5 reference documents.
- Use uploaded documents as the source for curriculum generation and associate the result with the selected program.
- Default the academic year to the current academic year and regulation to the current calendar year.
- Associate the curriculum with the selected program and its department.
- Save each generated result immediately as the current curriculum content. Do not create a user-visible draft or require approval.
- Allow multiple curricula for the same program and regulation; each generated result is retained separately.
- List all saved curricula in the curriculum workspace and allow the user to open any item.
- Redirect the user to the newly saved curriculum in the curriculum workspace.

## Business Rules

- Only authorized users can create curricula.
- A curriculum must belong to a valid program.
- The selected program must exist and at least one valid reference document must be uploaded.
- Academic year and regulation are derived automatically for direct generation.
- Generated curriculum content is immediately available for editing and use.
- A program and regulation combination is not unique; generating again creates a separate curriculum rather than opening or replacing an existing one.

## Example

B.Tech Computer Science
- Regulation: 2026
- Duration: 4 years
- Semesters: 8