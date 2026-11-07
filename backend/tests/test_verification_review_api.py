import uuid

from sqlalchemy import select

from app.db.models.audit import AuditLog
from app.db.models.verification import VerificationFinding
from app.db.session import SessionLocal
from tests.conftest import bearer
from tests.test_curriculum_api import curriculum_payload


def _create_finding(client, admin_token, program):
    curriculum_response = client.post(
        "/api/v1/curricula",
        json=curriculum_payload(program["id"]),
        headers=bearer(admin_token),
    )
    assert curriculum_response.status_code == 201
    version_id = curriculum_response.json()["versions"][0]["id"]
    curriculum_id = curriculum_response.json()["id"]
    run_response = client.post(
        f"/api/v1/curricula/{curriculum_id}/versions/{version_id}/verification-runs",
        headers=bearer(admin_token),
    )
    assert run_response.status_code == 201

    finding_id = uuid.uuid4()
    with SessionLocal() as session:
        session.add(
            VerificationFinding(
                id=finding_id,
                verification_run_id=uuid.UUID(run_response.json()["id"]),
                category="DEPENDENCY",
                severity="LOW",
                title="Review test finding",
                requires_human_review=True,
            )
        )
        session.commit()
    return str(finding_id)


def test_reviewer_can_record_finding_decision_and_audit(
    client, admin_token, reviewer_token, program
):
    finding_id = _create_finding(client, admin_token, program)

    response = client.patch(
        f"/api/v1/verification-findings/{finding_id}/review",
        json={"review_status": "ACCEPTED", "review_comments": "Confirmed by committee."},
        headers=bearer(reviewer_token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["review_status"] == "ACCEPTED"
    assert body["review_comments"] == "Confirmed by committee."
    assert body["reviewed_by"]
    assert body["reviewed_at"]

    fetched = client.get(
        f"/api/v1/verification-findings/{finding_id}", headers=bearer(reviewer_token)
    )
    assert fetched.status_code == 200
    assert fetched.json()["review_status"] == "ACCEPTED"
    with SessionLocal() as session:
        audit = session.scalar(
            select(AuditLog).where(
                AuditLog.entity_type == "verification_finding",
                AuditLog.entity_id == uuid.UUID(finding_id),
                AuditLog.action == "REVIEW",
            )
        )
        assert audit is not None
        assert audit.new_values["review_status"] == "ACCEPTED"


def test_faculty_cannot_review_findings(
    client, admin_token, faculty_token, program
):
    finding_id = _create_finding(client, admin_token, program)

    response = client.patch(
        f"/api/v1/verification-findings/{finding_id}/review",
        json={"review_status": "REJECTED"},
        headers=bearer(faculty_token),
    )

    assert response.status_code == 403


def test_finding_review_rejects_pending_decision(client, reviewer_token):
    response = client.patch(
        f"/api/v1/verification-findings/{uuid.uuid4()}/review",
        json={"review_status": "PENDING"},
        headers=bearer(reviewer_token),
    )

    assert response.status_code == 422


def test_finding_review_requires_authentication(client):
    response = client.patch(
        f"/api/v1/verification-findings/{uuid.uuid4()}/review",
        json={"review_status": "MODIFIED"},
    )

    assert response.status_code == 401
