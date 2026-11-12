# LLD: Authentication and Authorization

## 1. Purpose

This document defines the low-level design for FR-01 (User Authentication
and Authorization) in the FastAPI backend. It complements the identity
tables in `docs/lld/database-schema.md` (sections 4.1).

## 2. Components

```text
FastAPI router (app/api/v1)
        ↓
Dependency injection (app/api/deps.py)
        ↓
Service (app/services/auth.py, app/services/users.py)
        ↓
Repository (app/repositories/users.py, app/repositories/roles.py)
        ↓
SQLAlchemy models / PostgreSQL
```

Supporting modules:

- `app/core/security.py` — Argon2 password hashing and JWT creation/decoding.
- `app/db/models/user.py` — `User`, `Role`, `UserRole`, `UserStatus`, `RoleCode`.
- `app/schemas/` — Pydantic request/response DTOs.
- `app/db/bootstrap.py` — optional first-run administrator creation.

## 3. Token Design

- Algorithm: HS256 (configurable via `JWT_ALGORITHM`).
- Secret: `JWT_SECRET`, minimum 32 characters; required at startup.
- Lifetime: `ACCESS_TOKEN_EXPIRE_MINUTES` (default 60).
- Claims: `sub` (user UUID), `username`, `roles`, `iat`, `exp`.
- Tokens are stateless access tokens. Refresh tokens and session revocation
  remain future extensions (see database schema section 8).
- Authorization always re-reads the user and roles from PostgreSQL so that
  deactivation and role changes take effect without waiting for expiry.

## 4. Passwords

- Passwords are hashed with Argon2 through `pwdlib`.
- Plaintext passwords are never stored or logged.
- The `users.password_hash` column stores the encoded hash.
- Login verifies a dummy hash when the user does not exist to reduce timing
  differences between unknown-user and wrong-password responses.

## 5. API Endpoints

| Method | Path | Access | Behavior |
| --- | --- | --- | --- |
| `POST` | `/api/v1/auth/login` | Public | Accepts username or email plus password; returns access token and user profile. |
| `GET` | `/api/v1/auth/me` | Authenticated | Returns the current user with roles. |
| `POST` | `/api/v1/users` | `ADMIN` | Creates a user and assigns one or more roles. |
| `GET` | `/api/v1/users` | `ADMIN` | Lists users. |
| `GET` | `/api/v1/users/{id}` | `ADMIN` | Returns one user. |
| `PUT` | `/api/v1/users/{id}/roles` | `ADMIN` | Replaces the user's role assignments. |
| `PATCH` | `/api/v1/users/{id}/status` | `ADMIN` | Changes `ACTIVE`, `INACTIVE`, or `LOCKED` status. |
| `GET` | `/health` | Public | Liveness check. |

Example login request:

```json
{
  "username": "faculty.name",
  "password": "secret"
}
```

Example login response:

```json
{
  "access_token": "<jwt>",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": {
    "id": "00000000-0000-0000-0000-000000000000",
    "username": "faculty.name",
    "email": "faculty.name@example.com",
    "full_name": "Faculty Name",
    "status": "ACTIVE",
    "roles": ["FACULTY"],
    "last_login_at": "2026-10-28T10:15:00Z",
    "created_at": "2026-10-01T09:00:00Z"
  }
}
```

## 6. Roles and Authorization

Seeded roles: `ADMIN`, `COMMITTEE_MEMBER`, `FACULTY`, `REVIEWER`.

- User administration endpoints require `ADMIN`.
- Domain endpoints added by later requirements use `require_roles(...)` with
  the roles defined by those requirements.
- Reviewers are intended to be read-only for curriculum and verification
  data, as specified by FR-01 examples.
- A user with multiple roles receives the union of their permissions.

## 7. Error Contract

All errors use a consistent shape:

```json
{
  "error": {
    "code": "invalid_credentials",
    "message": "Invalid username or password"
  },
  "path": "/api/v1/auth/login",
  "details": null
}
```

Notable codes: `invalid_credentials`, `account_inactive`, `invalid_token`,
`forbidden`, `username_taken`, `email_taken`, `user_conflict`,
`validation_error`, `not_found`.

## 8. Configuration

| Variable | Required | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | Yes | SQLAlchemy PostgreSQL URL (`postgresql+psycopg://...`). |
| `JWT_SECRET` | Yes | Signing key, at least 32 characters. |
| `JWT_ALGORITHM` | No | Defaults to `HS256`. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | Defaults to `60`. |
| `CORS_ORIGINS` | No | JSON list, default `["http://localhost:3000"]`. |
| `BOOTSTRAP_ADMIN_USERNAME` | No | Defaults to `admin`. |
| `BOOTSTRAP_ADMIN_EMAIL` | No | Defaults to `admin@example.com`. |
| `BOOTSTRAP_ADMIN_PASSWORD` | No | When set, creates the administrator on first start if absent. |

Passwords are never placed in documentation or source control. Environment
files are excluded by `.gitignore`.

## 9. Frontend Integration

- The Next.js app calls `POST /api/v1/auth/login` and stores the access token
  in `localStorage` for this initial implementation.
- `/dashboard` calls `GET /api/v1/auth/me`; a `401` clears the token and
  redirects to `/login`.
- `/users` provides admin-only account administration: create an account,
  assign one or more seeded roles, and set the account status. The navigation
  item is hidden from other roles, and every user-administration endpoint still
  requires `ADMIN`. Administrators cannot change their own roles or status from
  this page, avoiding accidental lockout.
- Storing tokens in `localStorage` is acceptable for this development phase
  but is vulnerable to XSS. Moving to httpOnly secure cookies is a planned
  hardening step.

## 10. Tests

`backend/tests/` covers:

- Password hashing and JWT round trips.
- Login success, unknown user, wrong password, inactive account.
- Bearer requirement, malformed and expired tokens.
- Admin-only user creation, listing, role assignment, status changes.
- Duplicate username/email and request validation.
- Request validation and consistent error responses.
