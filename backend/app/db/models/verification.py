import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.user import utc_now


class VerificationRunStatus(StrEnum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class FindingCategory(StrEnum):
    STRUCTURAL = "STRUCTURAL"
    OUTCOME = "OUTCOME"
    DEPENDENCY = "DEPENDENCY"
    CONTENT = "CONTENT"
    INDUSTRY_ALIGNMENT = "INDUSTRY_ALIGNMENT"
    ACCREDITATION_OBE = "ACCREDITATION_OBE"


class FindingSeverity(StrEnum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ReviewStatus(StrEnum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    MODIFIED = "MODIFIED"


class ReferenceEntityType(StrEnum):
    CURRICULUM_VERSION = "CURRICULUM_VERSION"
    SEMESTER = "SEMESTER"
    COURSE = "COURSE"
    COURSE_OUTCOME = "COURSE_OUTCOME"
    PROGRAM_OUTCOME = "PROGRAM_OUTCOME"
    PEO = "PEO"
    CO_PO_MAPPING = "CO_PO_MAPPING"
    PREREQUISITE = "PREREQUISITE"
    VERIFICATION_REFERENCE = "VERIFICATION_REFERENCE"


class VerificationReferenceType(StrEnum):
    OBE = "OBE"
    ACCREDITATION = "ACCREDITATION"
    INDUSTRY = "INDUSTRY"
    INSTITUTIONAL = "INSTITUTIONAL"


class VerificationReferenceStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class VerificationReference(Base):
    """Governed OBE, accreditation, industry, or institutional rules.

    A reference with no ``program_id`` applies institution-wide. A
    program-specific reference with the same type and code overrides the
    institution-wide reference for that program.
    """

    __tablename__ = "verification_references"
    __table_args__ = (
        UniqueConstraint(
            "program_id",
            "reference_type",
            "code",
            "version_label",
            name="uq_verification_references_scope",
        ),
        Index(
            "idx_verification_references_program",
            "program_id",
            "reference_type",
            "status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    program_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("programs.id", ondelete="CASCADE")
    )
    reference_type: Mapped[str] = mapped_column(String(30), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    source: Mapped[str] = mapped_column(String(300), nullable=False)
    version_label: Mapped[str] = mapped_column(String(50), nullable=False, default="1.0")
    effective_date: Mapped[date | None] = mapped_column(Date)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="MEDIUM")
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=VerificationReferenceStatus.ACTIVE.value
    )
    rules: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class VerificationRun(Base):
    __tablename__ = "verification_runs"
    __table_args__ = (Index("idx_verification_runs_version", "curriculum_version_id", "status"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    curriculum_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("curriculum_versions.id"),
        nullable=False,
    )
    requested_by: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=VerificationRunStatus.QUEUED.value
    )
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    findings: Mapped[list["VerificationFinding"]] = relationship(
        back_populates="verification_run",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class VerificationFinding(Base):
    __tablename__ = "verification_findings"
    __table_args__ = (
        Index(
            "idx_verification_findings_category",
            "category",
            "severity",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    verification_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("verification_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    evidence: Mapped[str | None] = mapped_column(Text)
    recommendation: Mapped[str | None] = mapped_column(Text)
    requires_human_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    review_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ReviewStatus.PENDING.value
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_comments: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    verification_run: Mapped[VerificationRun] = relationship(back_populates="findings")
    references: Mapped[list["VerificationFindingReference"]] = relationship(
        back_populates="finding",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class VerificationFindingReference(Base):
    __tablename__ = "verification_finding_references"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    finding_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("verification_findings.id", ondelete="CASCADE"),
        nullable=False,
    )
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    note: Mapped[str | None] = mapped_column(String(500))

    finding: Mapped[VerificationFinding] = relationship(back_populates="references")
