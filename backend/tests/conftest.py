import os
import uuid
from datetime import timedelta
from typing import Any

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["JWT_SECRET"] = "test-jwt-secret-that-is-at-least-32-characters"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "60"
os.environ["BOOTSTRAP_ADMIN_PASSWORD"] = ""
os.environ["MAX_UPLOAD_SIZE_MB"] = "1"
os.environ["ALLOWED_UPLOAD_EXTENSIONS"] = '[".pdf", ".docx", ".txt", ".md", ".csv"]'
os.environ.pop("BOOTSTRAP_ADMIN_USERNAME", None)
os.environ.pop("BOOTSTRAP_ADMIN_EMAIL", None)
os.environ.pop("CORS_ORIGINS", None)
os.environ.pop("LLM_API_KEY", None)
os.environ.pop("UPLOADTHING_TOKEN", None)
os.environ.pop("UPLOADTHING_API_KEY", None)
os.environ.pop("UPLOADTHING_APP_ID", None)
os.environ.pop("UPLOADTHING_REGION", None)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.deps import get_uploadthing_client
from app.core.security import get_jwt_service, get_password_service
from app.db.base import Base
from app.db.models import (
    CourseType,
    Role,
    RoleCode,
    User,
    UserRole,
    UserStatus,
)
from app.db.session import SessionLocal, engine
from app.main import app
from app.services.uploadthing import UploadedFile, UploadThingError


class SharedStubStorage:
    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}
        self.uploads: list[dict[str, Any]] = []
        self.counter = 0

    def upload_file(
        self, data: bytes, filename: str, content_type: str | None = None
    ) -> UploadedFile:
        self.counter += 1
        key = f"ut-key-{self.counter}"
        self.files[key] = data
        self.uploads.append(
            {"data": data, "filename": filename, "content_type": content_type}
        )
        return UploadedFile(
            key=key, ufs_url=f"https://stub-app.ufs.sh/f/{key}", file_hash=None
        )

    def read_file(self, key: str) -> bytes:
        try:
            return self.files[key]
        except KeyError as exc:
            raise UploadThingError(f"stored file {key} is missing") from exc


shared_stub_storage = SharedStubStorage()
app.dependency_overrides[get_uploadthing_client] = lambda: shared_stub_storage


@pytest.fixture
def storage_stub() -> SharedStubStorage:
    return shared_stub_storage


@pytest.fixture(autouse=True)
def clean_database():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    shared_stub_storage.files.clear()
    shared_stub_storage.uploads.clear()
    shared_stub_storage.counter = 0
    with SessionLocal() as session:
        for code in RoleCode:
            session.add(
                Role(
                    id=uuid.uuid4(),
                    code=code.value,
                    name=code.value.replace("_", " ").title(),
                )
            )
        for code, name in (
            ("CORE", "Core"),
            ("ELECTIVE", "Elective"),
            ("LAB", "Laboratory"),
        ):
            session.add(CourseType(id=uuid.uuid4(), code=code, name=name, is_active=True))
        session.commit()
    yield


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def make_user():
    def factory(
        username: str = "faculty1",
        password: str = "Password123!",
        roles: tuple[RoleCode | str, ...] = (RoleCode.FACULTY,),
        status: UserStatus = UserStatus.ACTIVE,
        email: str | None = None,
    ) -> uuid.UUID:
        role_codes = [role.value if isinstance(role, RoleCode) else role for role in roles]
        with SessionLocal() as session:
            role_models = list(session.scalars(select(Role).where(Role.code.in_(role_codes))).all())
            user = User(
                id=uuid.uuid4(),
                username=username,
                email=email or f"{username}@example.com",
                password_hash=get_password_service().hash(password),
                full_name="Test User",
                status=status.value,
            )
            session.add(user)
            session.flush()
            for role in role_models:
                session.add(UserRole(user_id=user.id, role_id=role.id))
            session.commit()
            return user.id

    return factory


def login(client: TestClient, username: str, password: str):
    return client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_token(client, make_user):
    make_user(username="admin", roles=(RoleCode.ADMIN,))
    response = login(client, "admin", "Password123!")
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture
def faculty_token(client, make_user):
    make_user(username="faculty", roles=(RoleCode.FACULTY,))
    response = login(client, "faculty", "Password123!")
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture
def committee_token(client, make_user):
    make_user(username="committee", roles=(RoleCode.COMMITTEE_MEMBER,))
    response = login(client, "committee", "Password123!")
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture
def reviewer_token(client, make_user):
    make_user(username="reviewer", roles=(RoleCode.REVIEWER,))
    response = login(client, "reviewer", "Password123!")
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture
def department(client, admin_token):
    response = client.post(
        "/api/v1/departments",
        json={"code": "CSE", "name": "Computer Science and Engineering"},
        headers=bearer(admin_token),
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def program(client, admin_token, department):
    response = client.post(
        "/api/v1/programs",
        json={
            "department_id": department["id"],
            "code": "BTECH-CSE",
            "name": "B.Tech Computer Science and Engineering",
            "degree_type": "B.Tech",
            "duration_years": 4,
        },
        headers=bearer(admin_token),
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def expired_token(make_user):
    user_id = make_user(username="expired", roles=(RoleCode.FACULTY,))
    return get_jwt_service().create_access_token(
        user_id,
        "expired",
        [RoleCode.FACULTY.value],
        expires_delta=timedelta(seconds=-1),
    )

