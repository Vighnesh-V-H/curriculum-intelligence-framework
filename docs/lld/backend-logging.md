# Backend Logging LLD

## Purpose

Provide consistent, searchable operational and security-relevant logs across the FastAPI backend without logging curriculum content, credentials, or other sensitive request data.

## Design

- Use Python's standard `logging` package; no additional runtime dependency.
- Configure logging once in `app.core.logging_config` during application creation.
- Emit one JSON object per event to stdout. The platform/process manager owns collection, retention, and rotation; the application does not write log files.
- Use module-level loggers named from `__name__`, so application events share the `app.*` hierarchy.
- `LOG_LEVEL` supports `DEBUG`, `INFO`, `WARNING`, `ERROR`, and `CRITICAL`; default is `INFO`.
- HTTP middleware accepts a valid `X-Request-ID` or generates a UUID, returns it in the response header, and includes it in request-scoped logs. Untrusted request IDs are validated before reuse.
- Authenticated requests bind the actor's internal ID to the request context. IDs are not usernames or email addresses.
- Every HTTP request logs method, route template, status code, duration, request ID, and authenticated actor ID when available. The middleware does not log raw unmatched paths, query strings, bodies, or headers.
- Exception handlers log application error codes and status; validation events include error types/count only. Unexpected exceptions include safe stack-frame locations and exception type, never exception text or source lines.
- Long-running or external workflows (document upload/ingestion, LLM requests, curriculum drafting, and verification runs) log start, outcome, duration, and safe aggregate metadata. Retries include attempt and provider status.
- SQL statements and parameters are not logged. Uvicorn access logs are suppressed to avoid duplicate/unstructured access events; Uvicorn application errors use the configured formatter.

## Privacy and security

Never log passwords, bearer tokens, API keys, signed storage URLs, request/response bodies, uploaded document text, raw LLM prompts/responses, email addresses, or filenames. The JSON formatter only serializes an allowlist of structured fields. Add new fields only after reviewing them for sensitive data. Exception text is intentionally excluded from serialized stack traces; log a safe event and exception type instead.

## Failure behavior

Logging is best-effort observability and must not change request or business behavior. Logs go to stdout and use standard logger APIs; logging transport, storage, and retention are deployment concerns. Request correlation IDs are returned on handled responses and included in error responses where available.

## Verification

Automated tests cover JSON formatting, safe-field allowlisting, request ID propagation/validation, request outcome logging, and exception logging. Backend lint and test suites remain required.
