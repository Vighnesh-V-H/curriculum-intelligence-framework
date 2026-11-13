# Program Outcome and PEO Management API

Covers FR-08 (Program Outcomes) and FR-09 (Program Educational
Objectives). Both use the same data structures. Current behavior is immediate
create/edit with no approval gate; authorized faculty can write. The legacy
version tables are retained only for relational compatibility. Version-history
and version-status endpoints have been removed; the workspace uses current
outcome content only.

## Authorization

| Operation | Allowed roles |
| --- | --- |
| Read POs and PEOs | Any authenticated user |
| Create, update, or deactivate | `ADMIN`, `COMMITTEE_MEMBER`, `FACULTY` |

## Program Outcomes

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/api/v1/programs/{program_id}/program-outcomes` | Create an immediately effective PO |
| `GET` | `/api/v1/programs/{program_id}/program-outcomes` | List POs for a program |
| `GET` | `/api/v1/program-outcomes/{outcome_id}` | Get a PO with version history |
| `PATCH` | `/api/v1/program-outcomes/{outcome_id}` | Update the PO identifier or description in place |
| `PATCH` | `/api/v1/program-outcomes/{outcome_id}/status` | Activate or deactivate the PO |

## Program Educational Objectives

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/api/v1/programs/{program_id}/peos` | Create an immediately effective PEO |
| `GET` | `/api/v1/programs/{program_id}/peos` | List PEOs for a program |
| `GET` | `/api/v1/peos/{peo_id}` | Get a PEO with version history |
| `PATCH` | `/api/v1/peos/{peo_id}` | Update the PEO identifier or description in place |
| `PATCH` | `/api/v1/peos/{peo_id}/status` | Activate or deactivate the PEO |

## Retired Version Workflow

The following lifecycle is legacy documentation only. Current product behavior
creates and edits current PO/PEO content in place without these transitions.


```text
DRAFT -> PROPOSED -> APPROVED
                  -> REJECTED -> DRAFT
```

- Editing a draft updates it in place.
- Editing after approval creates a new draft version with the next
  version number.
- Editing is blocked while the latest version is `PROPOSED`.
- Approving a version sets `approved_by`, `approved_at`, and a default
  effective date when none was supplied.
- Approving a newer version marks the previous approved version as
  `SUPERSEDED`.
- Historical versions are never deleted.
- Deactivation sets the identity status to `INACTIVE` and preserves
  all versions and references.

## Validation

- PO/PEO codes are required, normalized to uppercase, and unique per
  program.
- Descriptions are required and cannot be blank.
- The program must exist and be active when creating an outcome.
- Version status changes follow the workflow above.
- Every create, update, status change, approval, and rejection writes
  to `audit_logs`.
