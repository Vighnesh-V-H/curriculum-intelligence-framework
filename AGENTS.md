# Project Agent Instructions

## 1. Project Overview

This project is an AI-powered curriculum design and
verification framework.

Backend:
- Java
- Spring Boot
- PostgreSQL
- Neo4j

AI services:
- Python

## 2. Development Workflow

Before implementing a feature:

1. Read the relevant requirements.
2. Identify the affected use cases.
3. Check the existing architecture.
4. Check the existing LLD.
5. Update the design if required.
6. Implement the feature.
7. Write/update tests.
8. Run tests.
9. Update documentation.

Do not start implementation without understanding
the existing design.

## 3. Architecture Rules

Follow:

Controller
    ↓
Service
    ↓
Repository
    ↓
Database

Controllers must not contain business logic.

Repositories must not contain business logic.

Business logic belongs in the service/domain layer.

## 4. Design Rules

Before introducing a new entity or module:

- Check whether an existing entity can be reused.
- Check existing requirements.
- Update the relevant LLD.
- Avoid unnecessary abstractions.

Do not create classes/interfaces only for the sake
of following a pattern.

## 5. API Rules

- Use RESTful APIs.
- Use DTOs for API requests/responses.
- Do not expose persistence entities directly.
- Validate incoming requests.
- Use consistent error responses.

## 6. Database Rules

- PostgreSQL is the primary relational database.
- Use migrations for schema changes.
- Do not modify production schema manually.
- Keep entity relationships consistent with the LLD.

## 7. Testing

Every new feature should have appropriate tests.

Run:

./mvnw test

Do not consider a feature complete if tests fail.

## 8. Documentation

Requirements:
docs/requirements/

Use cases:
docs/use-cases/

Architecture:
docs/architecture/

LLD:
docs/lld/

If implementation changes the design,
update the corresponding documentation.

## 9. Change Discipline

- Do not modify unrelated files.
- Do not introduce dependencies without justification.
- Do not rewrite existing code unnecessarily.
- Prefer small, focused changes.
- Preserve existing behavior unless the requirement
  explicitly changes it.

## 10. Important Rule

The documentation is the source of truth for intended
system behavior.

If the requested implementation conflicts with the
existing requirements or architecture:

1. Identify the conflict.
2. Explain it.
3. Propose the required design change.
4. Do not silently violate the existing architecture.