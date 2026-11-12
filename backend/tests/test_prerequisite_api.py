from tests.conftest import bearer
from tests.test_curriculum_api import curriculum_payload


def make_curriculum(client, token, program):
    response = client.post(
        "/api/v1/curricula",
        json=curriculum_payload(program["id"]),
        headers=bearer(token),
    )
    assert response.status_code == 201
    body = response.json()
    return body, body["versions"][0]


def test_remove_prerequisite(client, faculty_token, admin_token, program):
    curriculum, version = make_curriculum(client, admin_token, program)
    courses = {course["course_code"]: course for course in version["courses"]}
    base_url = (
        f"/api/v1/curricula/{curriculum['id']}/versions/{version['id']}"
        "/prerequisites"
    )

    created = client.post(
        base_url,
        json={
            "prerequisite_course_id": courses["CS101"]["id"],
            "target_course_id": courses["CS201"]["id"],
        },
        headers=bearer(faculty_token),
    )
    assert created.status_code == 201
    prerequisite = created.json()
    assert prerequisite["status"] == "PROPOSED"

    removed = client.delete(
        f"{base_url}/{prerequisite['id']}", headers=bearer(faculty_token)
    )
    assert removed.status_code == 204

    listed = client.get(base_url, headers=bearer(faculty_token))
    assert listed.status_code == 200
    assert listed.json() == []

    repeated = client.delete(
        f"{base_url}/{prerequisite['id']}", headers=bearer(faculty_token)
    )
    assert repeated.status_code == 404


def test_reviewer_cannot_remove_prerequisite(
    client, faculty_token, admin_token, reviewer_token, program
):
    curriculum, version = make_curriculum(client, admin_token, program)
    courses = {course["course_code"]: course for course in version["courses"]}
    base_url = (
        f"/api/v1/curricula/{curriculum['id']}/versions/{version['id']}"
        "/prerequisites"
    )
    created = client.post(
        base_url,
        json={
            "prerequisite_course_id": courses["CS101"]["id"],
            "target_course_id": courses["CS201"]["id"],
        },
        headers=bearer(faculty_token),
    )
    assert created.status_code == 201

    response = client.delete(
        f"{base_url}/{created.json()['id']}", headers=bearer(reviewer_token)
    )

    assert response.status_code == 403
