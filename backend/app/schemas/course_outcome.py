import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.db.models.academic import CourseOutcome

CO_CODE_PATTERN = r"^[A-Za-z0-9 ._-]+$"


class CourseOutcomeCreate(BaseModel):
    co_code: str = Field(min_length=1, max_length=30, pattern=CO_CODE_PATTERN)
    description: str = Field(min_length=1)

    @field_validator("co_code")
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


class CourseOutcomeUpdate(BaseModel):
    co_code: str | None = Field(default=None, max_length=30, pattern=CO_CODE_PATTERN)
    description: str | None = None

    @field_validator("co_code")
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


class CourseOutcomeResponse(BaseModel):
    id: uuid.UUID
    course_id: uuid.UUID
    curriculum_version_id: uuid.UUID
    co_code: str
    description: str
    status: str
    created_by: uuid.UUID
    updated_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, outcome: CourseOutcome) -> "CourseOutcomeResponse":
        return cls(
            id=outcome.id,
            course_id=outcome.course_id,
            curriculum_version_id=outcome.curriculum_version_id,
            co_code=outcome.co_code,
            description=outcome.description,
            status=outcome.status,
            created_by=outcome.created_by,
            updated_by=outcome.updated_by,
            created_at=outcome.created_at,
            updated_at=outcome.updated_at,
        )
