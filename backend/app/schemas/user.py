import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.db.models.user import RoleCode, User, UserStatus


class UserResponse(BaseModel):
    id: uuid.UUID
    username: str
    email: str
    full_name: str
    status: str
    roles: list[str]
    last_login_at: datetime | None
    created_at: datetime

    @classmethod
    def from_user(cls, user: User) -> "UserResponse":
        return cls(
            id=user.id,
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            status=user.status,
            roles=sorted(assignment.role.code for assignment in user.role_assignments),
            last_login_at=user.last_login_at,
            created_at=user.created_at,
        )


class CreateUserRequest(BaseModel):
    username: str = Field(min_length=3, max_length=100, pattern=r"^[a-zA-Z0-9._-]+$")
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=200)
    roles: list[RoleCode] = Field(min_length=1)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()

    @field_validator("full_name")
    @classmethod
    def normalize_full_name(cls, value: str) -> str:
        return value.strip()


class AssignRolesRequest(BaseModel):
    roles: list[RoleCode] = Field(min_length=1)


class UpdateUserStatusRequest(BaseModel):
    status: UserStatus
