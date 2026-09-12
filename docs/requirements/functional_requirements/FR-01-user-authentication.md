# Functional Requirements

## FR-01: User Authentication and Authorization

### Description

The system shall authenticate users and authorize access based
on their assigned roles.

### Actors

- Admin
- Curriculum Committee Member
- Faculty
- Reviewer

### Functional Behavior

The system shall:

- Authenticate registered users.
- Assign roles to users.
- Authorize API operations based on roles.
- Prevent unauthorized modification of curriculum data.

### Example

A Reviewer can:

- View verification reports.
- Review AI findings.

A Reviewer cannot:

- Modify curriculum.
- Delete courses.