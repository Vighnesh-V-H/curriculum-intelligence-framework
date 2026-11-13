from __future__ import annotations

from tests.conftest import bearer


def make_curriculum(
    client,
    token,
    program,
    *,
    semesters: list[int],
    courses: list[dict],
    regulation: str = "2026",
    duration_years: float | None = None,
):
    response = client.post(
        "/api/v1/curricula",
        json={
            "program_id": program["id"],
            "academic_year": "2026-27",
            "regulation": regulation,
            "title": "Verification fixture curriculum",
            "duration_years": duration_years or max(semesters) / 2,
            "semesters": [
                {"semester_number": number, "name": f"Semester {number}"}
                for number in semesters
            ],
            "courses": courses,
        },
        headers=bearer(token),
    )
    assert response.status_code == 201, response.json()
    body = response.json()
    return body, body["versions"][0]


def course(
    code: str,
    name: str,
    *,
    semester: int,
    credits: float = 4,
    course_type: str = "CORE",
    description: str | None = None,
    syllabus: str | None = None,
) -> dict:
    return {
        "course_code": code,
        "course_name": name,
        "course_type_code": course_type,
        "credits": credits,
        "semester_number": semester,
        "description": description,
        "syllabus": syllabus,
    }


def prerequisite_url(curriculum, version) -> str:
    return (
        f"/api/v1/curricula/{curriculum['id']}/versions/{version['id']}"
        "/prerequisites"
    )


def create_and_approve_prerequisite(
    client,
    faculty_token,
    admin_token,
    curriculum,
    version,
    prerequisite_course_id: str,
    target_course_id: str,
) -> dict:
    response = client.post(
        prerequisite_url(curriculum, version),
        json={
            "prerequisite_course_id": prerequisite_course_id,
            "target_course_id": target_course_id,
        },
        headers=bearer(faculty_token),
    )
    assert response.status_code == 201, response.json()
    created = response.json()
    assert created["status"] == "APPROVED"
    return created


def run_verification(client, token, curriculum, version) -> dict:
    response = client.post(
        f"/api/v1/curricula/{curriculum['id']}/versions/{version['id']}"
        "/verification-runs",
        headers=bearer(token),
    )
    assert response.status_code == 201, response.json()
    return response.json()


def list_findings(client, token, run: dict) -> list[dict]:
    response = client.get(
        f"/api/v1/verification-runs/{run['id']}/findings",
        headers=bearer(token),
    )
    assert response.status_code == 200, response.json()
    return response.json()


def evidence_codes(findings: list[dict]) -> set[str]:
    return {
        finding["evidence"].split(":", 1)[0]
        for finding in findings
        if finding["evidence"]
    }


def test_prerequisite_chain_and_transitive_edge(
    client, admin_token, faculty_token, reviewer_token, program
):
    curriculum, version = make_curriculum(
        client,
        admin_token,
        program,
        semesters=[1, 2, 3, 4, 5],
        courses=[
            course("CS101", "Programming Fundamentals", semester=1),
            course("CS201", "Data Structures", semester=3),
            course("CS301", "Advanced Algorithms", semester=5),
        ],
    )
    courses = {item["course_code"]: item for item in version["courses"]}
    create_and_approve_prerequisite(
        client,
        faculty_token,
        admin_token,
        curriculum,
        version,
        courses["CS101"]["id"],
        courses["CS201"]["id"],
    )
    create_and_approve_prerequisite(
        client,
        faculty_token,
        admin_token,
        curriculum,
        version,
        courses["CS201"]["id"],
        courses["CS301"]["id"],
    )
    direct = create_and_approve_prerequisite(
        client,
        faculty_token,
        admin_token,
        curriculum,
        version,
        courses["CS101"]["id"],
        courses["CS301"]["id"],
    )

    run = run_verification(client, reviewer_token, curriculum, version)
    summary = run["summary"]
    graph = summary["prerequisite_graph"]
    assert graph["longest_chain"] == ["CS101", "CS201", "CS301"]
    assert graph["longest_chain_length"] == 3
    assert graph["transitive_redundant_edges"] == 1

    findings = list_findings(client, reviewer_token, run)
    transitive = [
        finding
        for finding in findings
        if (finding["evidence"] or "").startswith("TRANSITIVE_PREREQUISITE:")
    ]
    assert len(transitive) == 1
    assert "CS101 -> CS201 -> CS301" in transitive[0]["evidence"]
    reference_types = {item["entity_type"] for item in transitive[0]["references"]}
    assert {"COURSE", "PREREQUISITE"} <= reference_types
    referenced_ids = {
        item["entity_id"]
        for item in transitive[0]["references"]
        if item["entity_type"] == "PREREQUISITE"
    }
    assert direct["id"] in referenced_ids


def test_topic_redundancy_progression_and_legitimate_sequence(
    client, admin_token, faculty_token, reviewer_token, program
):
    description = (
        "Relational database schema normalization transaction concurrency "
        "indexing query optimization replication sharding."
    )
    curriculum, version = make_curriculum(
        client,
        admin_token,
        program,
        semesters=[1, 2, 3, 4],
        courses=[
            course("DB101", "Database Systems", semester=1, description=description),
            course("DB102", "Database Design", semester=1, description=description),
            course("DB201", "Advanced Database Systems", semester=3, description=description),
            course("DB301", "Database Capstone", semester=4, description=description),
        ],
    )
    courses = {item["course_code"]: item for item in version["courses"]}
    create_and_approve_prerequisite(
        client,
        faculty_token,
        admin_token,
        curriculum,
        version,
        courses["DB201"]["id"],
        courses["DB301"]["id"],
    )

    run = run_verification(client, reviewer_token, curriculum, version)
    topic = run["summary"]["topic_overlap"]
    assert topic["redundancy_candidates"] >= 1
    assert topic["unverified_progression_candidates"] >= 1
    assert topic["progression_candidates"] >= 1
    classifications = {
        (item["course_a"], item["course_b"]): item["classification"]
        for item in topic["top_overlaps"]
    }
    assert classifications[("DB101", "DB102")] == "REDUNDANCY"
    assert classifications[("DB101", "DB201")] == "PROGRESSION_UNVERIFIED"
    assert classifications[("DB201", "DB301")] == "PROGRESSION"

    findings = list_findings(client, reviewer_token, run)
    codes = evidence_codes(findings)
    assert "TOPIC_REDUNDANCY" in codes
    assert "TOPIC_PROGRESSION" in codes
    progression = [
        finding
        for finding in findings
        if (finding["evidence"] or "").startswith("TOPIC_PROGRESSION:")
    ]
    assert progression
    assert all(
        {item["entity_type"] for item in finding["references"]} >= {"COURSE"}
        for finding in progression
    )


def test_structure_and_credit_distribution_summary(
    client, admin_token, reviewer_token, program
):
    curriculum, version = make_curriculum(
        client,
        admin_token,
        program,
        semesters=[1, 3],
        duration_years=2,
        courses=[
            course("CS101", "Programming Fundamentals", semester=1, credits=4),
            course("LAB101", "Programming Lab", semester=1, credits=2, course_type="LAB"),
        ],
    )

    run = run_verification(client, reviewer_token, curriculum, version)
    structure = run["summary"]["structure"]
    assert structure["active_course_count"] == 2
    assert structure["semester_count"] == 2
    assert structure["expected_semester_count"] == 4
    assert structure["total_credits"] == 6.0
    assert structure["credit_totals_by_semester"] == {"1": 6.0, "3": 0.0}
    assert structure["credits_by_course_type"] == {"CORE": 4.0, "LAB": 2.0}
    assert structure["course_counts_by_course_type"] == {"CORE": 1, "LAB": 1}
    assert structure["semester_credit_range"] == {"min": 0.0, "max": 6.0}
    assert run["summary"]["credit_totals_by_semester"] == {"1": 6.0, "3": 0.0}

    findings = list_findings(client, reviewer_token, run)
    codes = evidence_codes(findings)
    assert "SEMESTER_SEQUENCE_GAP" in codes
    assert "EMPTY_SEMESTER" in codes


def test_configured_references_produce_evidence_findings(
    client, admin_token, reviewer_token, program
):
    curriculum, version = make_curriculum(
        client,
        admin_token,
        program,
        semesters=[1, 2],
        courses=[
            course(
                "CS101",
                "Programming Fundamentals",
                semester=1,
                description="Programming language syntax control flow functions testing.",
            )
        ],
    )

    references = [
        {
            "reference_type": "INSTITUTIONAL",
            "code": "INST-2026",
            "title": "Institutional credit rules",
            "source": "Institutional curriculum policy",
            "severity": "HIGH",
            "rules": {
                "total_credits": {"min": 40},
                "semester_credits": {"max": 3},
                "course_type_credits": {"LAB": {"min": 2}},
            },
        },
        {
            "reference_type": "OBE",
            "code": "OBE-2026",
            "title": "OBE coverage targets",
            "source": "Program self-study",
            "rules": {
                "required_po_codes": ["PO1"],
                "required_peo_codes": ["PEO1"],
                "min_po_coverage_ratio": 0.8,
                "min_approved_mapping_ratio": 0.8,
            },
        },
        {
            "reference_type": "ACCREDITATION",
            "code": "ACCRED-2026",
            "title": "Accreditation criteria",
            "source": "Accreditation manual",
            "rules": {
                "criterion": "Criterion 4: continuous improvement",
                "required_po_codes": ["PO2"],
                "required_course_types": ["LAB"],
                "min_po_coverage_ratio": 0.5,
                "min_approved_mapping_ratio": 0.5,
            },
        },
        {
            "reference_type": "INDUSTRY",
            "code": "IND-2026",
            "title": "Industry competency expectations",
            "source": "Industry advisory board",
            "rules": {
                "skills": [
                    {
                        "code": "CLOUD",
                        "label": "Cloud engineering",
                        "keywords": ["kubernetes", "cloud"],
                        "required": True,
                        "min_courses": 1,
                    }
                ],
                "min_required_skill_coverage_ratio": 0.9,
            },
        },
    ]
    created = []
    for payload in references:
        response = client.post(
            "/api/v1/verification-references",
            json=payload,
            headers=bearer(admin_token),
        )
        assert response.status_code == 201, response.json()
        created.append(response.json())

    run = run_verification(client, reviewer_token, curriculum, version)
    comparison = run["summary"]["reference_comparison"]
    assert comparison["status"] == "EVALUATED"
    assert comparison["count"] == 4
    assert comparison["invalid_references"] == []
    assert set(comparison["findings_by_reference"]) == {
        reference["id"] for reference in created
    }
    assert all(
        count >= 1 for count in comparison["findings_by_reference"].values()
    )

    findings = list_findings(client, reviewer_token, run)
    codes = evidence_codes(findings)
    assert {
        "INSTITUTIONAL_TOTAL_CREDITS",
        "OBE_PO_REQUIRED",
        "OBE_PEO_REQUIRED",
        "ACCREDITATION_PO_REQUIRED",
        "ACCREDITATION_COURSE_TYPE_REQUIRED",
        "INDUSTRY_SKILL_COVERAGE",
    } <= codes

    reference_ids = {reference["id"] for reference in created}
    referenced = {
        item["entity_id"]
        for finding in findings
        for item in finding["references"]
        if item["entity_type"] == "VERIFICATION_REFERENCE"
    }
    assert reference_ids <= referenced


def test_program_specific_reference_overrides_global_reference(
    client, admin_token, reviewer_token, program
):
    curriculum, version = make_curriculum(
        client,
        admin_token,
        program,
        semesters=[1, 2],
        courses=[course("CS101", "Programming Fundamentals", semester=1)],
        regulation="2026-override",
    )

    global_reference = client.post(
        "/api/v1/verification-references",
        json={
            "reference_type": "INSTITUTIONAL",
            "code": "INST-OVERRIDE",
            "title": "Global credit target",
            "source": "Institution policy",
            "version_label": "1.0",
            "severity": "HIGH",
            "rules": {"total_credits": {"min": 1000}},
        },
        headers=bearer(admin_token),
    )
    assert global_reference.status_code == 201, global_reference.json()
    program_reference = client.post(
        "/api/v1/verification-references",
        json={
            "program_id": program["id"],
            "reference_type": "INSTITUTIONAL",
            "code": "INST-OVERRIDE",
            "title": "Program credit target",
            "source": "Program policy",
            "version_label": "2.0",
            "severity": "LOW",
            "rules": {"total_credits": {"min": 1}},
        },
        headers=bearer(admin_token),
    )
    assert program_reference.status_code == 201, program_reference.json()

    run = run_verification(client, reviewer_token, curriculum, version)
    comparison = run["summary"]["reference_comparison"]
    assert comparison["count"] == 1
    assert comparison["references"][0]["id"] == program_reference.json()["id"]
    assert comparison["references"][0]["version_label"] == "2.0"

    findings = list_findings(client, reviewer_token, run)
    assert "INSTITUTIONAL_TOTAL_CREDITS" not in evidence_codes(findings)


def test_reference_api_permissions_validation_and_duplicates(
    client, admin_token, faculty_token, program
):
    payload = {
        "reference_type": "INSTITUTIONAL",
        "code": "INST-1",
        "title": "Credit target",
        "source": "Policy manual",
        "rules": {"total_credits": {"min": 120, "max": 160}},
    }

    forbidden = client.post(
        "/api/v1/verification-references",
        json=payload,
        headers=bearer(faculty_token),
    )
    assert forbidden.status_code == 403

    invalid = client.post(
        "/api/v1/verification-references",
        json={
            **payload,
            "rules": {"total_credits": {"min": 200, "max": 100}},
        },
        headers=bearer(admin_token),
    )
    assert invalid.status_code == 400
    assert invalid.json()["error"]["code"] == "invalid_reference_rules"

    created = client.post(
        "/api/v1/verification-references",
        json=payload,
        headers=bearer(admin_token),
    )
    assert created.status_code == 201, created.json()

    duplicate = client.post(
        "/api/v1/verification-references",
        json=payload,
        headers=bearer(admin_token),
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "verification_reference_exists"

    invalid_update = client.patch(
        f"/api/v1/verification-references/{created.json()['id']}",
        json={"rules": {"total_credits": {"min": -1}}},
        headers=bearer(admin_token),
    )
    assert invalid_update.status_code == 400
    assert invalid_update.json()["error"]["code"] == "invalid_reference_rules"

    listed = client.get(
        "/api/v1/verification-references",
        params={"program_id": program["id"]},
        headers=bearer(faculty_token),
    )
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [created.json()["id"]]

    deactivated = client.patch(
        f"/api/v1/verification-references/{created.json()['id']}",
        json={"status": "INACTIVE"},
        headers=bearer(admin_token),
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["status"] == "INACTIVE"

    active_only = client.get(
        "/api/v1/verification-references",
        headers=bearer(faculty_token),
    )
    assert active_only.json() == []


def test_verification_runs_become_stale_when_curriculum_changes(
    client, admin_token, reviewer_token, program
):
    curriculum, version = make_curriculum(
        client,
        admin_token,
        program,
        semesters=[1, 2],
        courses=[course("CS101", "Programming Fundamentals", semester=1)],
    )
    course_id = version["courses"][0]["id"]
    run = run_verification(client, reviewer_token, curriculum, version)
    assert run["is_stale"] is False
    assert run["input_fingerprint"].startswith("sha256:")

    runs_url = (
        f"/api/v1/curricula/{curriculum['id']}/versions/{version['id']}"
        "/verification-runs"
    )
    fresh = client.get(runs_url, headers=bearer(reviewer_token))
    assert fresh.status_code == 200
    assert fresh.json()[0]["is_stale"] is False

    updated = client.patch(
        f"/api/v1/curricula/{curriculum['id']}/versions/{version['id']}"
        f"/courses/{course_id}",
        json={"course_name": "Programming Fundamentals with Python"},
        headers=bearer(admin_token),
    )
    assert updated.status_code == 200, updated.json()

    stale = client.get(runs_url, headers=bearer(reviewer_token))
    assert stale.status_code == 200
    assert stale.json()[0]["is_stale"] is True

    report = client.get(
        f"/api/v1/verification-runs/{run['id']}/report?group_by=category",
        headers=bearer(reviewer_token),
    )
    assert report.status_code == 200
    assert report.json()["run"]["is_stale"] is True

    rerun = run_verification(client, reviewer_token, curriculum, version)
    assert rerun["is_stale"] is False
    assert rerun["input_fingerprint"] != run["input_fingerprint"]
