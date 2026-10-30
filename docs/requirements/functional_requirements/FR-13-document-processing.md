
# FR-13: Curriculum Document Processing

## Description

The Curriculum Document Processing module shall allow authorized
users to upload curriculum documents (syllabi, curriculum
packages, mapping reports) so their content can be ingested and
analyzed by the AI / LLM layer.

The system shall store uploaded documents durably, extract the
textual content of the stored document, pass the extracted text
to the LLM analysis layer, and record the analysis result and
processing status together with the document.

This requirement covers the Document Processing branch of the
system architecture (upload → ingest → NLP/LLM layer). Projection
of the analysis result into the Neo4j curriculum graph is covered
by future requirements.

---

## Actors

### Primary Actors

- **Faculty / Instructor** — Uploads curriculum documents for analysis.
- **Curriculum Committee Member** — Uploads curriculum documents
  and reviews analysis results.

### Secondary Actors

- **Admin** — Uploads curriculum documents, manages processing
  configuration where permitted, and views all stored documents.
- **Reviewer** — Views stored documents and analysis results.

---

## Functional Requirements

### FR-13-01: Upload Curriculum Document

The system shall allow authorized users to upload a document using
a multipart upload request.

For each upload the system shall record:

- The original file name
- The declared content type
- The file size
- A content checksum
- The stored file location
- The uploading user
- The processing status

### FR-13-02: Validate Uploaded File

The system shall validate uploads before storage:

- The file must not be empty.
- The file name must have an allowed extension.
- The file size must not exceed the configured maximum.
- Binary formats must match their expected content signature.
- The stored name shall not expose the original file name
  (path traversal / name spoofing protection).

### FR-13-03: Store Uploaded Document Locally

The system shall persist the uploaded file in local file system
storage under a configured upload directory.

Files shall be organized so that a document row can locate its
stored file unambiguously.

Local storage is the storage backend for this increment; moving
uploads to a cloud object store shall only affect the storage
layer, not the API contract.

### FR-13-04: Ingest Stored Document

The system shall allow authorized users to trigger ingestion of a
stored document.

Ingestion shall:

- Extract the text content of the stored file according to its
  format (PDF, DOCX, plain text / Markdown / CSV).
- Detect documents that contain no extractable text.
- Pass the extracted text to the LLM analysis layer.
- Store the extracted text, the LLM model identifier, and the
  analysis output together with the document.

### FR-13-05: Track Document Processing Status

The system shall maintain a processing status for every document:

- `UPLOADED` — stored but not yet ingested
- `PROCESSING` — ingestion in progress
- `COMPLETED` — text extracted and LLM analysis recorded
- `FAILED` — ingestion failed; a reason shall be recorded

Users shall be able to view the status at any time.

### FR-13-06: View Documents and Analysis Results

The system shall allow authenticated users to:

- List all uploaded documents with their statuses.
- View the details of a single document, including metadata,
  extracted text, and LLM analysis output where available.

---

## Business Rules

### BR-DP-01: Authorized Upload

Only users with the Faculty, Curriculum Committee Member, or Admin
role shall upload documents and trigger ingestion. All other
authenticated roles have read access.

### BR-DP-02: Allowed Formats

Documents shall only be accepted for the configured format
allow-list (regulated by deployment configuration). Rejected
uploads shall not create a document record.

### BR-DP-03: Size Limit

Uploads exceeding the configured maximum size shall be rejected
before storage completes.

### BR-DP-04: Traceability

Every document record shall identify the uploading user, the
stored file, and the checksum of the content that was analyzed.

### BR-DP-05: Analysis Traceability

Each analysis result shall record the LLM model that produced it.
Analysis results are advisory content for later verification and
graph-projection steps; they shall not modify curriculum data.

### BR-DP-06: Ingestion Re-runs

Re-running ingestion shall overwrite the stored extraction and
analysis results and update the checksum-verified content status.

---

## Preconditions

- The user is authenticated.
- The user has the required permission (upload / ingest actions).
- The upload storage directory is configured and writable.
- The LLM provider is configured for ingestion (misses are
  reported as a service configuration error).

---

## Postconditions

### On Successful Upload

- The file is stored in local storage.
- A document record with status `UPLOADED` is created.
- The upload is recorded in the audit history.

### On Successful Ingestion

- The extracted text is stored on the document record.
- The LLM analysis output is stored on the document record.
- The document status becomes `COMPLETED`.
- Ingestion is recorded in the audit history.

### On Failed Ingestion

- The document status becomes `FAILED`.
- A human-readable failure reason is recorded.
- No partially analyzed data is presented as analysis output.

---

## Dependencies

This requirement depends on:

- User and Role Management (FR-01)

Document processing shall be consumed by:

- Curriculum verification (content findings, later FRs)
- Curriculum graph projection in Neo4j (future requirements)
- Verification reporting

---

## Validation Rules

### VR-DP-01: File Validation

- An empty upload is rejected.
- An unknown or disallowed extension is rejected.
- An oversized file is rejected.
- A file whose binary signature does not match its declared
  format extension is rejected.

### VR-DP-02: Existence Validation

- Ingestion of an unknown document identifier is rejected.

### VR-DP-03: State Validation

- Only stored documents can be ingested.
- A document that is currently processing shall not start a
  second concurrent ingestion.

---

## Exceptions / Edge Cases

### EX-DP-01: Empty Upload

The upload is rejected with an appropriate client error.

### EX-DP-02: Unsupported Format

The upload is rejected and no document record is created.

### EX-DP-03: Oversized Upload

The upload is rejected with a payload-too-large error.

### EX-DP-04: Content Signature Mismatch

A binary upload whose signature does not match its extension is
rejected as invalid content.

### EX-DP-05: No Extractable Text

The document transitions to `FAILED` with a reason stating that no
text was extractable (e.g. scanned PDFs are out of scope until OCR
is introduced).

### EX-DP-06: LLM Provider Not Configured

Ingestion ends with a service-unavailable error indicating the
LLM provider is not configured; the document remains `UPLOADED`.

### EX-DP-07: LLM Provider Failure

A transport or unparsable-response failure marks the document as
`FAILED` with the recorded reason and shall not crash the API.

### EX-DP-08: Stored File Missing

If the stored file cannot be read at ingestion time, the document
transitions to `FAILED` with the recorded reason.

---

## Outcome

Upon successful implementation of this requirement:

- Curriculum documents can be uploaded by authorized users.
- Uploads are validated and stored in durable local storage.
- Documents can be ingested on demand.
- Text is extracted according to document format.
- Extracted text is passed to the LLM analysis layer.
- Analysis output and processing status are stored and visible.
- Storage can later be replaced by cloud object storage without
  changing the API contract.
