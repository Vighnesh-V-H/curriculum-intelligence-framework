from tests.conftest import bearer, login


def create_user_payload(**overrides):
    payload = {
        "username": "new.faculty",
        "email": "new.faculty@example.com",
        "password": "Password123!",
        "full_name": "New Faculty",
        "roles": ["FACULTY"],
    }
    payload.update(overrides)
    return payload


def test_admin_can_create_user(client, admin_token):
    response = client.post(
        "/api/v1/users",
        json=create_user_payload(),
        headers=bearer(admin_token),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["username"] == "new.faculty"
    assert body["email"] == "new.faculty@example.com"
    assert body["status"] == "ACTIVE"
    assert body["roles"] == ["FACULTY"]

    login_response = login(client, "new.faculty", "Password123!")
    assert login_response.status_code == 200


def test_non_admin_cannot_create_user(client, faculty_token):
    response = client.post(
        "/api/v1/users",
        json=create_user_payload(),
        headers=bearer(faculty_token),
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_create_user_requires_authentication(client):
    response = client.post("/api/v1/users", json=create_user_payload())

    assert response.status_code == 401


def test_create_user_rejects_duplicate_username(client, admin_token, make_user):
    make_user(username="existing")

    response = client.post(
        "/api/v1/users",
        json=create_user_payload(username="existing"),
        headers=bearer(admin_token),
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "username_taken"


def test_create_user_rejects_duplicate_email(client, admin_token, make_user):
    make_user(username="existing", email="taken@example.com")

    response = client.post(
        "/api/v1/users",
        json=create_user_payload(email="taken@example.com"),
        headers=bearer(admin_token),
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "email_taken"


def test_create_user_validates_required_fields(client, admin_token):
    response = client.post(
        "/api/v1/users",
        json={"username": "ab", "email": "not-an-email", "password": "short"},
        headers=bearer(admin_token),
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_admin_can_list_users(client, admin_token, make_user):
    make_user(username="faculty1")

    response = client.get("/api/v1/users", headers=bearer(admin_token))

    assert response.status_code == 200
    usernames = {user["username"] for user in response.json()}
    assert {"admin", "faculty1"} <= usernames


def test_admin_can_assign_roles(client, admin_token, make_user):
    user_id = make_user(username="faculty1", roles=("FACULTY",))

    response = client.put(
        f"/api/v1/users/{user_id}/roles",
        json={"roles": ["COMMITTEE_MEMBER", "REVIEWER"]},
        headers=bearer(admin_token),
    )

    assert response.status_code == 200
    assert response.json()["roles"] == ["COMMITTEE_MEMBER", "REVIEWER"]


def test_admin_can_deactivate_user(client, admin_token, make_user):
    user_id = make_user(username="faculty1")

    response = client.patch(
        f"/api/v1/users/{user_id}/status",
        json={"status": "INACTIVE"},
        headers=bearer(admin_token),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "INACTIVE"

    login_response = login(client, "faculty1", "Password123!")
    assert login_response.status_code == 403


def test_admin_can_get_user(client, admin_token, make_user):
    user_id = make_user(username="faculty1")

    response = client.get(f"/api/v1/users/{user_id}", headers=bearer(admin_token))

    assert response.status_code == 200
    assert response.json()["id"] == str(user_id)


def test_missing_user_returns_404(client, admin_token):
    response = client.get(
        "/api/v1/users/00000000-0000-0000-0000-000000000099",
        headers=bearer(admin_token),
    )

    assert response.status_code == 404
