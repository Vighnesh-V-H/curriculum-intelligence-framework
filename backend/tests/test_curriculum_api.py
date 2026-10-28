from tests.conftest import bearer


def curriculum_payload(program_id: str, regulation: str = "2026"):
    return {
        "program_id": program_id,
        "academic_year": "2026-27",
        "regulation": regulation,
        "title": "B.Tech CSE Curriculum",
        "duration_years": 4,
        "semesters": [
            {"semester_number": number, "name": f"Semester {number}"} for number in range(1, 9)
        ],
        "courses": [
            {
                "course_code": "CS101",
                "course_name": "Programming Fundamentals",
                "course_type_code": "CORE",
                "credits": 4,
                "semester_number": 1,
                "contact_hours": 4,
            },
            {
                "course_code": "CS201",
                "course_name": "Data Structures",
                "course_type_code": "CORE",
                "credits": 4,
                "semester_number": 3,
            },
        ],
    }


def test_faculty_can_create_curriculum_with_initial_draft_version(client, faculty_token, program):
    response = client.post(
        "/api/v1/curricula",
        json=curriculum_payload(program["id"]),
        headers=bearer(faculty_token),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["program_id"] == program["id"]
    assert body["program_code"] == "BTECH-CSE"
    assert body["regulation"] == "2026"
    assert body["latest_version"]["version_label"] == "1.0"
    assert body["latest_version"]["status"] == "DRAFT"
    assert len(body["versions"]) == 1

    version = body["versions"][0]
    assert version["version_label"] == "1.0"
    assert version["status"] == "DRAFT"
    assert len(version["semesters"]) == 8
    assert {course["course_code"] for course in version["courses"]} == {
        "CS101",
        "CS201",
    }
    assert all(course["status"] == "ACTIVE" for course in version["courses"])


def test_duplicate_regulation_for_program_is_rejected(client, faculty_token, program):
    payload = curriculum_payload(program["id"])
    first = client.post("/api/v1/curricula", json=payload, headers=bearer(faculty_token))
    assert first.status_code == 201

    second = client.post("/api/v1/curricula", json=payload, headers=bearer(faculty_token))

    assert second.status_code == 409
    assert second.json()["error"]["code"] == "curriculum_exists"


def test_different_regulations_for_same_program_are_allowed(client, faculty_token, program):
    first = client.post(
        "/api/v1/curricula",
        json=curriculum_payload(program["id"], "2026"),
        headers=bearer(faculty_token),
    )
    second = client.post(
        "/api/v1/curricula",
        json=curriculum_payload(program["id"], "2027"),
        headers=bearer(faculty_token),
    )

    assert first.status_code == 201
    assert second.status_code == 201


def test_create_curriculum_requires_existing_program(client, faculty_token):
    response = client.post(
        "/api/v1/curricula",
        json=curriculum_payload("00000000-0000-0000-0000-000000000099"),
        headers=bearer(faculty_token),
    )

    assert response.status_code == 404


def test_create_curriculum_rejects_invalid_course_type(client, faculty_token, program):
    payload = curriculum_payload(program["id"])
    payload["courses"][0]["course_type_code"] = "UNKNOWN"

    response = client.post("/api/v1/curricula", json=payload, headers=bearer(faculty_token))

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_course_type"


def test_create_curriculum_rejects_undefined_semester(client, faculty_token, program):
    payload = curriculum_payload(program["id"])
    payload["courses"][0]["semester_number"] = 12

    response = client.post("/api/v1/curricula", json=payload, headers=bearer(faculty_token))

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_create_curriculum_rejects_duplicate_course_codes(client, faculty_token, program):
    payload = curriculum_payload(program["id"])
    payload["courses"][1]["course_code"] = "CS101"

    response = client.post("/api/v1/curricula", json=payload, headers=bearer(faculty_token))

    assert response.status_code == 422


def test_reviewer_cannot_create_curriculum(client, reviewer_token, program):
    response = client.post(
        "/api/v1/curricula",
        json=curriculum_payload(program["id"]),
        headers=bearer(reviewer_token),
    )

    assert response.status_code == 403


def test_list_and_get_curriculum(client, faculty_token, program):
    created = client.post(
        "/api/v1/curricula",
        json=curriculum_payload(program["id"]),
        headers=bearer(faculty_token),
    ).json()

    listed = client.get("/api/v1/curricula", headers=bearer(faculty_token))
    fetched = client.get(f"/api/v1/curricula/{created['id']}", headers=bearer(faculty_token))

    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["latest_version"]["version_label"] == "1.0"
    assert fetched.status_code == 200
    assert fetched.json()["id"] == created["id"]


def test_list_versions_and_get_single_version(client, faculty_token, program):
    created = client.post(
        "/api/v1/curricula",
        json=curriculum_payload(program["id"]),
        headers=bearer(faculty_token),
    ).json()
    version_id = created["versions"][0]["id"]

    versions = client.get(
        f"/api/v1/curricula/{created['id']}/versions",
        headers=bearer(faculty_token),
    )
    version = client.get(
        f"/api/v1/curricula/{created['id']}/versions/{version_id}",
        headers=bearer(faculty_token),
    )

    assert versions.status_code == 200
    assert len(versions.json()) == 1
    assert version.status_code == 200
    assert version.json()["id"] == version_id


def test_unknown_curriculum_returns_404(client, faculty_token):
    response = client.get(
        "/api/v1/curricula/00000000-0000-0000-0000-000000000099",
        headers=bearer(faculty_token),
    )

    assert response.status_code == 404
