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

- Allow an authorized user to create a curriculum.
- Validate required curriculum information.
- Associate the curriculum with a program and department.
- Create the initial curriculum version.
- Save the curriculum as a draft.

## Business Rules

- Only authorized users can create curricula.
- A curriculum must belong to a valid program.
- Required fields must be provided.
- The initial curriculum shall start with version `1.0`.

## Example

B.Tech Computer Science
- Regulation: 2026
- Duration: 4 years
- Semesters: 8