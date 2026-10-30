import hashlib
import io
import os
import uuid

from docx import Document as DocxBuilder

from app.api.deps import get_llm_client
from app.services.llm import LLMResponseError, OpenAICompatibleLLMClient
from tests.conftest import bearer

UPLOADS_ROOT = os.environ["UPLOAD_DIR"]


class StubLLMClient:
    model = "stub-model"

    def __init__(self, result: dict | None = None, error: Exception | None = None):
        self.result = result or {"summary": "stub analysis", "courses": []}
        self.error = error
        self.calls: list[tuple[str, str]] = []

    def analyze_document(self, document_text: str, original_filename: str) -> dict:
        self.calls.append((document_text, original_filename))
        if self.error is not None:
            raise self.error
        return self.result


def override_llm(client, stub):
    client.app.dependency_overrides[get_llm_client] = lambda: stub


def release_llm(client):
    client.app.dependency_overrides.pop(get_llm_client, None)


def upload_file(client, token, *, filename, content, content_type=None):
    return client.post(
        "/api/v1/documents",
        files=[("file", (filename, content, content_type or "application/octet-stream"))],
        headers=bearer(token),
    )


def find_stored_file(document_id: str, extension: str) -> bytes | None:
    for root, _, names in os.walk(UPLOADS_ROOT):
        for name in names:
            if name == f"{document_id}{extension}":
                with open(os.path.join(root, name), "rb") as handle:
                    return handle.read()
    return None


def make_minimal_pdf(text: str) -> bytes:
    content = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("latin-1")
    objects = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        (
            b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
        ),
        b"4 0 obj\n<< /Length " + str(len(content)).encode() + b" >>\nstream\n"
        + content
        + b"\nendstream\nendobj\n",
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
    ]
    buffer = io.BytesIO()
    buffer.write(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(buffer.tell())
        buffer.write(obj)
    xref_position = buffer.tell()
    entries = [b"0000000000 65535 f\n"]
    for offset in offsets[1:]:
        entries.append(f"{offset:010d} 00000 n\n".encode())
    buffer.write(b"xref\n0 6\n")
    buffer.write(b"".join(entries))
    buffer.write(b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n")
    buffer.write(str(xref_position).encode())
    buffer.write(b"\n%%EOF\n")
    return buffer.getvalue()


def make_docx(paragraphs: list[str], table: list[list[str]] | None = None) -> bytes:
    builder = DocxBuilder()
    for paragraph in paragraphs:
        builder.add_paragraph(paragraph)
    if table:
        rows = len(table)
        columns = len(table[0])
        grid = builder.add_table(rows=rows, cols=columns)
        for row_index, row in enumerate(table):
            for column_index, value in enumerate(row):
                grid.cell(row_index, column_index).text = value
    buffer = io.BytesIO()
    builder.save(buffer)
    return buffer.getvalue()


# ---------------------------------------------------------------- unit helpers


def test_minimal_pdf_fixture_is_extractable():
    from pypdf import PdfReader

    pdf_bytes = make_minimal_pdf("Hello Curriculum Draft")
    reader = PdfReader(io.BytesIO(pdf_bytes))
    assert "Hello Curriculum Draft" in "\n".join(
        page.extract_text() or "" for page in reader.pages
    )


# ----------------------------------------------------------------- upload API


def test_faculty_can_upload_text_document(client, faculty_token):
    content = b"B.Tech CSE curriculum draft ppt"

    response = upload_file(
        client,
        faculty_token,
        filename="curriculum-draft.txt",
        content=content,
        content_type="text/plain",
    )

    assert response.status_code == 201
    body = response.json()
    assert body["original_filename"] == "curriculum-draft.txt"
    assert body["file_extension"] == ".txt"
    assert body["content_type"] == "text/plain"
    assert body["status"] == "UPLOADED"
    assert body["size_bytes"] == len(content)
    assert body["checksum_sha256"] == hashlib.sha256(content).hexdigest()
    assert uuid.UUID(body["id"])
    assert find_stored_file(body["id"], ".txt") == content


def test_uploaded_files_never_keep_the_original_name(client, faculty_token):
    response = upload_file(
        client,
        faculty_token,
        filename="../../etc/passwd.txt",
        content=b"harmless",
    )

    assert response.status_code == 201
    body = response.json()
    assert body["original_filename"] == "passwd.txt"
    stored = find_stored_file(body["id"], ".txt")
    assert stored == b"harmless"


def test_docx_upload_is_accepted(client, faculty_token):
    response = upload_file(
        client,
        faculty_token,
        filename="syllabus.DOCX",
        content=make_docx(["Syllabus Content"]),
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    assert response.status_code == 201
    body = response.json()
    assert body["file_extension"] == ".docx"
    assert find_stored_file(body["id"], ".docx") is not None


def test_upload_requires_authentication(client):
    response = upload_file(client, None, filename="curriculum.txt", content=b"data")
    assert response.status_code == 401


def test_reviewer_cannot_upload(client, reviewer_token):
    response = upload_file(
        client, reviewer_token, filename="curriculum.txt", content=b"data"
    )
    assert response.status_code == 403


def test_upload_rejects_empty_file(client, faculty_token):
    response = upload_file(client, faculty_token, filename="empty.txt", content=b"")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "empty_file"


def test_upload_rejects_unsupported_extension(client, faculty_token):
    response = upload_file(
        client, faculty_token, filename="payload.exe", content=b"MZFake"
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "unsupported_file_type"


def test_upload_rejects_file_without_extension(client, faculty_token):
    response = upload_file(client, faculty_token, filename="readme", content=b"data")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "unsupported_file_type"


def test_upload_rejects_oversized_file(client, faculty_token):
    response = upload_file(
        client, faculty_token, filename="big.txt", content=b"x" * (1024 * 1024 + 1)
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "file_too_large"


def test_upload_rejects_signature_mismatch(client, faculty_token):
    response = upload_file(
        client, faculty_token, filename="fake.pdf", content=b"not a pdf at all"
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_file_content"


# -------------------------------------------------------------------- reading


def test_any_authenticated_user_can_list_documents(
    client, faculty_token, committee_token, reviewer_token
):
    first = upload_file(
        client, faculty_token, filename="cs101.txt", content=b"CS101 syllabus"
    )
    second = upload_file(
        client, committee_token, filename="cs201.txt", content=b"CS201 syllabus"
    )
    assert first.status_code == 201 and second.status_code == 201

    listed = client.get("/api/v1/documents", headers=bearer(reviewer_token))

    assert listed.status_code == 200
    ids = {item["id"] for item in listed.json()}
    assert ids == {first.json()["id"], second.json()["id"]}


def test_document_detail_and_missing_document(client, reviewer_token, faculty_token):
    uploaded = upload_file(
        client, faculty_token, filename="detail.txt", content=b"content"
    )
    document_id = uploaded.json()["id"]

    detail = client.get(f"/api/v1/documents/{document_id}", headers=bearer(reviewer_token))
    assert detail.status_code == 200
    assert detail.json()["original_filename"] == "detail.txt"

    missing = client.get(
        f"/api/v1/documents/{uuid.uuid4()}", headers=bearer(reviewer_token)
    )
    assert missing.status_code == 404


# ------------------------------------------------------------------- ingestion


def test_ingest_passes_document_to_llm(client, faculty_token):
    uploaded = upload_file(
        client,
        faculty_token,
        filename="syllabus.txt",
        content=b"B.Tech CSE regulation 2026. Semester 1: CS101.",
    )
    document_id = uploaded.json()["id"]
    stub = StubLLMClient(result={"summary": "one course", "courses": []})
    override_llm(client, stub)
    try:
        response = client.post(
            f"/api/v1/documents/{document_id}/ingest", headers=bearer(faculty_token)
        )
    finally:
        release_llm(client)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "COMPLETED"
    assert body["llm_model"] == "stub-model"
    assert body["llm_analysis"] == {"summary": "one course", "courses": []}
    assert body["extracted_text"] == "B.Tech CSE regulation 2026. Semester 1: CS101."
    assert body["processed_at"] is not None
    assert stub.calls == [
        (
            "B.Tech CSE regulation 2026. Semester 1: CS101.",
            "syllabus.txt",
        )
    ]


def test_ingest_docx_document(client, faculty_token):
    docx_bytes = make_docx(
        ["Course: CS101 Programming Fundamentals"],
        table=[["CO1", "Apply control structures"]],
    )
    uploaded = upload_file(
        client, faculty_token, filename="cs101-co.docx", content=docx_bytes
    )
    document_id = uploaded.json()["id"]
    override_llm(client, StubLLMClient())
    try:
        response = client.post(
            f"/api/v1/documents/{document_id}/ingest", headers=bearer(faculty_token)
        )
    finally:
        release_llm(client)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "COMPLETED"
    text = body["extracted_text"]
    assert "Course: CS101 Programming Fundamentals" in text
    assert "Apply control structures" in text


def test_ingest_pdf_document(client, faculty_token):
    uploaded = upload_file(
        client,
        faculty_token,
        filename="regulation.pdf",
        content=make_minimal_pdf("Hello Curriculum Draft"),
        content_type="application/pdf",
    )
    document_id = uploaded.json()["id"]
    override_llm(client, StubLLMClient())
    try:
        response = client.post(
            f"/api/v1/documents/{document_id}/ingest", headers=bearer(faculty_token)
        )
    finally:
        release_llm(client)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "COMPLETED"
    assert "Hello Curriculum Draft" in body["extracted_text"]


def test_ingest_llm_failure_marks_document_failed(client, faculty_token):
    uploaded = upload_file(
        client, faculty_token, filename="syllabus.txt", content=b"some content"
    )
    document_id = uploaded.json()["id"]
    override_llm(client, StubLLMClient(error=LLMResponseError("bad answer")))
    try:
        response = client.post(
            f"/api/v1/documents/{document_id}/ingest", headers=bearer(faculty_token)
        )
    finally:
        release_llm(client)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "FAILED"
    assert "LLM analysis failed" in body["error_message"]


def test_ingest_without_extractable_text_marks_document_failed(client, faculty_token):
    uploaded = upload_file(
        client, faculty_token, filename="blank.txt", content=b"   \n\t"
    )
    document_id = uploaded.json()["id"]
    override_llm(client, StubLLMClient())
    try:
        response = client.post(
            f"/api/v1/documents/{document_id}/ingest", headers=bearer(faculty_token)
        )
    finally:
        release_llm(client)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "FAILED"
    assert "No extractable text" in body["error_message"]


def test_ingest_without_llm_configuration_returns_service_unavailable(
    client, faculty_token
):
    uploaded = upload_file(
        client, faculty_token, filename="syllabus.txt", content=b"content"
    )
    document_id = uploaded.json()["id"]
    unconfigured = OpenAICompatibleLLMClient(
        base_url="https://example.invalid/v1",
        api_key=None,
        model="gpt-4o-mini",
        timeout_seconds=5,
    )
    client.app.dependency_overrides[get_llm_client] = lambda: unconfigured
    try:
        response = client.post(
            f"/api/v1/documents/{document_id}/ingest", headers=bearer(faculty_token)
        )
    finally:
        release_llm(client)

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "llm_not_configured"
    stored = client.get(
        f"/api/v1/documents/{document_id}", headers=bearer(faculty_token)
    )
    assert stored.json()["status"] == "UPLOADED"


def test_ingest_repeatedly_overwrites_previous_results(client, faculty_token):
    uploaded = upload_file(
        client, faculty_token, filename="syllabus.txt", content=b"content v1"
    )
    document_id = uploaded.json()["id"]

    override_llm(client, StubLLMClient(result={"summary": "first"}))
    try:
        first = client.post(
            f"/api/v1/documents/{document_id}/ingest", headers=bearer(faculty_token)
        )
    finally:
        release_llm(client)
    assert first.json()["llm_analysis"] == {"summary": "first"}

    override_llm(client, StubLLMClient(result={"summary": "second"}))
    try:
        second = client.post(
            f"/api/v1/documents/{document_id}/ingest", headers=bearer(faculty_token)
        )
    finally:
        release_llm(client)

    assert second.status_code == 200
    assert second.json()["status"] == "COMPLETED"
    assert second.json()["llm_analysis"] == {"summary": "second"}


def test_reviewer_cannot_ingest(client, reviewer_token, faculty_token):
    uploaded = upload_file(
        client, faculty_token, filename="syllabus.txt", content=b"content"
    )
    document_id = uploaded.json()["id"]

    response = client.post(
        f"/api/v1/documents/{document_id}/ingest", headers=bearer(reviewer_token)
    )

    assert response.status_code == 403


def test_ingest_unknown_document_returns_404(client, faculty_token):
    response = client.post(
        f"/api/v1/documents/{uuid.uuid4()}/ingest", headers=bearer(faculty_token)
    )
    assert response.status_code == 404
