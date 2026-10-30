# Document Processing — LLD

## Scope

This document defines the low-level design for FR-13 (Curriculum
Document Processing): document upload, cloud storage via
UploadThing, text extraction, and passing extracted text to the
LLM analysis layer.

Neo4j graph projection of the analysis result is out of scope
(see `database-schema.md` section 7) and will consume the stored
analysis payload produced here.

The storage provider is infrastructure detail behind the
`UploadThingClient` interface; exchanging the provider shall not
change the API contract (FR-13-03).

---

## 1. Architecture fit

The feature follows the mandated layering:

```text
api/v1/documents.py        Router (no business logic)
        ↓
services/documents.py      DocumentProcessingService (business logic)
        ↓
repositories/documents.py  DocumentRepository (data access)
        ↓
db/models/document.py      Document (SQLAlchemy model)
```

The LLM layer is an infrastructure client injected into the
service (`services/llm.py`); it contains no curriculum business
logic. The storage layer is equally external: `services/
uploadthing.py` implements the UploadThing storage protocol behind
the `UploadThingClient` interface and is injected the same way.

---

## 2. API contract

All endpoints are protected with JWT bearer authentication.

| Method | Path | Roles | Description |
| --- | --- | --- | --- |
| `POST` | `/api/v1/documents` | FACULTY, COMMITTEE_MEMBER, ADMIN | multipart upload field `file`; 201 + `DocumentResponse` |
| `GET` | `/api/v1/documents` | any authenticated | list documents (newest first) |
| `GET` | `/api/v1/documents/{document_id}` | any authenticated | document detail |
| `POST` | `/api/v1/documents/{document_id}/ingest` | FACULTY, COMMITTEE_MEMBER, ADMIN | extract text + LLM analysis; 200 |

`DocumentResponse` fields:

| Field | Type | Notes |
| --- | --- | --- |
| `id` | UUID | |
| `original_filename` | string | as uploaded |
| `file_extension` | string | normalized lowercase with leading dot |
| `content_type` | string \| null | declared by client; not trusted for validation |
| `size_bytes` | int | |
| `checksum_sha256` | string | hex digest of stored bytes |
| `status` | string | UPLOADED / PROCESSING / COMPLETED / FAILED |
| `llm_model` | string \| null | set on COMPLETED |
| `extracted_text` | string \| null | set on COMPLETED |
| `llm_analysis` | object \| null | parsed JSON from the LLM |
| `error_message` | string \| null | set on FAILED |
| `uploaded_by` | UUID | |
| `uploaded_at` | datetime | |
| `processed_at` | datetime \| null | |

Error responses use the shared error envelope
(`error.code`, `error.message`). Document-specific codes:

| HTTP | Code | Cause |
| --- | --- | --- |
| 400 | `empty_file` | zero-byte upload |
| 400 | `unsupported_file_type` | extension not in allow-list |
| 400 | `invalid_file_content` | binary signature mismatch / unreadable name |
| 404 | `not_found` | unknown document id |
| 409 | `document_processing` | ingestion already running |
| 413 | `file_too_large` | exceeds `max_upload_size_mb` |
| 503 | `llm_not_configured` | LLM provider missing during ingest |
| 503 | `storage_not_configured` | STORAGE provider not configured (upload / ingest) |
| 502 | `storage_provider_error` | storage provider rejected or failed the upload |

---

## 3. Data model

New table `documents` (see migration
`0003_document_ingestion`):

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID PK | default `gen_random_uuid()` |
| `original_filename` | `VARCHAR(255)` NOT NULL | basename stored |
| `file_extension` | `VARCHAR(10)` NOT NULL | lower-case, includes dot |
| `content_type` | `VARCHAR(100)` | raw declared content type |
| `size_bytes` | `BIGINT` NOT NULL | |
| `checksum_sha256` | `VARCHAR(64)` NOT NULL | |
| `storage_path` | `VARCHAR(500)` NOT NULL | provider-relative key (UploadThing file key) |
| `status` | `VARCHAR(20)` NOT NULL, CHECK | see FR-13-05 |
| `extracted_text` | `TEXT` | |
| `llm_analysis` | `JSONB` | parsed LLM JSON |
| `llm_model` | `VARCHAR(100)` | |
| `error_message` | `TEXT` | |
| `uploaded_by` | `UUID` → `users.id` | |
| `uploaded_at` / `processed_at` | `TIMESTAMPTZ` | |
| `updated_at` | `TIMESTAMPTZ` | set_updated_at trigger |

Indexes: `(uploaded_by, status)` query index. The checksum is
recorded for traceability but not enforced unique: re-uploads are
legitimate (BR-DP-06).

Document analysis references later steps instead of catalog rows
today; no FK to curricula versions until graph projection lands.

---

## 4. Storage layer (UploadThing)

Settings (all consumed through `Settings`):

| Setting | Default | Meaning |
| --- | --- | --- |
| `UPLOADTHING_TOKEN` | empty | base64 JSON token `{apiKey, appId, regions[]}` from the UploadThing dashboard (preferred) |
| `UPLOADTHING_API_KEY` / `UPLOADTHING_APP_ID` / `UPLOADTHING_REGION` | empty | alternative to the token for key-based setup; `REGION` required in this mode |
| `UPLOADTHING_INGEST_HOST` | `ingest.uploadthing.com` | ingest host (token override supported) |
| `UPLOADTHING_UFS_HOST` | `ufs.sh` | CDN host for signed file access |
| `UPLOADTHING_UFS_APP_ID_LOCATION` | `subdomain` | `subdomain` or `path` style access URLs |
| `UPLOADTHING_TIMEOUT_SECONDS` | `120` | provider request timeout |
| `MAX_UPLOAD_SIZE_MB` | `20` | hard upload ceiling |
| `ALLOWED_UPLOAD_EXTENSIONS` | `[".pdf", ".docx", ".txt", ".md", ".csv"]` | allow-list |

`build_uploadthing_client()` resolves credentials (token preferred,
then the key/app-id/region triple) and returns the client or `None`
when unconfigured; a partially provided key triple raises
`storage_not_configured` (EX-DP-09).

Protocol (mirrors the official `UTApi` server SDK, uploadthing
v7.x):

- **File key** — generated locally: a sha-style key of shuffled
  sqids alphabet seeded by the app id hash; 12-char app part +
  36-char file part (`djb2`-style `Hash.string` over UTF-16 code
  units, truncating JS modulo semantics). No user-supplied name
  survives into the key.
- **Upload** — `PUT {region}.ingest.uploadthing.com/{key}` with a
  locally HMAC-SHA256-signed presigned URL
  (`expires`, `x-ut-identifier`, `x-ut-file-name`, `x-ut-file-size`,
  `x-ut-file-type`, `x-ut-content-disposition`, `signature=
  hmac-sha256=...`), multipart field `file`, and headers
  `Range: bytes=0-` + `x-uploadthing-version`. The response carries
  `ufsUrl` / `fileHash`.
- **Read (ingest)** — GET on the signed access URL
  `https://{appId}.ufs.sh/f/{key}?expires=...&signature=...`
  (5-minute TTL), so both public and private files resolve without
  an API roundtrip.
- Query values are encoded exactly like JS `URLSearchParams`
  (space → `+`, `~` → `%7E`, uppercase percent-hex) so the signature
  covers the exact wire bytes.

Extraction branches on `file_extension`:

| Extension | Reader | Notes |
| --- | --- | --- |
| `.pdf` | `pypdf` | page-wise `extract_text()`; scanned PDFs yield empty text → FAILED |
| `.docx` | `python-docx` | paragraphs plus table cells |
| `.txt` / `.md` / `.csv` | UTF-8 decode | `errors="replace"` for stray bytes |

Signature checks for binary formats before persisting:

| Extension | Magic prefix |
| --- | --- |
| `.pdf` | `%PDF-` |
| `.docx` | `PK\x03\x04` |

---

## 5. LLM layer

`services/llm.py` defines:

- `LLMClient` protocol: `analyze_document(document_text,
  original_filename) -> dict` — thin transport, framework-agnostic.
- `LLMNotConfiguredError` (503) raised when `LLM_API_KEY` is
  absent at call time; the document stays `UPLOADED` (EX-DP-06).
- `LLMResponseError` for transport errors, non-2xx answers, and
  JSON that cannot be parsed; the service converts it to document
  status `FAILED` (EX-DP-07) instead of leaking transport details.
- `OpenAICompatibleLLMClient`: `POST {base_url}/chat/completions`
  with temperature `0` and a system prompt that demands a single
  JSON object (Fenced code blocks are stripped before parsing).
  `response_format` is not sent so Ollama/vLLM-style compatible
  servers keep working.
- `get_llm_client()` settings factory, injected via
  `get_llm_client` dependency so tests can substitute stubs.

Payload limits guard the LLM call: the prompt is truncated to
`DOCUMENT_TEXT_MAX_CHARS = 120_000` characters (roughly the token
budget of current models) before sending.

Extraction contract (advisory only, stored verbatim in
`llm_analysis`): program metadata, semesters, courses (code/name/
type/credits/semester/contact hours), course outcomes,
prerequisites, and a short summary, with unknown values as `null`
and empty arrays where absent.

---

## 6. Service flow

### Upload

```text
validate extension/name/size/empty/signature
  → buffer bytes (sha256 + byte count, size capped)
  → PUT to UploadThing ingest presigned URL   (EX-DP-10 → 502)
     storage unconfigured                     (EX-DP-09 → 503)
  → INSERT documents row (status UPLOADED, storage_path = file key)
     + audit log
  → COMMIT → 201 DocumentResponse
```

Any refusal happens before a UT call and before a row is created,
so rejected uploads leave no residue.

### Ingest

```text
404 unknown id → storage unconfigured → 503 (EX-DP-09)
SET status = PROCESSING (IF PROCESSING → 409), audit, COMMIT
  → download stored bytes via signed URL (EX-DP-08 → FAILED)
  → extract text by extension (EX-DP-05 → FAILED)
  → text.strip() empty → FAILED
  → llm_client.analyze_document(...)
        LLMNotConfiguredError → status back to UPLOADED, 503
        LLMResponseError      → status FAILED
        success               → llm_analysis, llm_model, COMPLETED
  → audit + COMMIT → 200 DocumentResponse
```

Re-ingest is idempotent (BR-DP-06) and always starts from the
stored file, never from previous output.

Concurrency note: the PROCESSING guard is a database read
(non-locking, single instance deployment acceptable for the local
increment); a distributed lock is not added until multi-node
deployments are introduced.

---

## 7. Test plan

Unit / API tests (`tests/test_document_api.py`):

- Faculty upload happy path (`.txt`): 201, metadata, checksum,
  status UPLOADED, bytes recorded by the stub storage client.
- Reviewer cannot upload (403); anonymous cannot upload (401).
- Rejections: empty file, unsupported extension, oversized file,
  PDF signature mismatch (400/413 mapping).
- Storage unconfigured → upload/ingest return 503
  `storage_not_configured`; document stays UPLOADED.
- Storage provider failure → 502 `storage_provider_error`, no row.
- List + detail endpoints (fields, ordering).
- Ingest happy path with stub LLM client: text extraction,
  `llm_analysis` persisted, status COMPLETED, model recorded.
- Ingest with PDF fixture (pypdf) exercising the PDF branch.
- Stub LLM raising `LLMResponseError` → FAILED + error_message.
- Real factory default (no API key in test env) → ingest returns
  503 `llm_not_configured` and document stays UPLOADED.
- Unknown id ingest → 404.
- Re-ingest overwrite (BR-DP-06).

Storage-client unit tests (official port parity):

- `effect_hash_string` reference vectors (`"" -> 5381`,
  `"hello" -> 181380007`, `"world" -> 164394279`).
- JS `URLSearchParams` encoding vectors (space → `+`,
  `~` → `%7E`, `%3D` signatures).
- File key shape (length ≥ 48, sqids alphabet only,
  deterministic app prefix) and token parsing.

Run with `uv run pytest` and `uv run ruff check .` from
`backend/`.

---

## 8. Frontend (curriculum UI)

The Next.js client mirrors the API contract:

- `lib/api.ts` — `Document` type plus `uploadDocument`,
  `listDocuments`, `getDocument`, and `ingestDocument`. The shared
  `request` wrapper sends the bearer token and must not set
  `Content-Type` on multipart `FormData` bodies.
- `app/documents/page.tsx` — document workspace: upload form,
  document list with status badges, expandable detail panel
  (metadata, extracted text, parsed AI analysis, error reason),
  and an `Analyze` action that calls the ingest endpoint.
- Upload/ingest controls are rendered only for users holding
  FACULTY, COMMITTEE_MEMBER, or ADMIN roles; REVIEWER sees
  read-only data. The server remains the authorization source of
  truth (BR-DP-01).
- Client-side validation (extension allow-list, empty file, size
  ceiling) mirrors BR-DP-02/03 for fast feedback; the API rejects
  invalid uploads regardless.
- The dashboard workspace grid links to `/documents` as the first
  available module.
- Cross-origin uploads from the dev UI are permitted via
  `CORS_ALLOW_ORIGIN_REGEX`, which by default accepts any
  `localhost` / `127.0.0.1` / private-range address on any port the
  Next.js dev server may bind (3000, 3001, or a LAN address).
