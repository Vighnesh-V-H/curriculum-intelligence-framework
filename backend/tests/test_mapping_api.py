import uuid

from app.db.models import MappingLevel
from app.db.session import SessionLocal
from tests.conftest import bearer


def seed_mapping_levels() -> None:
    with SessionLocal() as session:
        for sort_order, code, name in (
            (1, "LOW", "Low"),
            (2, "MEDIUM", "Medium"),
            (3, "HIGH", "High"),
        ):
            session.add(
                MappingLevel(
                    id=uuid.uuid4(),
                    code=code,
                    name=name,
                    numeric_value=sort_order,
                    is_active=True,
                    sort_order=sort_order,
                )
            )
        session.commit()


def make_mapping(client, admin_token, program):
    curriculum_response = client.post(
        "/api/v1/curricula",
        json={
            "program_id": program["id"],
            "academic_year": "2026-27",
            "regulation": "2026",
            "duration_years": 4,
            "semesters": [{"semester_number": 1, "name": "Semester 1"}],
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
        headers=bearer(admin_token),
    )
    assert curriculum_response.status_code == 201
    curriculum = curriculum_response.json()
    version = curriculum["versions"][0]
    course = version["courses"][0]

    co_response = client.post(
        f"/api/v1/curricula/{curriculum['id']}/versions/{version['id']}"
        f"/courses/{course['id']}/outcomes",
        json={"co_code": "CO1", "description": "Apply programming concepts"},
        headers=bearer(admin_token),
    )
    assert co_response.status_code == 201
    co = co_response.json()

    po_response = client.post(
        f"/api/v1/programs/{program['id']}/program-outcomes",
        json={"po_code": "PO1", "description": "Solve engineering problems"},
        headers=bearer(admin_token),
    )
    assert po_response.status_code == 201
    po = po_response.json()
    for status in ("PROPOSED", "APPROVED"):
        status_response = client.patch(
            f"/api/v1/program-outcomes/{po['id']}/versions/"
            f"{po['current_version']['id']}/status",
            json={"status": status},
            headers=bearer(admin_token),
        )
        assert status_response.status_code == 200

    mapping_response = client.post(
        f"/api/v1/curricula/{curriculum['id']}/versions/{version['id']}/mappings",
        json={
            "course_outcome_id": co["id"],
            "program_outcome_id": po["id"],
            "mapping_level_code": "MEDIUM",
        },
        headers=bearer(admin_token),
    )
    assert mapping_response.status_code == 201, mapping_response.json()
    return curriculum, version, mapping_response.json()


def change_mapping_status(client, admin_token, mapping, status):
    response = client.patch(
        f"/api/v1/mappings/{mapping['id']}/versions/"
        f"{mapping['current_version']['id']}/status",
        json={"status": status},
        headers=bearer(admin_token),
    )
    assert response.status_code == 200, response.json()
    return response.json()


def test_mapping_level_update_applies_to_draft_version(
    client, admin_token, program
):
    seed_mapping_levels()
    _, _, mapping = make_mapping(client, admin_token, program)

    response = client.patch(
        f"/api/v1/mappings/{mapping['id']}",
        json={"mapping_level_code": "high"},
        headers=bearer(admin_token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["current_version"]["mapping_level_code"] == "HIGH"
    assert body["current_version"]["status"] == "DRAFT"
    assert len(body["versions"]) == 1


def test_mapping_level_update_after_approval_creates_draft_version(
    client, admin_token, program
):
    seed_mapping_levels()
    _, _, mapping = make_mapping(client, admin_token, program)
    change_mapping_status(client, admin_token, mapping, "PROPOSED")
    approved = change_mapping_status(client, admin_token, mapping, "APPROVED")
    assert approved["status"] == "APPROVED"

    response = client.patch(
        f"/api/v1/mappings/{mapping['id']}",
        json={"mapping_level_code": "HIGH"},
        headers=bearer(admin_token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["current_version"]["mapping_level_code"] == "MEDIUM"
    assert body["current_version"]["status"] == "APPROVED"
    assert len(body["versions"]) == 2
    newest = body["versions"][-1]
    assert newest["version_number"] == 2
    assert newest["mapping_level_code"] == "HIGH"
    assert newest["status"] == "DRAFT"


def test_mapping_under_review_cannot_be_edited(client, admin_token, program):
    seed_mapping_levels()
    _, _, mapping = make_mapping(client, admin_token, program)
    change_mapping_status(client, admin_token, mapping, "PROPOSED")

    response = client.patch(
        f"/api/v1/mappings/{mapping['id']}",
        json={"mapping_level_code": "HIGH"},
        headers=bearer(admin_token),
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "mapping_version_under_review"


def test_mapping_removal_deactivates_mapping(client, admin_token, program):
    seed_mapping_levels()
    curriculum, version, mapping = make_mapping(client, admin_token, program)

    response = client.delete(
        f"/api/v1/mappings/{mapping['id']}", headers=bearer(admin_token)
    )
    assert response.status_code == 204

    removed = client.get(
        f"/api/v1/mappings/{mapping['id']}", headers=bearer(admin_token)
    )
    assert removed.status_code == 200
    assert removed.json()["status"] == "INACTIVE"

    listed = client.get(
        f"/api/v1/curricula/{curriculum['id']}/versions/{version['id']}/mappings",
        headers=bearer(admin_token),
    )
    assert listed.status_code == 200
    assert listed.json() == []

    repeated = client.delete(
        f"/api/v1/mappings/{mapping['id']}", headers=bearer(admin_token)
    )
    assert repeated.status_code == 409
    assert repeated.json()["error"]["code"] == "mapping_inactive"


def test_reviewer_cannot_update_or_remove_mapping(
    client, admin_token, reviewer_token, program
):
    seed_mapping_levels()
    _, _, mapping = make_mapping(client, admin_token, program)

    update = client.patch(
        f"/api/v1/mappings/{mapping['id']}",
        json={"mapping_level_code": "HIGH"},
        headers=bearer(reviewer_token),
    )
    removal = client.delete(
        f"/api/v1/mappings/{mapping['id']}", headers=bearer(reviewer_token)
    )

    assert update.status_code == 403
    assert removal.status_code == 403
