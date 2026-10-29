import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator

from app.db.models.outcomes import (
    OutcomeStatus,
    OutcomeVersionStatus,
    PeoVersion,
    ProgramEducationalObjective,
    ProgramOutcome,
    ProgramOutcomeVersion,
)

OUTCOME_CODE_PATTERN = r"^[A-Za-z0-9 ._-]+$"


class ProgramOutcomeCreate(BaseModel):
    po_code: str = Field(min_length=1, max_length=30, pattern=OUTCOME_CODE_PATTERN)
    description: str = Field(min_length=1)
    effective_date: date | None = None

    @field_validator("po_code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Description must not be blank")
        return normalized


class ProgramOutcomeUpdate(BaseModel):
    po_code: str | None = Field(default=None, max_length=30, pattern=OUTCOME_CODE_PATTERN)
    description: str | None = None
    effective_date: date | None = None

    @field_validator("po_code")
    @classmethod
    def normalize_code(cls, value: str | None) -> str | None:
        return value.strip().upper() if value is not None else None

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("Description must not be blank")
        return normalized


class ProgramEducationalObjectiveCreate(BaseModel):
    peo_code: str = Field(min_length=1, max_length=30, pattern=OUTCOME_CODE_PATTERN)
    description: str = Field(min_length=1)
    effective_date: date | None = None

    @field_validator("peo_code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Description must not be blank")
        return normalized


class ProgramEducationalObjectiveUpdate(BaseModel):
    peo_code: str | None = Field(default=None, max_length=30, pattern=OUTCOME_CODE_PATTERN)
    description: str | None = None
    effective_date: date | None = None

    @field_validator("peo_code")
    @classmethod
    def normalize_code(cls, value: str | None) -> str | None:
        return value.strip().upper() if value is not None else None

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("Description must not be blank")
        return normalized


class OutcomeStatusUpdate(BaseModel):
    status: OutcomeStatus


class OutcomeVersionStatusUpdate(BaseModel):
    status: OutcomeVersionStatus
    review_comments: str | None = Field(default=None, max_length=2000)

    @field_validator("review_comments")
    @classmethod
    def normalize_comments(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class OutcomeVersionResponse(BaseModel):
    id: uuid.UUID
    version_number: int
    description: str
    effective_date: date | None
    status: str
    review_comments: str | None
    created_by: uuid.UUID
    approved_by: uuid.UUID | None
    created_at: datetime
    approved_at: datetime | None

    @classmethod
    def from_model(cls, version: ProgramOutcomeVersion | PeoVersion) -> "OutcomeVersionResponse":
        return cls(
            id=version.id,
            version_number=version.version_number,
            description=version.description,
            effective_date=version.effective_date,
            status=version.status,
            review_comments=version.review_comments,
            created_by=version.created_by,
            approved_by=version.approved_by,
            created_at=version.created_at,
            approved_at=version.approved_at,
        )


def _current_version(
    versions: list[ProgramOutcomeVersion] | list[PeoVersion],
) -> OutcomeVersionResponse | None:
    if not versions:
        return None
    approved = next(
        (
            version
            for version in reversed(versions)
            if version.status == OutcomeVersionStatus.APPROVED.value
        ),
        None,
    )
    return OutcomeVersionResponse.from_model(approved or versions[-1])


class ProgramOutcomeResponse(BaseModel):
    id: uuid.UUID
    program_id: uuid.UUID
    program_code: str
    program_name: str
    po_code: str
    status: str
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime
    current_version: OutcomeVersionResponse | None
    versions: list[OutcomeVersionResponse]

    @classmethod
    def from_model(cls, outcome: ProgramOutcome) -> "ProgramOutcomeResponse":
        versions = sorted(outcome.versions, key=lambda item: item.version_number)
        return cls(
            id=outcome.id,
            program_id=outcome.program_id,
            program_code=outcome.program.code,
            program_name=outcome.program.name,
            po_code=outcome.po_code,
            status=outcome.status,
            created_by=outcome.created_by,
            created_at=outcome.created_at,
            updated_at=outcome.updated_at,
            current_version=_current_version(versions),
            versions=[OutcomeVersionResponse.from_model(version) for version in versions],
        )


class ProgramEducationalObjectiveResponse(BaseModel):
    id: uuid.UUID
    program_id: uuid.UUID
    program_code: str
    program_name: str
    peo_code: str
    status: str
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime
    current_version: OutcomeVersionResponse | None
    versions: list[OutcomeVersionResponse]

    @classmethod
    def from_model(
        cls, objective: ProgramEducationalObjective
    ) -> "ProgramEducationalObjectiveResponse":
        versions = sorted(objective.versions, key=lambda item: item.version_number)
        return cls(
            id=objective.id,
            program_id=objective.program_id,
            program_code=objective.program.code,
            program_name=objective.program.name,
            peo_code=objective.peo_code,
            status=objective.status,
            created_by=objective.created_by,
            created_at=objective.created_at,
            updated_at=objective.updated_at,
            current_version=_current_version(versions),
            versions=[OutcomeVersionResponse.from_model(version) for version in versions],
        )
