import uuid
from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.academic import Program
from app.db.models.user import utc_now


class OutcomeStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class OutcomeVersionStatus(StrEnum):
    DRAFT = "DRAFT"
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"


class ProgramOutcome(Base):
    __tablename__ = "program_outcomes"
    __table_args__ = (UniqueConstraint("program_id", "po_code", name="uq_program_outcomes_code"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    program_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("programs.id"), nullable=False)
    po_code: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=OutcomeStatus.ACTIVE.value
    )
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    program: Mapped[Program] = relationship(lazy="joined")
    versions: Mapped[list["ProgramOutcomeVersion"]] = relationship(
        back_populates="program_outcome",
        cascade="all, delete-orphan",
        order_by="ProgramOutcomeVersion.version_number",
        lazy="selectin",
    )


class ProgramOutcomeVersion(Base):
    __tablename__ = "program_outcome_versions"
    __table_args__ = (
        UniqueConstraint(
            "program_outcome_id", "version_number", name="uq_program_outcome_versions"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    program_outcome_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("program_outcomes.id", ondelete="CASCADE"),
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    effective_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=OutcomeVersionStatus.DRAFT.value
    )
    review_comments: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    program_outcome: Mapped[ProgramOutcome] = relationship(back_populates="versions")


class ProgramEducationalObjective(Base):
    __tablename__ = "program_educational_objectives"
    __table_args__ = (UniqueConstraint("program_id", "peo_code", name="uq_peos_code"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    program_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("programs.id"), nullable=False)
    peo_code: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=OutcomeStatus.ACTIVE.value
    )
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    program: Mapped[Program] = relationship(lazy="joined")
    versions: Mapped[list["PeoVersion"]] = relationship(
        back_populates="program_educational_objective",
        cascade="all, delete-orphan",
        order_by="PeoVersion.version_number",
        lazy="selectin",
    )


class PeoVersion(Base):
    __tablename__ = "peo_versions"
    __table_args__ = (UniqueConstraint("peo_id", "version_number", name="uq_peo_versions"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    peo_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("program_educational_objectives.id", ondelete="CASCADE"),
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    effective_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=OutcomeVersionStatus.DRAFT.value
    )
    review_comments: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    program_educational_objective: Mapped[ProgramEducationalObjective] = relationship(
        back_populates="versions"
    )
