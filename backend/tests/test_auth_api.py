from app.db.models import RoleCode, UserStatus
from tests.conftest import bearer, login


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_login_returns_token_and_user(client, make_user):
    make_user(username="faculty1", roles=(RoleCode.FACULTY,))

    response = login(client, "faculty1", "Password123!")

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 3600
    assert body["access_token"]
    assert body["user"]["username"] == "faculty1"
    assert body["user"]["roles"] == ["FACULTY"]
    assert body["user"]["last_login_at"] is not None


def test_login_accepts_email(client, make_user):
    make_user(username="faculty1", roles=(RoleCode.FACULTY,))

    response = login(client, "faculty1@example.com", "Password123!")

    assert response.status_code == 200
    assert response.json()["user"]["username"] == "faculty1"


def test_login_rejects_wrong_password(client, make_user):
    make_user(username="faculty1")

    response = login(client, "faculty1", "wrong-password")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


def test_login_rejects_unknown_user(client):
    response = login(client, "missing", "Password123!")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


def test_login_rejects_inactive_user(client, make_user):
    make_user(username="inactive", status=UserStatus.INACTIVE)

    response = login(client, "inactive", "Password123!")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "account_inactive"


def test_me_requires_token(client):
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401


def test_me_returns_current_user(client, make_user):
    make_user(username="faculty1", roles=(RoleCode.FACULTY, RoleCode.REVIEWER))
    token = login(client, "faculty1", "Password123!").json()["access_token"]

    response = client.get("/api/v1/auth/me", headers=bearer(token))

    assert response.status_code == 200
    assert response.json()["username"] == "faculty1"
    assert response.json()["roles"] == ["FACULTY", "REVIEWER"]


def test_me_rejects_expired_token(client, expired_token):
    response = client.get("/api/v1/auth/me", headers=bearer(expired_token))

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_token"


def test_me_rejects_malformed_token(client):
    response = client.get("/api/v1/auth/me", headers=bearer("not-a-jwt"))

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_token"
