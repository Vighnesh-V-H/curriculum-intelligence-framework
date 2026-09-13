# FR-08: Remove Course

## Description

The system shall allow an authorized user to remove an existing course from an editable curriculum version.

## Actors

- Faculty / Instructor

## Preconditions

- The user must be authenticated.
- The user must have permission to modify the curriculum.
- The course must exist in the selected curriculum version.
- The curriculum version must be editable.

## Functional Behavior

The system shall:

- Allow an authorized user to select a course for removal.
- Check whether the course has dependencies within the curriculum.
- Notify the user of relevant dependencies before removal.
- Allow the user to confirm the removal.
- Remove the course from the applicable curriculum version.
- Record the course removal as a curriculum change.

## Dependency Check

Before removing a course, the system shall check whether the course is:

- A prerequisite for another course.
- A corequisite for another course.
- Referenced by other curriculum components.
- Required by applicable curriculum rules.

If dependencies exist, the system shall inform the user before the course is removed.

## Business Rules

- Only authorized users shall be allowed to remove courses.
- A course shall not be physically deleted when it is required for historical curriculum records.
- Removing a course from one curriculum version shall not modify previous versions.
- A course removed from a published curriculum shall remain available in the historical published version.
- Removing a course from a published curriculum shall require a new curriculum version.
- The system shall preserve the history of the removal.

## Validation Rules

- The selected course must exist in the curriculum version.
- The curriculum version must be editable.
- The user must have the required permission.
- Dependencies shall be checked before removal.

## Exceptions / Edge Cases

- If the course does not exist, the system shall reject the operation.
- If the curriculum version is published, the system shall prevent direct removal.
- If the user does not have permission, the system shall reject the operation.
- If the course is referenced as a prerequisite or corequisite by another course, the system shall notify the user.
- If removal would violate curriculum rules, the system shall prevent the operation or require the appropriate correction.

## Outcome

The course shall be removed from the applicable editable curriculum version, while historical curriculum versions and relevant change history remain preserved.
