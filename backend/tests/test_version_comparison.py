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


def create_curriculum(client, token, program):
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
                },
                {
                    "course_code": "CS201",
                    "course_name": "Data Structures",
                    "course_type_code": "CORE",
                    "credits": 4,
                    "semester_number": 2,
                },
            ],
        },
        headers=bearer(token),
    )
    assert response.status_code == 201, response.json()
    body = response.json()
    return body, body["versions"][0]


def set_version_status(client, token, curriculum_id, version_id, statuses):
    for status in statuses:
        response = client.patch(
            f"/api/v1/curricula/{curriculum_id}/versions/{version_id}/status",
            json={"status": status},
            headers=bearer(token),
        )
        assert response.status_code == 200, response.json()


def add_course_outcome(client, token, curriculum_id, version_id, course_id, code, description):
    response = client.post(
        f"/api/v1/curricula/{curriculum_id}/versions/{version_id}"
        f"/courses/{course_id}/outcomes",
        json={"co_code": code, "description": description},
        headers=bearer(token),
    )
    assert response.status_code == 201, response.json()
    return response.json()


def create_approved_program_outcome(client, token, program_id, code, description):
    response = client.post(
        f"/api/v1/programs/{program_id}/program-outcomes",
        json={"po_code": code, "description": description},
        headers=bearer(token),
    )
    assert response.status_code == 201, response.json()
    outcome = response.json()
    for status in ("PROPOSED", "APPROVED"):
        status_response = client.patch(
            f"/api/v1/program-outcomes/{outcome['id']}/versions/"
            f"{outcome['current_version']['id']}/status",
            json={"status": status},
            headers=bearer(token),
        )
        assert status_response.status_code == 200, status_response.json()
    return outcome


def approve_program_outcome_version(client, token, outcome):
    latest = max(outcome["versions"], key=lambda version: version["version_number"])
    for status in ("PROPOSED", "APPROVED"):
        status_response = client.patch(
            f"/api/v1/program-outcomes/{outcome['id']}/versions/{latest['id']}/status",
            json={"status": status},
            headers=bearer(token),
        )
        assert status_response.status_code == 200, status_response.json()


def add_mapping(client, token, curriculum_id, version_id, co_id, po_id, level_code):
    response = client.post(
        f"/api/v1/curricula/{curriculum_id}/versions/{version_id}/mappings",
        json={
            "course_outcome_id": co_id,
            "program_outcome_id": po_id,
            "mapping_level_code": level_code,
        },
        headers=bearer(token),
    )
    assert response.status_code == 201, response.json()
    return response.json()


def add_prerequisite(client, token, curriculum_id, version_id, prerequisite_id, target_id):
    response = client.post(
        f"/api/v1/curricula/{curriculum_id}/versions/{version_id}/prerequisites",
        json={
            "prerequisite_course_id": prerequisite_id,
            "target_course_id": target_id,
        },
        headers=bearer(token),
    )
    assert response.status_code == 201, response.json()
    return response.json()


def test_compare_versions_reports_prerequisite_outcome_and_mapping_changes(
    client, admin_token, program
):
    seed_mapping_levels()
    curriculum, v1 = create_curriculum(client, admin_token, program)
    v1_courses = {course["course_code"]: course for course in v1["courses"]}

    v1_co1 = add_course_outcome(
        client, admin_token, curriculum["id"], v1["id"], v1_courses["CS101"]["id"],
        "CO1", "Original course outcome",
    )
    add_course_outcome(
        client, admin_token, curriculum["id"], v1["id"], v1_courses["CS101"]["id"],
        "CO2", "Removed course outcome",
    )
    cs201_co1 = add_course_outcome(
        client, admin_token, curriculum["id"], v1["id"], v1_courses["CS201"]["id"],
        "CO1", "Stable course outcome",
    )

    po1 = create_approved_program_outcome(
        client, admin_token, program["id"], "PO1", "Original program outcome"
    )
    po2 = create_approved_program_outcome(
        client, admin_token, program["id"], "PO2", "Removed program outcome"
    )

    add_mapping(
        client, admin_token, curriculum["id"], v1["id"],
        v1_co1["id"], po1["id"], "LOW",
    )
    add_mapping(
        client, admin_token, curriculum["id"], v1["id"],
        v1_co1["id"], po2["id"], "MEDIUM",
    )
    add_mapping(
        client, admin_token, curriculum["id"], v1["id"],
        cs201_co1["id"], po1["id"], "HIGH",
    )
    add_prerequisite(
        client, admin_token, curriculum["id"], v1["id"],
        v1_courses["CS101"]["id"], v1_courses["CS201"]["id"],
    )

    set_version_status(
        client, admin_token, curriculum["id"], v1["id"], ("UNDER_REVIEW", "APPROVED")
    )

    version_response = client.post(
        f"/api/v1/curricula/{curriculum['id']}/versions",
        json={"change_summary": "Comparison test version"},
        headers=bearer(admin_token),
    )
    assert version_response.status_code == 201, version_response.json()
    v2 = version_response.json()
    v2_courses = {course["course_code"]: course for course in v2["courses"]}

    v2_co1 = add_course_outcome(
        client, admin_token, curriculum["id"], v2["id"], v2_courses["CS101"]["id"],
        "CO1", "Updated course outcome",
    )
    v2_co3 = add_course_outcome(
        client, admin_token, curriculum["id"], v2["id"], v2_courses["CS101"]["id"],
        "CO3", "Added course outcome",
    )
    v2_cs201_co1 = add_course_outcome(
        client, admin_token, curriculum["id"], v2["id"], v2_courses["CS201"]["id"],
        "CO1", "Stable course outcome",
    )

    updated_po1_response = client.patch(
        f"/api/v1/program-outcomes/{po1['id']}",
        json={"description": "Updated program outcome"},
        headers=bearer(admin_token),
    )
    assert updated_po1_response.status_code == 200, updated_po1_response.json()
    updated_po1 = updated_po1_response.json()
    assert updated_po1["versions"][-1]["description"] == "Updated program outcome"
    approve_program_outcome_version(client, admin_token, updated_po1)
    po3 = create_approved_program_outcome(
        client, admin_token, program["id"], "PO3", "Added program outcome"
    )

    add_mapping(
        client, admin_token, curriculum["id"], v2["id"],
        v2_co1["id"], updated_po1["id"], "HIGH",
    )
    add_mapping(
        client, admin_token, curriculum["id"], v2["id"],
        v2_co3["id"], po3["id"], "LOW",
    )
    add_mapping(
        client, admin_token, curriculum["id"], v2["id"],
        v2_cs201_co1["id"], updated_po1["id"], "HIGH",
    )
    add_prerequisite(
        client, admin_token, curriculum["id"], v2["id"],
        v2_courses["CS201"]["id"], v2_courses["CS101"]["id"],
    )

    response = client.get(
        f"/api/v1/curricula/{curriculum['id']}/compare",
        params={"base_version_id": v1["id"], "target_version_id": v2["id"]},
        headers=bearer(admin_token),
    )
    assert response.status_code == 200, response.json()
    comparison = response.json()

    assert comparison["added_courses"] == []
    assert comparison["removed_courses"] == []
    assert comparison["modified_courses"] == []

    assert comparison["added_prerequisites"] == [
        {"prerequisite_course_code": "CS201", "target_course_code": "CS101"}
    ]
    assert comparison["removed_prerequisites"] == [
        {"prerequisite_course_code": "CS101", "target_course_code": "CS201"}
    ]

    assert comparison["added_course_outcomes"] == [
        {
            "course_code": "CS101",
            "co_code": "CO3",
            "description": "Added course outcome",
        }
    ]
    assert comparison["removed_course_outcomes"] == [
        {
            "course_code": "CS101",
            "co_code": "CO2",
            "description": "Removed course outcome",
        }
    ]
    assert comparison["modified_course_outcomes"] == [
        {
            "course_code": "CS101",
            "co_code": "CO1",
            "before_description": "Original course outcome",
            "after_description": "Updated course outcome",
        }
    ]

    assert comparison["added_program_outcomes"] == [
        {"po_code": "PO3", "description": "Added program outcome"}
    ]
    assert comparison["removed_program_outcomes"] == [
        {"po_code": "PO2", "description": "Removed program outcome"}
    ]
    assert comparison["modified_program_outcomes"] == [
        {
            "po_code": "PO1",
            "before_description": "Original program outcome",
            "after_description": "Updated program outcome",
        }
    ]

    assert comparison["added_mappings"] == [
        {
            "course_code": "CS101",
            "co_code": "CO3",
            "po_code": "PO3",
            "mapping_level_code": "LOW",
        }
    ]
    assert comparison["removed_mappings"] == [
        {
            "course_code": "CS101",
            "co_code": "CO1",
            "po_code": "PO2",
            "mapping_level_code": "MEDIUM",
        }
    ]
    assert comparison["modified_mappings"] == [
        {
            "course_code": "CS101",
            "co_code": "CO1",
            "po_code": "PO1",
            "before_mapping_level_code": "LOW",
            "after_mapping_level_code": "HIGH",
        }
    ]
