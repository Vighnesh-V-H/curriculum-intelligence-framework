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


def test_faculty_can_create_curriculum_with_immediately_available_content(
    client, faculty_token, program
):
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
    assert body["latest_version"]["status"] == "APPROVED"
    assert len(body["versions"]) == 1

    version = body["versions"][0]
    assert version["version_label"] == "1.0"
    assert version["status"] == "APPROVED"
    assert len(version["semesters"]) == 8
    assert {course["course_code"] for course in version["courses"]} == {
        "CS101",
        "CS201",
    }
    assert all(course["status"] == "ACTIVE" for course in version["courses"])


def test_multiple_curricula_with_same_regulation_are_allowed(client, faculty_token, program):
    payload = curriculum_payload(program["id"])
    first = client.post("/api/v1/curricula", json=payload, headers=bearer(faculty_token))
    second = client.post("/api/v1/curricula", json=payload, headers=bearer(faculty_token))

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] != second.json()["id"]


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


def test_update_curriculum_metadata(client, faculty_token, program):
    created = client.post(
        "/api/v1/curricula",
        json=curriculum_payload(program["id"]),
        headers=bearer(faculty_token),
    ).json()

    response = client.patch(
        f"/api/v1/curricula/{created['id']}",
        json={
            "academic_year": "2027-28",
            "regulation": "2027",
            "title": "Revised CSE Curriculum",
            "description": "Revised programme description.",
            "duration_years": 3.5,
        },
        headers=bearer(faculty_token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["academic_year"] == "2027-28"
    assert body["regulation"] == "2027"
    assert body["title"] == "Revised CSE Curriculum"
    assert body["description"] == "Revised programme description."
    assert body["duration_years"] == 3.5

    fetched = client.get(
        f"/api/v1/curricula/{created['id']}", headers=bearer(faculty_token)
    )
    assert fetched.json()["regulation"] == "2027"


def test_update_curriculum_allows_duplicate_regulation(client, faculty_token, program):
    first = client.post(
        "/api/v1/curricula",
        json=curriculum_payload(program["id"], "2026"),
        headers=bearer(faculty_token),
    ).json()
    second = client.post(
        "/api/v1/curricula",
        json=curriculum_payload(program["id"], "2027"),
        headers=bearer(faculty_token),
    ).json()

    response = client.patch(
        f"/api/v1/curricula/{second['id']}",
        json={"regulation": first["regulation"]},
        headers=bearer(faculty_token),
    )

    assert response.status_code == 200
    assert response.json()["regulation"] == first["regulation"]


def test_update_curriculum_does_not_require_approval_workflow(client, faculty_token, program):
    created = client.post(
        "/api/v1/curricula",
        json=curriculum_payload(program["id"]),
        headers=bearer(faculty_token),
    ).json()
    response = client.patch(
        f"/api/v1/curricula/{created['id']}",
        json={"title": "Should not apply"},
        headers=bearer(faculty_token),
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Should not apply"


def test_update_and_remove_course_outcome(client, faculty_token, program):
    created = client.post(
        "/api/v1/curricula",
        json=curriculum_payload(program["id"]),
        headers=bearer(faculty_token),
    ).json()
    version = created["versions"][0]
    course = version["courses"][0]
    outcome_url = (
        f"/api/v1/curricula/{created['id']}/versions/{version['id']}"
        f"/courses/{course['id']}/outcomes"
    )
    created_outcome = client.post(
        outcome_url,
        json={"co_code": "co1", "description": "Original statement"},
        headers=bearer(faculty_token),
    )
    assert created_outcome.status_code == 201
    outcome = created_outcome.json()
    assert outcome["co_code"] == "CO1"

    updated = client.patch(
        f"{outcome_url}/{outcome['id']}",
        json={"co_code": "co2", "description": "Revised statement"},
        headers=bearer(faculty_token),
    )

    assert updated.status_code == 200
    assert updated.json()["co_code"] == "CO2"
    assert updated.json()["description"] == "Revised statement"

    removed = client.delete(
        f"{outcome_url}/{outcome['id']}", headers=bearer(faculty_token)
    )
    assert removed.status_code == 204

    listed = client.get(outcome_url, headers=bearer(faculty_token))
    assert listed.status_code == 200
    assert listed.json() == []

    repeated = client.delete(
        f"{outcome_url}/{outcome['id']}", headers=bearer(faculty_token)
    )
    assert repeated.status_code == 404


def test_update_course_outcome_rejects_duplicate_code(client, faculty_token, program):
    created = client.post(
        "/api/v1/curricula",
        json=curriculum_payload(program["id"]),
        headers=bearer(faculty_token),
    ).json()
    version = created["versions"][0]
    course = version["courses"][0]
    outcome_url = (
        f"/api/v1/curricula/{created['id']}/versions/{version['id']}"
        f"/courses/{course['id']}/outcomes"
    )
    first = client.post(
        outcome_url,
        json={"co_code": "CO1", "description": "First outcome"},
        headers=bearer(faculty_token),
    ).json()
    second = client.post(
        outcome_url,
        json={"co_code": "CO2", "description": "Second outcome"},
        headers=bearer(faculty_token),
    ).json()

    response = client.patch(
        f"{outcome_url}/{second['id']}",
        json={"co_code": first["co_code"]},
        headers=bearer(faculty_token),
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "course_outcome_exists"


def test_remove_course_with_prerequisite_dependency_requires_force(
    client, faculty_token, program
):
    created = client.post(
        "/api/v1/curricula",
        json=curriculum_payload(program["id"]),
        headers=bearer(faculty_token),
    ).json()
    version = created["versions"][0]
    courses = {course["course_code"]: course for course in version["courses"]}
    prerequisite = client.post(
        f"/api/v1/curricula/{created['id']}/versions/{version['id']}/prerequisites",
        json={
            "prerequisite_course_id": courses["CS101"]["id"],
            "target_course_id": courses["CS201"]["id"],
        },
        headers=bearer(faculty_token),
    )
    assert prerequisite.status_code == 201

    course_url = (
        f"/api/v1/curricula/{created['id']}/versions/{version['id']}"
        f"/courses/{courses['CS101']['id']}"
    )
    blocked = client.delete(course_url, headers=bearer(faculty_token))
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "course_has_dependencies"

    forced = client.delete(f"{course_url}?force=true", headers=bearer(faculty_token))
    assert forced.status_code == 204

    detail = client.get(
        f"/api/v1/curricula/{created['id']}/versions/{version['id']}",
        headers=bearer(faculty_token),
    )
    assert detail.status_code == 200
    assert {course["course_code"] for course in detail.json()["courses"]} == {"CS201"}
