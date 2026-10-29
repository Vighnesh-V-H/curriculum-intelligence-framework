import uuid
from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.academic import CourseOutcome
from app.db.models.outcomes import ProgramOutcome
from app.db.models.user import utc_now


class MappingStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class MappingVersionStatus(StrEnum):
    DRAFT = "DRAFT"
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"


class MappingLevel(Base):
    __tablename__ = "mapping_levels"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    numeric_value: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class CurriculumVersionProgramOutcome(Base):
    __tablename__ = "curriculum_version_program_outcomes"

    curriculum_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("curriculum_versions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    program_outcome_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("program_outcomes.id"), primary_key=True
    )
    program_outcome_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("program_outcome_versions.id"), nullable=False
    )
    added_by: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    program_outcome: Mapped[ProgramOutcome] = relationship(lazy="joined")


class CoPoMapping(Base):
    __tablename__ = "co_po_mappings"
    __table_args__ = (
        Index(
            "uq_co_po_mappings_active",
            "curriculum_version_id",
            "course_outcome_id",
            "program_outcome_id",
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
    course_outcome_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("course_outcomes.id"), nullable=False
    )
    program_outcome_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("program_outcomes.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=MappingStatus.ACTIVE.value
    )
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    course_outcome: Mapped[CourseOutcome] = relationship(lazy="joined")
    program_outcome: Mapped[ProgramOutcome] = relationship(lazy="joined")
    versions: Mapped[list["CoPoMappingVersion"]] = relationship(
        back_populates="mapping",
        cascade="all, delete-orphan",
        order_by="CoPoMappingVersion.version_number",
        lazy="selectin",
    )


class CoPoMappingVersion(Base):
    __tablename__ = "co_po_mapping_versions"
    __table_args__ = (
        UniqueConstraint("mapping_id", "version_number", name="uq_co_po_mapping_versions"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    mapping_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("co_po_mappings.id", ondelete="CASCADE"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    mapping_level_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("mapping_levels.id"), nullable=False
    )
    effective_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=MappingVersionStatus.DRAFT.value
    )
    review_comments: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    mapping: Mapped[CoPoMapping] = relationship(back_populates="versions")
    mapping_level: Mapped[MappingLevel] = relationship(lazy="joined")
