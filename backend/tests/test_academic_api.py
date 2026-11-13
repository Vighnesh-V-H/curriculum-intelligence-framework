from tests.conftest import bearer


def test_admin_can_create_department_and_program(client, admin_token, department, program):
    assert department["code"] == "CSE"
    assert program["code"] == "BTECH-CSE"
    assert program["department_code"] == "CSE"
    assert program["duration_years"] == 4.0


def test_duplicate_department_code_is_rejected(client, admin_token, department):
    response = client.post(
        "/api/v1/departments",
        json={"code": "cse", "name": "Another Department"},
        headers=bearer(admin_token),
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "department_exists"


def test_duplicate_program_code_is_rejected(client, admin_token, department, program):
    response = client.post(
        "/api/v1/programs",
        json={
            "department_id": department["id"],
            "code": "btech-cse",
            "name": "Duplicate Program",
            "duration_years": 4,
        },
        headers=bearer(admin_token),
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "program_exists"


def test_program_requires_existing_department(client, admin_token):
    response = client.post(
        "/api/v1/programs",
        json={
            "department_id": "00000000-0000-0000-0000-000000000099",
            "code": "BTECH-ECE",
            "name": "B.Tech Electronics",
            "duration_years": 4,
        },
        headers=bearer(admin_token),
    )

    assert response.status_code == 404


def test_faculty_can_create_program(client, faculty_token, department):
    response = client.post(
        "/api/v1/programs",
        json={
            "department_id": department["id"],
            "code": "BTECH-ECE",
            "name": "B.Tech Electronics",
            "degree_type": "B.Tech",
            "duration_years": 4,
        },
        headers=bearer(faculty_token),
    )

    assert response.status_code == 201
    assert response.json()["code"] == "BTECH-ECE"


def test_reviewer_can_create_program(client, reviewer_token, department):
    response = client.post(
        "/api/v1/programs",
        json={
            "department_id": department["id"],
            "code": "MSC-DS",
            "name": "M.Sc. Data Science",
            "duration_years": 2,
        },
        headers=bearer(reviewer_token),
    )

    assert response.status_code == 201


def test_faculty_can_create_department(client, faculty_token):
    response = client.post(
        "/api/v1/departments",
        json={"code": "ECE", "name": "Electronics"},
        headers=bearer(faculty_token),
    )

    assert response.status_code == 201
    assert response.json()["code"] == "ECE"


def test_reviewer_can_create_department(client, reviewer_token):
    response = client.post(
        "/api/v1/departments",
        json={"code": "MAT", "name": "Mathematics"},
        headers=bearer(reviewer_token),
    )

    assert response.status_code == 201


def test_reviewer_can_read_academic_structure(client, reviewer_token, department, program):
    departments = client.get("/api/v1/departments", headers=bearer(reviewer_token))
    programs = client.get("/api/v1/programs", headers=bearer(reviewer_token))
    course_types = client.get("/api/v1/course-types", headers=bearer(reviewer_token))

    assert departments.status_code == 200
    assert programs.status_code == 200
    assert course_types.status_code == 200
    assert {item["code"] for item in course_types.json()} == {"CORE", "ELECTIVE", "LAB"}
