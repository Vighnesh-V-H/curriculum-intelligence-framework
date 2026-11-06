import io
from typing import Any

from app.api.deps import get_llm_client
from app.services.llm import LLMNotConfiguredError, LLMResponseError
from tests.conftest import bearer


class StubDraftLLMClient:
    model = "stub-model"

    def __init__(self, result: dict | None = None, error: Exception | None = None):
        self.result = result or make_draft_payload()
        self.error = error
        self.calls: list[str] = []

    def draft_curriculum(self, document_text: str) -> dict[str, Any]:
        self.calls.append(document_text)
        if self.error is not None:
            raise self.error
        return self.result


def override_llm(client, stub):
    client.app.dependency_overrides[get_llm_client] = lambda: stub


def release_llm(client):
    client.app.dependency_overrides.pop(
        get_llm_client, None
    )


def generate(client, token, entries: list[tuple[str, bytes]]) -> Any:
    return client.post(
        "/api/v1/curriculum-drafts",
        files=[
            ("files", (name, content, "text/plain")) for name, content in entries
        ],
        headers=bearer(token) if token else None,
    )


def make_draft_payload() -> dict[str, Any]:
    return {
        "program": {
            "name": "B.Tech Computer Science and Engineering",
            "degree": "B.Tech",
            "duration_years": 4,
            "summary": "Four-year undergraduate engineering program.",
        },
        "semesters": [
            {
                "semester_number": 1,
                "semester_name": "Semester 1",
                "focus": "Foundations",
                "courses": [
                    {
                        "code": "CS101",
                        "title": "Programming Fundamentals",
                        "credits": 4,
                        "category": "foundation",
                        "summary": "Introduces structured programming.",
                        "outcomes": [
                            {"code": "CO1", "statement": "Write basic programs."},
                            {"code": "CO2", "statement": "Apply control structures."},
                        ],
                    },
                    {
                        "code": "MA101",
                        "title": "Mathematics I",
                        "credits": 3,
                        "category": "foundation",
                        "summary": "Covers single-variable calculus.",
                        "outcomes": [
                            {"code": "CO1", "statement": "Solve limits and derivatives."},
                        ],
                    },
                ],
            },
            {
                "semester_number": 2,
                "semester_name": "Semester 2",
                "focus": "Core computing",
                "courses": [
                    {
                        "code": "CS201",
                        "title": "Data Structures",
                        "credits": 4,
                        "category": "core",
                        "summary": "Cores the classic data structures.",
                        "outcomes": [
                            {"code": "CO1", "statement": "Implement lists and trees."},
                            {"code": "CO2", "statement": "Analyze algorithm complexity."},
                        ],
                    },
                    {
                        "code": "CS202",
                        "title": "Digital Logic Lab",
                        "credits": 2,
                        "category": "lab",
                        "summary": "Hands-on digital logic design.",
                        "outcomes": [
                            {"code": "CO1", "statement": "Build basic circuits."},
                        ],
                    },
                ],
            },
        ],
        "peos": [
            {"code": "PEO1", "statement": "Graduates excel in engineering practice."},
            {"code": "PEO2", "statement": "Graduates pursue advanced studies."},
            {
                "code": "PEO3",
                "statement": "Graduates demonstrate ethics and leadership.",
            },
        ],
        "pos": [
            {"code": "PO1", "statement": "Apply engineering knowledge."},
            {"code": "PO2", "statement": "Analyze engineering problems."},
            {"code": "PO3", "statement": "Design engineering solutions."},
            {"code": "PO4", "statement": "Use modern engineering tools."},
            {"code": "PO5", "statement": "Act with professional ethics."},
        ],
        "mappings": [
            {
                "course_code": "CS101",
                "course_outcome_code": "CO1",
                "program_outcome_code": "PO1",
                "level": 3,
            },
            {
                "course_code": "CS101",
                "course_outcome_code": "CO2",
                "program_outcome_code": "PO2",
                "level": 2,
            },
            {
                "course_code": "MA101",
                "course_outcome_code": "CO1",
                "program_outcome_code": "PO1",
                "level": 1,
            },
            {
                "course_code": "CS201",
                "course_outcome_code": "CO1",
                "program_outcome_code": "PO3",
                "level": 3,
            },
            {
                "course_code": "CS202",
                "course_outcome_code": "CO1",
                "program_outcome_code": "PO5",
                "level": 2,
            },
        ],
    }


def make_draft_with_unknown_mapping_course() -> dict[str, Any]:
    payload = make_draft_payload()
    payload["mappings"][0]["course_code"] = "XX999"
    return payload


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


# ------------------------------------------------------------------- access


def test_draft_generation_requires_authentication(client):
    response = client.post("/api/v1/curriculum-drafts")
    assert response.status_code == 401


def test_reviewer_cannot_generate_draft(client, reviewer_token):
    response = generate(
        client, reviewer_token, [("syllabus.txt", b"CS101 syllabus")]
    )
    assert response.status_code == 403


def test_committee_member_and_admin_can_generate(
    client, committee_token, admin_token
):
    for token in (committee_token, admin_token):
        stub = StubDraftLLMClient()
        override_llm(client, stub)
        try:
            response = generate(client, token, [("syllabus.txt", b"CS101 syllabus")])
        finally:
            release_llm(client)
        assert response.status_code == 200


# ------------------------------------------------------------ file guards


def test_generate_rejects_no_files(client, faculty_token):
    response = client.post("/api/v1/curriculum-drafts", headers=bearer(faculty_token))
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "too_many_files"


def test_generate_rejects_too_many_files(client, faculty_token):
    entries = [(f"file-{index}.txt", b"content") for index in range(6)]
    response = generate(client, faculty_token, entries)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "too_many_files"


def test_generate_rejects_unsupported_extension(client, faculty_token):
    stub = StubDraftLLMClient()
    override_llm(client, stub)
    try:
        response = generate(client, faculty_token, [("payload.exe", b"MZFake")])
    finally:
        release_llm(client)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "unsupported_file_type"
    assert stub.calls == []


def test_generate_rejects_empty_file(client, faculty_token):
    response = generate(client, faculty_token, [("empty.txt", b"")])
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "empty_file"


def test_generate_rejects_oversized_file(client, faculty_token):
    response = generate(
        client, faculty_token, [("big.txt", b"x" * (1024 * 1024 + 1))]
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "file_too_large"


def test_generate_rejects_signature_mismatch(client, faculty_token):
    stub = StubDraftLLMClient()
    override_llm(client, stub)
    try:
        response = generate(client, faculty_token, [("fake.pdf", b"not a pdf at all")])
    finally:
        release_llm(client)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_file_content"
    assert stub.calls == []


def test_generate_rejects_files_without_extractable_text(client, faculty_token):
    stub = StubDraftLLMClient()
    override_llm(client, stub)
    try:
        response = generate(
            client,
            faculty_token,
            [("blank-a.txt", b"   \n\t"), ("blank-b.md", b"   \n\t")],
        )
    finally:
        release_llm(client)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "no_extractable_text"
    assert stub.calls == []


# ---------------------------------------------------------------- drafting


def test_generate_returns_draft_from_single_text_document(client, faculty_token):
    stub = StubDraftLLMClient()
    override_llm(client, stub)
    try:
        response = generate(
            client,
            faculty_token,
            [
                (
                    "syllabus.txt",
                    b"B.Tech CSE regulation 2026. Semester 1: CS101 Programming "
                    b"Fundamentals.",
                )
            ],
        )
    finally:
        release_llm(client)

    assert response.status_code == 200
    body = response.json()
    assert body["program"]["name"] == "B.Tech Computer Science and Engineering"
    assert body["program"]["duration_years"] == 4
    assert len(body["semesters"]) == 2
    assert [semester["semester_number"] for semester in body["semesters"]] == [1, 2]
    assert all(semester["courses"] for semester in body["semesters"])
    assert len(body["peos"]) == 3
    assert len(body["pos"]) == 5
    assert len(body["mappings"]) == 5
    assert all(mapping["level"] in (1, 2, 3) for mapping in body["mappings"])
    assert any(
        mapping["course_code"] == "CS101"
        and mapping["program_outcome_code"] == "PO1"
        for mapping in body["mappings"]
    )
    assert stub.calls == [
        (
            "= File: syllabus.txt =\n"
            "B.Tech CSE regulation 2026. Semester 1: CS101 Programming Fundamentals."
        )
    ]


def test_generate_combines_multiple_documents(client, faculty_token):
    stub = StubDraftLLMClient()
    override_llm(client, stub)
    try:
        response = generate(
            client,
            faculty_token,
            [
                ("syllabus.txt", b"CS101 syllabus text."),
                ("curriculum.md", b"# CS201 Data Structures outline."),
            ],
        )
    finally:
        release_llm(client)

    assert response.status_code == 200
    assert stub.calls == [
        (
            "= File: syllabus.txt =\n"
            "CS101 syllabus text.\n"
            "\n"
            "= File: curriculum.md =\n"
            "# CS201 Data Structures outline."
        )
    ]


def test_generate_supports_pdf_files(client, faculty_token):
    stub = StubDraftLLMClient()
    override_llm(client, stub)
    try:
        response = client.post(
            "/api/v1/curriculum-drafts",
            files=[
                (
                    "files",
                    (
                        "regulation.pdf",
                        make_minimal_pdf("CS101 Programming Fundamentals syllabus"),
                        "application/pdf",
                    ),
                )
            ],
            headers=bearer(faculty_token),
        )
    finally:
        release_llm(client)

    assert response.status_code == 200
    assert stub.calls == [
        (
            "= File: regulation.pdf =\n"
            "CS101 Programming Fundamentals syllabus"
        )
    ]


# ------------------------------------------------------------- llm errors


def test_generate_rejects_invalid_llm_payload(client, faculty_token):
    stub = StubDraftLLMClient(result=make_draft_with_unknown_mapping_course())
    override_llm(client, stub)
    try:
        response = generate(client, faculty_token, [("syllabus.txt", b"content")])
    finally:
        release_llm(client)

    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "invalid_draft"
    assert "invalid" in body["error"]["message"].lower()


def test_generate_llm_failure_returns_service_unavailable(client, faculty_token):
    stub = StubDraftLLMClient(error=LLMResponseError("bad answer"))
    override_llm(client, stub)
    try:
        response = generate(client, faculty_token, [("syllabus.txt", b"content")])
    finally:
        release_llm(client)

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "llm_draft_failed"


def test_generate_without_llm_configuration_returns_service_unavailable(
    client, faculty_token
):
    stub = StubDraftLLMClient(error=LLMNotConfiguredError())
    override_llm(client, stub)
    try:
        response = generate(client, faculty_token, [("syllabus.txt", b"content")])
    finally:
        release_llm(client)

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "llm_not_configured"
