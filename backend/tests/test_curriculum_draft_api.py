import io
from typing import Any

from app.api.deps import get_llm_client
from app.db.models.mappings import MappingLevel
from app.db.session import SessionLocal
from app.services.llm import LLMNotConfiguredError, LLMResponseError
from tests.conftest import bearer


class StubDraftLLMClient:
    model = "stub-model"

    def __init__(
        self,
        result: dict | None = None,
        error: Exception | None = None,
        repair_result: dict | None = None,
    ):
        self.result = result or make_draft_payload()
        self.error = error
        self.repair_result = repair_result
        self.calls: list[str] = []
        self.repair_calls: list[tuple[str, dict[str, Any], str]] = []
        self.topic_calls: list[str] = []
        self.topic_repair_calls: list[tuple[str, dict[str, Any], str]] = []

    def draft_curriculum(self, document_text: str) -> dict[str, Any]:
        self.calls.append(document_text)
        if self.error is not None:
            raise self.error
        return self.result

    def draft_curriculum_from_topic(self, topic: str) -> dict[str, Any]:
        self.topic_calls.append(topic)
        if self.error is not None:
            raise self.error
        return self.result

    def repair_curriculum_draft(
        self,
        document_text: str,
        previous_payload: dict[str, Any],
        validation_feedback: str,
    ) -> dict[str, Any]:
        self.repair_calls.append((document_text, previous_payload, validation_feedback))
        if self.error is not None:
            raise self.error
        return self.repair_result or self.result

    def repair_curriculum_draft_from_topic(
        self,
        topic: str,
        previous_payload: dict[str, Any],
        validation_feedback: str,
    ) -> dict[str, Any]:
        self.topic_repair_calls.append((topic, previous_payload, validation_feedback))
        if self.error is not None:
            raise self.error
        return self.repair_result or self.result


def override_llm(client, stub):
    client.app.dependency_overrides[get_llm_client] = lambda: stub


def release_llm(client):
    client.app.dependency_overrides.pop(get_llm_client, None)


def generate(client, token, entries: list[tuple[str, bytes]]) -> Any:
    return client.post(
        "/api/v1/curriculum-drafts",
        files=[("files", (name, content, "text/plain")) for name, content in entries],
        headers=bearer(token) if token else None,
    )


def generate_topic(client, token, topic: str) -> Any:
    return client.post(
        "/api/v1/curriculum-drafts",
        data={"topic": topic},
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
                "course_code": "CS201",
                "course_outcome_code": "CO2",
                "program_outcome_code": "PO2",
                "level": 2,
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


def make_draft_with_unmapped_outcome() -> dict[str, Any]:
    payload = make_draft_payload()
    payload["semesters"][0]["courses"][1]["outcomes"].append(
        {"code": "CO2", "statement": "Apply integral calculus."}
    )
    return payload


def make_repaired_draft() -> dict[str, Any]:
    payload = make_draft_with_unmapped_outcome()
    payload["mappings"].append(
        {
            "course_code": "MA101",
            "course_outcome_code": "CO2",
            "program_outcome_code": "PO2",
            "level": 2,
        }
    )
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
        b"4 0 obj\n<< /Length "
        + str(len(content)).encode()
        + b" >>\nstream\n"
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
    response = generate(client, reviewer_token, [("syllabus.txt", b"CS101 syllabus")])
    assert response.status_code == 403


def test_reviewer_cannot_generate_draft_from_topic(client, reviewer_token):
    response = generate_topic(client, reviewer_token, "B.Tech in Artificial Intelligence")
    assert response.status_code == 403


def test_committee_member_and_admin_can_generate(client, committee_token, admin_token):
    for token in (committee_token, admin_token):
        stub = StubDraftLLMClient()
        override_llm(client, stub)
        try:
            response = generate(client, token, [("syllabus.txt", b"CS101 syllabus")])
        finally:
            release_llm(client)
        assert response.status_code == 200


# ------------------------------------------------------------ file guards


def test_generate_rejects_no_topic_or_files(client, faculty_token):
    response = client.post("/api/v1/curriculum-drafts", headers=bearer(faculty_token))
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "missing_draft_source"


def test_generate_rejects_blank_topic_without_files(client, faculty_token):
    response = generate_topic(client, faculty_token, "   ")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "missing_draft_source"


def test_generate_rejects_invalid_topic_length(client, faculty_token):
    short = generate_topic(client, faculty_token, "AI")
    assert short.status_code == 400
    assert short.json()["error"]["code"] == "invalid_topic"
    too_long = generate_topic(client, faculty_token, "x" * 501)
    assert too_long.status_code == 400
    assert too_long.json()["error"]["code"] == "invalid_topic"


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
    response = generate(client, faculty_token, [("big.txt", b"x" * (1024 * 1024 + 1))])
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
                    b"B.Tech CSE regulation 2026. Semester 1: CS101 Programming Fundamentals.",
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
    assert len(body["mappings"]) == 6
    assert all(mapping["level"] in (1, 2, 3) for mapping in body["mappings"])
    assert any(
        mapping["course_code"] == "CS101" and mapping["program_outcome_code"] == "PO1"
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


def test_generate_returns_draft_from_topic_brief(client, faculty_token):
    stub = StubDraftLLMClient()
    override_llm(client, stub)
    try:
        response = generate_topic(
            client,
            faculty_token,
            "  B.Tech in Artificial Intelligence, 4 years, applied project focus  ",
        )
    finally:
        release_llm(client)

    assert response.status_code == 200, response.text
    assert response.json()["program"]["name"] == "B.Tech Computer Science and Engineering"
    assert stub.topic_calls == [
        "B.Tech in Artificial Intelligence, 4 years, applied project focus"
    ]
    assert stub.calls == []


def test_generate_uses_topic_as_brief_with_documents(client, faculty_token):
    stub = StubDraftLLMClient()
    override_llm(client, stub)
    try:
        response = client.post(
            "/api/v1/curriculum-drafts",
            data={"topic": "Data science with an applied capstone"},
            files=[("files", ("syllabus.txt", b"CS101 syllabus", "text/plain"))],
            headers=bearer(faculty_token),
        )
    finally:
        release_llm(client)

    assert response.status_code == 200, response.text
    assert stub.calls == [
        "= Curriculum brief =\nData science with an applied capstone\n\n"
        "= File: syllabus.txt =\nCS101 syllabus"
    ]
    assert stub.topic_calls == []


def test_generate_repairs_topic_draft_with_missing_outcome_mapping(client, faculty_token):
    invalid_payload = make_draft_with_unmapped_outcome()
    stub = StubDraftLLMClient(result=invalid_payload, repair_result=make_repaired_draft())
    override_llm(client, stub)
    try:
        response = generate_topic(
            client, faculty_token, "B.Sc in Data Science, 3 years"
        )
    finally:
        release_llm(client)

    assert response.status_code == 200, response.text
    assert len(response.json()["mappings"]) == 7
    assert len(stub.topic_calls) == 1
    assert len(stub.topic_repair_calls) == 1
    topic, previous_payload, feedback = stub.topic_repair_calls[0]
    assert topic == "B.Sc in Data Science, 3 years"
    assert previous_payload == invalid_payload
    assert "MA101" in feedback
    assert "has no program outcome mapping" in feedback
    assert stub.calls == []
    assert stub.repair_calls == []


def test_save_reviewed_draft_persists_normalized_curriculum(client, faculty_token, program):
    with SessionLocal() as session:
        for number in (1, 2, 3):
            session.add(
                MappingLevel(
                    code=f"LEVEL_{number}",
                    name=f"Level {number}",
                    numeric_value=number,
                    is_active=True,
                )
            )
        session.commit()

    response = client.post(
        "/api/v1/curriculum-drafts/save",
        headers=bearer(faculty_token),
        json={
            "program_id": program["id"],
            "academic_year": "2026-27",
            "regulation": "AI-2026",
            "title": "AI-reviewed CSE curriculum",
            "course_type_codes": {
                "foundation": "CORE",
                "core": "CORE",
                "lab": "LAB",
            },
            "credits_by_course_code": {},
            "draft": make_draft_payload(),
        },
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["description"] == make_draft_payload()["program"]["summary"]
    version = body["versions"][0]
    assert version["status"] == "APPROVED"
    assert len(version["semesters"]) == 2
    assert version["semesters"][0]["focus"] == "Foundations"
    assert len(version["courses"]) == 4

    course = version["courses"][0]
    outcomes = client.get(
        f"/api/v1/curricula/{body['id']}/versions/{version['id']}/courses/{course['id']}/outcomes",
        headers=bearer(faculty_token),
    )
    mappings = client.get(
        f"/api/v1/curricula/{body['id']}/versions/{version['id']}/mappings",
        headers=bearer(faculty_token),
    )
    assert outcomes.status_code == 200
    assert len(outcomes.json()) >= 1
    assert mappings.status_code == 200
    assert len(mappings.json()) == 6
    assert all(row["current_version"]["status"] == "APPROVED" for row in mappings.json())

    pos = client.get(
        f"/api/v1/programs/{program['id']}/program-outcomes", headers=bearer(faculty_token)
    )
    peos = client.get(f"/api/v1/programs/{program['id']}/peos", headers=bearer(faculty_token))
    assert len(pos.json()) == 5
    assert len(peos.json()) == 3
    assert all(row["current_version"]["status"] == "APPROVED" for row in pos.json())
    assert all(row["current_version"]["status"] == "APPROVED" for row in peos.json())

    listing = client.get("/api/v1/curricula", headers=bearer(faculty_token))
    assert listing.status_code == 200
    listed = next(row for row in listing.json() if row["id"] == body["id"])
    assert listed["academic_year"] == "2026-27"
    assert listed["regulation"] == "AI-2026"
    assert listed["latest_version"]["status"] == "APPROVED"
    assert listed["latest_version"]["version_label"] == "1.0"


def test_document_to_saved_curriculum_verification_report(
    client, faculty_token, reviewer_token, program
):
    with SessionLocal() as session:
        for number in (1, 2, 3):
            session.add(
                MappingLevel(
                    code=f"LEVEL_{number}",
                    name=f"Level {number}",
                    numeric_value=number,
                    is_active=True,
                )
            )
        session.commit()

    stub = StubDraftLLMClient()
    override_llm(client, stub)
    try:
        generated = generate(
            client,
            faculty_token,
            [
                (
                    "curriculum.txt",
                    b"B.Tech CSE curriculum with semesters, courses, and CO-PO mappings.",
                )
            ],
        )
    finally:
        release_llm(client)
    assert generated.status_code == 200, generated.text
    draft = generated.json()

    saved = client.post(
        "/api/v1/curriculum-drafts/save",
        headers=bearer(faculty_token),
        json={
            "program_id": program["id"],
            "academic_year": "2026-27",
            "regulation": "E2E-2026",
            "course_type_codes": {
                "foundation": "CORE",
                "core": "CORE",
                "lab": "LAB",
            },
            "credits_by_course_code": {},
            "draft": draft,
        },
    )
    assert saved.status_code == 201, saved.text
    curriculum = saved.json()
    version = curriculum["versions"][0]

    run_response = client.post(
        f"/api/v1/curricula/{curriculum['id']}/versions/"
        f"{version['id']}/verification-runs",
        headers=bearer(reviewer_token),
    )
    assert run_response.status_code == 201, run_response.text
    run = run_response.json()
    assert run["status"] == "COMPLETED"

    findings_response = client.get(
        f"/api/v1/verification-runs/{run['id']}/findings",
        headers=bearer(reviewer_token),
    )
    assert findings_response.status_code == 200
    findings = findings_response.json()
    assert findings

    report_response = client.get(
        f"/api/v1/verification-runs/{run['id']}/report?group_by=category",
        headers=bearer(reviewer_token),
    )
    assert report_response.status_code == 200
    report = report_response.json()
    assert report["total_findings"] == len(findings)
    assert sum(report["counts_by_category"].values()) == report["total_findings"]
    assert sum(report["counts_by_severity"].values()) == report["total_findings"]
    assert sum(report["counts_by_review_status"].values()) == report["total_findings"]
    assert {group["key"] for group in report["groups"]} == set(
        report["counts_by_category"]
    )
    assert all(group["findings"] for group in report["groups"])


def test_save_draft_requires_type_for_each_category(client, faculty_token, program):
    response = client.post(
        "/api/v1/curriculum-drafts/save",
        headers=bearer(faculty_token),
        json={
            "program_id": program["id"],
            "academic_year": "2026-27",
            "regulation": "AI-2026",
            "course_type_codes": {"foundation": "CORE"},
            "draft": make_draft_payload(),
        },
    )
    assert response.status_code == 422


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
    assert stub.calls == [("= File: regulation.pdf =\nCS101 Programming Fundamentals syllabus")]


# ------------------------------------------------------------- llm errors


def test_generate_repairs_draft_with_missing_outcome_mapping(client, faculty_token):
    invalid_payload = make_draft_with_unmapped_outcome()
    stub = StubDraftLLMClient(result=invalid_payload, repair_result=make_repaired_draft())
    override_llm(client, stub)
    try:
        response = generate(client, faculty_token, [("syllabus.txt", b"content")])
    finally:
        release_llm(client)

    assert response.status_code == 200, response.text
    assert len(response.json()["mappings"]) == 7
    assert len(stub.calls) == 1
    assert len(stub.repair_calls) == 1
    document_text, previous_payload, feedback = stub.repair_calls[0]
    assert document_text == "= File: syllabus.txt =\ncontent"
    assert previous_payload == invalid_payload
    assert "MA101" in feedback
    assert "CO2" in feedback
    assert "has no program outcome mapping" in feedback


def test_generate_rejects_invalid_llm_payload_after_repair(client, faculty_token):
    stub = StubDraftLLMClient(result=make_draft_with_unknown_mapping_course())
    override_llm(client, stub)
    try:
        response = generate(client, faculty_token, [("syllabus.txt", b"content")])
    finally:
        release_llm(client)

    assert response.status_code == 503
    body = response.json()
    assert body["error"]["code"] == "llm_draft_failed"
    assert "invalid" in body["error"]["message"].lower()
    assert "repair" in body["error"]["message"].lower()
    assert "(at 'payload')" in body["error"]["message"]
    assert len(stub.calls) == 1
    assert len(stub.repair_calls) == 1


def test_generate_rejects_draft_without_program_outcomes_or_mappings(client, faculty_token):
    payload = make_draft_payload()
    payload["pos"] = []
    payload["mappings"] = []
    stub = StubDraftLLMClient(result=payload)
    override_llm(client, stub)
    try:
        response = generate(client, faculty_token, [("syllabus.txt", b"content")])
    finally:
        release_llm(client)

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "llm_draft_failed"
    assert len(stub.repair_calls) == 1


def test_generate_llm_failure_returns_service_unavailable(client, faculty_token):
    stub = StubDraftLLMClient(error=LLMResponseError("bad answer"))
    override_llm(client, stub)
    try:
        response = generate(client, faculty_token, [("syllabus.txt", b"content")])
    finally:
        release_llm(client)

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "llm_draft_failed"
    assert stub.repair_calls == []


def test_generate_without_llm_configuration_returns_service_unavailable(client, faculty_token):
    stub = StubDraftLLMClient(error=LLMNotConfiguredError())
    override_llm(client, stub)
    try:
        response = generate(client, faculty_token, [("syllabus.txt", b"content")])
    finally:
        release_llm(client)

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "llm_not_configured"
    assert stub.repair_calls == []
