import uuid
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class UserStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    LOCKED = "LOCKED"


class RoleCode(StrEnum):
    ADMIN = "ADMIN"
    COMMITTEE_MEMBER = "COMMITTEE_MEMBER"
    FACULTY = "FACULTY"
    REVIEWER = "REVIEWER"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=UserStatus.ACTIVE.value)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    role_assignments: Mapped[list["UserRole"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="UserRole.user_id",
        lazy="selectin",
    )


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class UserRole(Base):
    __tablename__ = "user_roles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("roles.id"), primary_key=True)
    assigned_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    user: Mapped[User] = relationship(back_populates="role_assignments", foreign_keys=[user_id])
    role: Mapped[Role] = relationship(lazy="joined")
    assigner: Mapped[User | None] = relationship(foreign_keys=[assigned_by])
