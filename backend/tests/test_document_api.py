import base64
import hashlib
import io
import json
import uuid
from collections.abc import Callable
from unittest import mock

import httpx
import pytest
from docx import Document as DocxBuilder

from app.api.deps import get_llm_client, get_uploadthing_client
from app.services.llm import LLMResponseError, OpenAICompatibleLLMClient
from app.services.uploadthing import (
    _KEY_ALPHABET,
    UPLOADTHING_VERSION,
    HttpxUploadThingClient,
    UploadThingCredentials,
    UploadThingError,
    UploadThingNotConfiguredError,
    _credentials_from_token,
    _generate_file_key,
    _js_query_encode,
    _sign_url,
    effect_hash_string,
)
from tests.conftest import bearer


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


def file_without_storage(client):
    client.app.dependency_overrides[get_uploadthing_client] = lambda: None


def file_with_provider_failure(client):
    class FailingStorage:
        def upload_file(self, data, filename, content_type=None):
            raise UploadThingError("ingest down")

        def read_file(self, key):
            raise UploadThingError("ingest down")

    client.app.dependency_overrides[get_uploadthing_client] = lambda: FailingStorage()


def restore_default_storage(client, stub):
    client.app.dependency_overrides[get_uploadthing_client] = lambda: stub


def upload_file(client, token, *, filename, content, content_type=None):
    return client.post(
        "/api/v1/documents",
        files=[("file", (filename, content, content_type or "application/octet-stream"))],
        headers=bearer(token),
    )


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


def test_faculty_can_upload_text_document(client, faculty_token, storage_stub):
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
    upload = storage_stub.uploads[-1]
    assert upload["data"] == content
    assert upload["filename"] == "curriculum-draft.txt"


def test_uploaded_files_never_keep_the_original_name(client, faculty_token, storage_stub):
    response = upload_file(
        client,
        faculty_token,
        filename="../../etc/passwd.txt",
        content=b"harmless",
    )

    assert response.status_code == 201
    body = response.json()
    assert body["original_filename"] == "passwd.txt"
    assert storage_stub.uploads[-1]["filename"] == "passwd.txt"
    assert storage_stub.uploads[-1]["data"] == b"harmless"


def test_docx_upload_is_accepted(client, faculty_token, storage_stub):
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
    assert storage_stub.uploads[-1]["data"] is not None


def test_upload_requires_authentication(client):
    response = upload_file(client, None, filename="curriculum.txt", content=b"data")
    assert response.status_code == 401


def test_green_upload_rejects_invalid_content_without_calling_storage(
    client, faculty_token, storage_stub
):
    response = upload_file(
        client, faculty_token, filename="fake.pdf", content=b"not a pdf at all"
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_file_content"
    assert storage_stub.uploads == []


def test_upload_without_storage_configuration_returns_service_unavailable(
    client, faculty_token, storage_stub
):
    file_without_storage(client)
    try:
        response = upload_file(
            client, faculty_token, filename="ok.txt", content=b"data"
        )
    finally:
        restore_default_storage(client, storage_stub)

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "storage_not_configured"
    assert storage_stub.uploads == []


def test_upload_storage_provider_failure_returns_bad_gateway(
    client, faculty_token, storage_stub
):
    file_with_provider_failure(client)
    try:
        response = upload_file(
            client, faculty_token, filename="ok.txt", content=b"data"
        )
    finally:
        restore_default_storage(client, storage_stub)

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "storage_provider_error"


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


def test_ingest_without_storage_configuration_returns_service_unavailable(
    client, faculty_token, storage_stub
):
    uploaded = upload_file(
        client, faculty_token, filename="syllabus.txt", content=b"content"
    )
    document_id = uploaded.json()["id"]
    file_without_storage(client)
    try:
        response = client.post(
            f"/api/v1/documents/{document_id}/ingest", headers=bearer(faculty_token)
        )
    finally:
        restore_default_storage(client, storage_stub)

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "storage_not_configured"
    stored = client.get(
        f"/api/v1/documents/{document_id}", headers=bearer(faculty_token)
    )
    assert stored.json()["status"] == "UPLOADED"


def test_ingest_read_failure_marks_document_failed(
    client, faculty_token, storage_stub
):
    uploaded = upload_file(
        client, faculty_token, filename="syllabus.txt", content=b"content"
    )
    document_id = uploaded.json()["id"]
    storage_stub.files.clear()
    response = client.post(
        f"/api/v1/documents/{document_id}/ingest", headers=bearer(faculty_token)
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "FAILED"
    assert "Stored file could not be downloaded" in body["error_message"]


# ------------------------------------------------------- storage client parity


def test_effect_hash_matches_reference_vectors():
    assert effect_hash_string("") == 5381
    assert effect_hash_string("hello") == 181380007
    assert effect_hash_string("world") == 164394279


def test_js_query_encoding_matches_urlsearchparams():
    assert _js_query_encode("a b") == "a+b"
    assert _js_query_encode("~x*") == "%7Ex*"
    assert _js_query_encode("hmac-sha256=abc") == "hmac-sha256%3Dabc"
    assert _js_query_encode("curriculum file.pdf") == "curriculum+file.pdf"


def test_file_key_shape_and_deterministic_prefix():
    first = _generate_file_key(
        "app123", "curriculum.pdf", 100, "application/pdf", 1700000000000
    )
    second = _generate_file_key(
        "app123", "curriculum.pdf", 100, "application/pdf", 1700000000000
    )
    other = _generate_file_key(
        "app987", "curriculum.pdf", 100, "application/pdf", 1700000000000
    )
    assert len(first) >= 48
    assert set(first) <= set(_KEY_ALPHABET)
    assert first[:12] == second[:12]
    assert first[:12] != other[:12]


def test_token_credentials_are_parsed():
    token = base64.b64encode(
        json.dumps(
            {"apiKey": "sk_live_abc", "appId": "ap1", "regions": ["fra1"]}
        ).encode()
    ).decode()
    credentials = _credentials_from_token(
        token, "ingest.uploadthing.com", "ufs.sh", "subdomain"
    )
    assert credentials.api_key == "sk_live_abc"
    assert credentials.app_id == "ap1"
    assert credentials.ingest_url == "https://fra1.ingest.uploadthing.com"
    assert credentials.ufs_url_base == "https://ap1.ufs.sh"


def test_invalid_token_reports_configuration_error():
    with pytest.raises(UploadThingNotConfiguredError):
        _credentials_from_token("broken", "ingest.uploadthing.com", "ufs.sh", "subdomain")


def make_protocol_client(handler: Callable[[httpx.Request], httpx.Response]):
    credentials = UploadThingCredentials(
        api_key="sk_test_secret",
        app_id="app123",
        ingest_url="https://fra1.ingest.uploadthing.com",
        ufs_url_base="https://app123.ufs.sh",
        ufs_app_id_location="subdomain",
    )
    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    return HttpxUploadThingClient(credentials, timeout_seconds=5, http_client=http_client)


def test_upload_request_matches_uploadthing_protocol():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["path"] = request.url.raw.raw_path.decode("utf-8")
        captured["headers"] = dict(request.headers)
        captured["body"] = request.content
        return httpx.Response(
            200, json={"ufsUrl": "https://app123.ufs.sh/f/out", "fileHash": "ff"}
        )

    with mock.patch("app.services.uploadthing._utc_now_ms", return_value=1700000000000):
        uploaded = make_protocol_client(handler).upload_file(
            b"hello world", "curriculum file.pdf", "application/pdf"
        )

    assert uploaded.key and uploaded.ufs_url == "https://app123.ufs.sh/f/out"
    assert uploaded.file_hash == "ff"
    assert captured["method"] == "PUT"
    assert captured["path"].startswith(f"/{uploaded.key}?")
    assert "curriculum+file.pdf" in captured["path"]
    assert captured["headers"]["range"] == "bytes=0-"
    assert captured["headers"]["x-uploadthing-version"] == UPLOADTHING_VERSION
    wire_source = f"https://fra1.ingest.uploadthing.com{captured['path']}".split(
        "&signature="
    )[0]
    signature = captured["path"].split("&signature=")[1]
    assert signature == "hmac-sha256%3D" + _sign_url(wire_source, "sk_test_secret").split("=")[1]
    assert b"hello world" in captured["body"]


def test_read_request_matches_uploadthing_protocol():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.raw.raw_path.decode("utf-8")
        return httpx.Response(200, content=b"\x00\x01readme")

    with mock.patch("app.services.uploadthing._utc_now_ms", return_value=1700000000000):
        data = make_protocol_client(handler).read_file("readkey123")

    assert data == b"\x00\x01readme"
    assert captured["path"].startswith("/f/readkey123?expires=1700000300000&signature=")
    wire_source = f"https://app123.ufs.sh{captured['path']}".split("&signature=")[0]
    signature = captured["path"].split("&signature=")[1]
    assert signature == "hmac-sha256%3D" + _sign_url(wire_source, "sk_test_secret").split("=")[1]
