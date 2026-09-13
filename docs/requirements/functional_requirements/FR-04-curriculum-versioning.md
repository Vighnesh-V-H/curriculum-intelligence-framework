# FR-04: Curriculum Versioning

## Description

The system shall maintain multiple versions of a curriculum and allow authorized users to track, view, and compare changes between curriculum versions.

## Actors

- **Faculty** — Creates or modifies curriculum versions where authorized.
- **Curriculum Committee Member** — Reviews and compares curriculum versions.

## Functional Behavior

The system shall:

- Create a new version when a curriculum is modified after a version has been finalized or published.
- Maintain all previous curriculum versions.
- Assign a unique version identifier to each curriculum version.
- Record the creation date, creator, and status of each version.
- Allow authorized users to view previous curriculum versions.
- Allow authorized users to compare two curriculum versions.
- Identify changes between selected versions.
- Display the differences in a structured manner.

## Version Comparison

When comparing two curriculum versions, the system shall identify:

- Added courses.
- Removed courses.
- Modified course information.
- Changed course credits.
- Changed semester allocation.
- Added or removed prerequisites.
- Modified course outcomes (COs).
- Modified program outcomes (POs) or CO-PO mappings.

### Example

A curriculum for **B.Tech Computer Science and Engineering** may have:

```text
2024 Regulation
2025 Regulation
2026 Regulation
```

A Curriculum Committee Member can compare:

```text
2025 Regulation → 2026 Regulation
```

The system may produce a comparison such as:

```text
Added Courses
├── Generative AI
└── Cloud Computing

Removed Courses
└── Legacy Computer Architecture

Modified Courses
└── Machine Learning
    ├── Credits: 3 → 4
    └── Semester: 6 → 5

Changed Prerequisites
└── Deep Learning
    └── Machine Learning → Machine Learning + Statistics
```

## Business Rules

- A curriculum version shall be immutable once it is published.
- Modifications to a published curriculum shall create a new version.
- Previous versions shall not be overwritten or deleted.
- Each version shall belong to exactly one curriculum.
- A version comparison shall not modify either of the compared versions.
- Only authorized users shall be allowed to access curriculum version history.
- The system shall preserve the relationship between successive versions.

## Expected Outcome

The system shall provide a complete history of curriculum changes and allow authorized users to clearly identify differences between any two available curriculum versions.
