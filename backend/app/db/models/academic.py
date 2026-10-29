import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.user import utc_now


class DepartmentStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class ProgramStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class CurriculumStatus(StrEnum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class VersionStatus(StrEnum):
    DRAFT = "DRAFT"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


class CourseStatus(StrEnum):
    ACTIVE = "ACTIVE"
    REMOVED = "REMOVED"


class CourseOutcomeStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=DepartmentStatus.ACTIVE.value
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    programs: Mapped[list["Program"]] = relationship(back_populates="department")


class Program(Base):
    __tablename__ = "programs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    department_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("departments.id"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    degree_type: Mapped[str | None] = mapped_column(String(50))
    duration_years: Mapped[Decimal] = mapped_column(Numeric(3, 1), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ProgramStatus.ACTIVE.value
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    department: Mapped[Department] = relationship(back_populates="programs", lazy="joined")
    curricula: Mapped[list["Curriculum"]] = relationship(back_populates="program")


class Curriculum(Base):
    __tablename__ = "curricula"
    __table_args__ = (
        UniqueConstraint("program_id", "regulation", name="uq_curricula_program_regulation"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    program_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("programs.id"), nullable=False)
    academic_year: Mapped[str] = mapped_column(String(20), nullable=False)
    regulation: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str | None] = mapped_column(String(200))
    duration_years: Mapped[Decimal] = mapped_column(Numeric(3, 1), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=CurriculumStatus.ACTIVE.value
    )
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    program: Mapped[Program] = relationship(back_populates="curricula", lazy="joined")
    versions: Mapped[list["CurriculumVersion"]] = relationship(
        back_populates="curriculum",
        cascade="all, delete-orphan",
        order_by="CurriculumVersion.created_at",
        lazy="selectin",
    )


class CurriculumVersion(Base):
    __tablename__ = "curriculum_versions"
    __table_args__ = (
        UniqueConstraint("curriculum_id", "version_label", name="uq_curriculum_versions"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    curriculum_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("curricula.id", ondelete="CASCADE"), nullable=False
    )
    version_label: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=VersionStatus.DRAFT.value
    )
    previous_version_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("curriculum_versions.id")
    )
    change_summary: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    published_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    curriculum: Mapped[Curriculum] = relationship(back_populates="versions")
    semesters: Mapped[list["Semester"]] = relationship(
        back_populates="version",
        cascade="all, delete-orphan",
        order_by="Semester.semester_number",
        lazy="selectin",
    )
    courses: Mapped[list["Course"]] = relationship(
        back_populates="version",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class Semester(Base):
    __tablename__ = "semesters"
    __table_args__ = (
        UniqueConstraint("curriculum_version_id", "semester_number", name="uq_semesters"),
        UniqueConstraint("id", "curriculum_version_id", name="uq_semesters_id_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    curriculum_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("curriculum_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    semester_number: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    name: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    version: Mapped[CurriculumVersion] = relationship(back_populates="semesters")
    courses: Mapped[list["Course"]] = relationship(back_populates="semester")


class CourseType(Base):
    __tablename__ = "course_types"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class Course(Base):
    __tablename__ = "courses"
    __table_args__ = (
        UniqueConstraint("id", "curriculum_version_id", name="uq_courses_id_version"),
        Index(
            "uq_courses_code_active",
            "curriculum_version_id",
            "course_code",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
            sqlite_where=text("status = 'ACTIVE'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    curriculum_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("curriculum_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    semester_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("semesters.id"), nullable=False)
    course_code: Mapped[str] = mapped_column(String(30), nullable=False)
    course_name: Mapped[str] = mapped_column(String(200), nullable=False)
    course_type_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("course_types.id"), nullable=False
    )
    credits: Mapped[Decimal] = mapped_column(Numeric(4, 1), nullable=False)
    contact_hours: Mapped[int | None] = mapped_column(Integer)
    description: Mapped[str | None] = mapped_column(Text)
    syllabus: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=CourseStatus.ACTIVE.value
    )
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))
    removed_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    version: Mapped[CurriculumVersion] = relationship(back_populates="courses")
    semester: Mapped[Semester] = relationship(back_populates="courses", lazy="joined")
    course_type: Mapped[CourseType] = relationship(lazy="joined")
    outcomes: Mapped[list["CourseOutcome"]] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
        order_by="CourseOutcome.co_code",
        lazy="selectin",
    )


class CourseOutcome(Base):
    __tablename__ = "course_outcomes"
    __table_args__ = (
        Index(
            "uq_course_outcomes_code_active",
            "course_id",
            "co_code",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
            sqlite_where=text("status = 'ACTIVE'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    course_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    curriculum_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("curriculum_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    co_code: Mapped[str] = mapped_column(String(30), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=CourseOutcomeStatus.ACTIVE.value
    )
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    course: Mapped[Course] = relationship(back_populates="outcomes")


class CoursePrerequisite(Base):
    __tablename__ = "course_prerequisites"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    curriculum_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("curriculum_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    prerequisite_course_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("courses.id"), nullable=False
    )
    target_course_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("courses.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PROPOSED")
    review_comments: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    target_course: Mapped[Course] = relationship(foreign_keys=[target_course_id], lazy="joined")
