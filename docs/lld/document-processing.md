# Document Processing — LLD

## Scope

This document defines the low-level design for FR-13 (Curriculum
Document Processing): document upload, local-disk storage, text
extraction, and passing extracted text to the LLM analysis layer.

Neo4j graph projection of the analysis result is out of scope
(see `database-schema.md` section 7) and will consume the stored
analysis payload produced here.

Cloud object storage is a future storage-backend swap; the API
contract does not change (FR-13-03).

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
logic. RNG-free filesystem access (save/read of the stored file)
lives in the service behind small helper methods so a future
cloud-storage backend can replace it.

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
| `storage_path` | `VARCHAR(500)` NOT NULL | provider-relative key |
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

## 4. Storage layout (local)

Settings (all consumed by the service through `Settings`):

| Setting | Default | Meaning |
| --- | --- | --- |
| `UPLOAD_DIR` | `local-storage/documents` | local document root |
| `MAX_UPLOAD_SIZE_MB` | `20` | hard upload ceiling |
| `ALLOWED_UPLOAD_EXTENSIONS` | `[".pdf", ".docx", ".txt", ".md", ".csv"]` | allow-list |
| `LLM_BASE_URL` | `https://api.openai.com/v1` | OpenAI-compatible base |
| `LLM_API_KEY` | empty | absence = not configured |
| `LLM_MODEL` | `gpt-4o-mini` | model identifier |
| `LLM_TIMEOUT_SECONDS` | `120` | request timeout |

Stored path (provider-relative key persisted as `storage_path`):

```text
<UPLOAD_DIR>/<uploaded_at:YYYY>/<MM>/<document_id><extension>
```

- `document_id` is assigned before streaming, so the final name
  never depends on the user-supplied file name.
- Content is streamed to `<final>.part` and renamed atomically.
- `storage_path` intentionally contains no absolute path so the
  same rows can move to object storage later.

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
validate extension/size/empty/signature
  → stream to <UPLOAD_DIR>/YYYY/MM/<id><ext>.part     (sha256 + byte count)
  → rename to final name
  → INSERT documents row (status UPLOADED) + audit log
  → COMMIT → 201 DocumentResponse
```

Any refusal happens before the file is persisted and before a row
is created, so rejected uploads leave no residue.

### Ingest

```text
SET status = PROCESSING (IF PROCESSING → 409), audit, COMMIT
  → read file bytes (EX-DP-08 → FAILED)
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
  status UPLOADED, file exists on disk.
- Reviewer cannot upload (403); anonymous cannot upload (401).
- Rejections: empty file, unsupported extension, oversized file,
  PDF signature mismatch (400/413 mapping).
- List + detail endpoints (fields, ordering).
- Ingest happy path with stub LLM client: text extraction,
  `llm_analysis` persisted, status COMPLETED, model recorded.
- Ingest with PDF fixture (pypdf) exercising the PDF branch.
- Stub LLM raising `LLMResponseError` → FAILED + error_message.
- Real factory default (no API key in test env) → ingest returns
  503 `llm_not_configured` and document stays UPLOADED.
- Unknown id ingest → 404.
- Re-ingest overwrite (BR-DP-06).

Run with `uv run pytest` and `uv run ruff check .` from
`backend/`.
