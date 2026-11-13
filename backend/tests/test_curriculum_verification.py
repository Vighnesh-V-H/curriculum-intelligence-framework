import uuid

from app.db.models import MappingLevel
from app.db.session import SessionLocal
from tests.conftest import bearer


def make_curriculum(client, token, program):
    response = client.post(
        "/api/v1/curricula",
        json={
            "program_id": program["id"],
            "academic_year": "2026-27",
            "regulation": "2026",
            "duration_years": 4,
            "semesters": [
                {"semester_number": 1, "name": "Semester 1"},
                {"semester_number": 2, "name": "Semester 2"},
            ],
            "courses": [
                {
                    "course_code": "CS101",
                    "course_name": "Programming Fundamentals",
                    "course_type_code": "CORE",
                    "credits": 4,
                    "semester_number": 1,
                }
            ],
        },
        headers=bearer(token),
    )
    assert response.status_code == 201
    body = response.json()
    return body, body["versions"][0]


def run_verification(client, token, curriculum, version):
    return client.post(
        f"/api/v1/curricula/{curriculum['id']}/versions/{version['id']}/verification-runs",
        headers=bearer(token),
    )


def test_verification_reports_structure_outcomes_and_credit_summary(
    client, faculty_token, reviewer_token, program
):
    curriculum, version = make_curriculum(client, faculty_token, program)

    run_response = run_verification(client, reviewer_token, curriculum, version)

    assert run_response.status_code == 201
    run = run_response.json()
    assert run["status"] == "COMPLETED"
    assert run["summary"]["analyzers"] == [
        "PREREQUISITE",
        "CONTENT",
        "STRUCTURE",
        "OUTCOME_COVERAGE",
        "REFERENCE_COMPARISON",
    ]
    assert run["summary"]["credit_totals_by_semester"] == {"1": 4.0, "2": 0.0}
    assert run["input_fingerprint"].startswith("sha256:")
    assert run["is_stale"] is False
    assert run["summary"]["findings_by_category"] == {"OUTCOME": 1, "STRUCTURAL": 1}

    findings_response = client.get(
        f"/api/v1/verification-runs/{run['id']}/findings",
        headers=bearer(reviewer_token),
    )
    findings = findings_response.json()
    assert findings_response.status_code == 200
    assert {finding["title"] for finding in findings} == {
        "Course has no active course outcomes",
        "Semester has no active courses",
    }
    assert all(finding["requires_human_review"] for finding in findings)
    assert all(finding["review_status"] == "PENDING" for finding in findings)
    assert all(finding["evidence"] and finding["references"] for finding in findings)

    report = client.get(
        f"/api/v1/verification-runs/{run['id']}/report?group_by=severity",
        headers=bearer(reviewer_token),
    )
    assert report.status_code == 200
    report_body = report.json()
    assert report_body["total_findings"] == 2
    assert report_body["counts_by_category"] == {"OUTCOME": 1, "STRUCTURAL": 1}
    assert report_body["counts_by_review_status"] == {"PENDING": 2}
    assert {group["key"] for group in report_body["groups"]} == {"INFO", "MEDIUM"}


def test_draft_mapping_does_not_count_as_approved_coverage(
    client, admin_token, reviewer_token, program
):
    curriculum, version = make_curriculum(client, admin_token, program)
    course = version["courses"][0]
    co_response = client.post(
        f"/api/v1/curricula/{curriculum['id']}/versions/{version['id']}"
        f"/courses/{course['id']}/outcomes",
        json={"co_code": "CO1", "description": "Apply programming concepts"},
        headers=bearer(admin_token),
    )
    po_response = client.post(
        f"/api/v1/programs/{program['id']}/program-outcomes",
        json={"po_code": "PO1", "description": "Solve engineering problems"},
        headers=bearer(admin_token),
    )
    assert co_response.status_code == 201
    assert po_response.status_code == 201
    po_id = po_response.json()["id"]
    po_version_id = po_response.json()["current_version"]["id"]
    for outcome_status in ("PROPOSED", "APPROVED"):
        status_response = client.patch(
            f"/api/v1/program-outcomes/{po_id}/versions/{po_version_id}/status",
            json={"status": outcome_status},
            headers=bearer(admin_token),
        )
        assert status_response.status_code == 200

    with SessionLocal() as session:
        session.add(
            MappingLevel(
                id=uuid.uuid4(),
                code="MEDIUM",
                name="Medium",
                numeric_value=2,
                is_active=True,
                sort_order=2,
            )
        )
        session.commit()

    mapping_response = client.post(
        f"/api/v1/curricula/{curriculum['id']}/versions/{version['id']}/mappings",
        json={
            "course_outcome_id": co_response.json()["id"],
            "program_outcome_id": po_response.json()["id"],
            "mapping_level_code": "MEDIUM",
        },
        headers=bearer(admin_token),
    )
    assert mapping_response.status_code == 201, mapping_response.json()
    mapping = mapping_response.json()
    draft_run = run_verification(client, reviewer_token, curriculum, version)
    draft_findings = client.get(
        f"/api/v1/verification-runs/{draft_run.json()['id']}/findings",
        headers=bearer(reviewer_token),
    )
    draft_titles = {finding["title"] for finding in draft_findings.json()}
    assert "Course outcome has no approved program-outcome mapping" in draft_titles
    assert "Program outcome has no approved course-outcome coverage" in draft_titles

    mapping_version_id = mapping["current_version"]["id"]
    for mapping_status in ("PROPOSED", "APPROVED"):
        status_response = client.patch(
            f"/api/v1/mappings/{mapping['id']}/versions/{mapping_version_id}/status",
            json={"status": mapping_status},
            headers=bearer(admin_token),
        )
        assert status_response.status_code == 200

    approved_run = run_verification(client, reviewer_token, curriculum, version)
    approved_findings = client.get(
        f"/api/v1/verification-runs/{approved_run.json()['id']}/findings",
        headers=bearer(reviewer_token),
    )
    approved_titles = {finding["title"] for finding in approved_findings.json()}
    assert "Course outcome has no approved program-outcome mapping" not in approved_titles
    assert "Program outcome has no approved course-outcome coverage" not in approved_titles
