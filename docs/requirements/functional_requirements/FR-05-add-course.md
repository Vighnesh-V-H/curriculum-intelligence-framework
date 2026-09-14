# FR-06: Add Course

## Description

The system shall allow an authorized user to add a new course to an editable curriculum version.

## Actors

* Faculty / Instructor

## Preconditions

* The user must be authenticated.
* The user must have permission to modify the curriculum.
* The selected curriculum version must exist.
* The curriculum version must be editable.

## Functional Behavior

The system shall:

* Allow an authorized user to add a new course to a curriculum version.
* Allow the user to provide the required course information.
* Validate the provided course information.
* Associate the course with the selected curriculum version.
* Check for duplicate course codes within the applicable curriculum version.
* Save the course information.
* Record the creation of the course.

## Course Information

The course may contain information such as:

* Course Code
* Course Name
* Course Type
* Credits
* Semester
* Hours
* Description
* Syllabus
* Other applicable course information

The following shall be managed through separate functional requirements:

* Prerequisites
* Corequisites
* Course Outcomes (COs)
* CO-PO Mapping

## Business Rules

* Only authorized users shall be allowed to add courses.
* Course code shall be unique within the applicable curriculum version.
* Required course information must be provided before the course can be added.
* A course shall be associated with a valid semester.
* Credits and other applicable course information shall satisfy the relevant curriculum rules.
* A published curriculum version shall not be directly modified.
* A course added to a new curriculum version shall not modify previous versions.

## Validation Rules

* Course Code must be provided.
* Course Name must be provided.
* Course Type must be valid.
* Credits must be valid.
* Semester must belong to the curriculum.
* Required course information must be complete.
* Course Code must not already exist within the curriculum version.

## Exceptions / Edge Cases

* If the course code already exists, the system shall reject the operation.
* If required information is missing, the system shall request correction.
* If the curriculum version is not editable, the system shall prevent the operation.
* If the user does not have permission, the system shall reject the operation.
* If the provided course information violates curriculum rules, the system shall reject the operation.

## Outcome

A valid course shall be added to the selected editable curriculum version and the creation shall be recorded for future reference.