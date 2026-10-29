import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator

from app.db.models.mappings import (
    CoPoMapping,
    CoPoMappingVersion,
    MappingLevel,
    MappingVersionStatus,
)


def _normalize_level_code(value: str) -> str:
    return value.strip().upper()


class MappingCreate(BaseModel):
    course_outcome_id: uuid.UUID
    program_outcome_id: uuid.UUID
    mapping_level_code: str = Field(min_length=1, max_length=20)
    effective_date: date | None = None

    @field_validator("mapping_level_code")
    @classmethod
    def normalize_level_code(cls, value: str) -> str:
        return _normalize_level_code(value)


class MappingUpdate(BaseModel):
    mapping_level_code: str | None = Field(default=None, max_length=20)
    effective_date: date | None = None

    @field_validator("mapping_level_code")
    @classmethod
    def normalize_level_code(cls, value: str | None) -> str | None:
        return _normalize_level_code(value) if value is not None else None


class MappingVersionStatusUpdate(BaseModel):
    status: MappingVersionStatus
    review_comments: str | None = Field(default=None, max_length=2000)

    @field_validator("review_comments")
    @classmethod
    def normalize_comments(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class MappingLevelResponse(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    numeric_value: int
    description: str | None
    sort_order: int

    @classmethod
    def from_model(cls, level: MappingLevel) -> "MappingLevelResponse":
        return cls(
            id=level.id,
            code=level.code,
            name=level.name,
            numeric_value=level.numeric_value,
            description=level.description,
            sort_order=level.sort_order,
        )


class MappingVersionResponse(BaseModel):
    id: uuid.UUID
    version_number: int
    mapping_level_code: str
    mapping_level_name: str
    numeric_value: int
    effective_date: date | None
    status: str
    review_comments: str | None
    created_by: uuid.UUID
    approved_by: uuid.UUID | None
    created_at: datetime
    approved_at: datetime | None

    @classmethod
    def from_model(cls, version: CoPoMappingVersion) -> "MappingVersionResponse":
        return cls(
            id=version.id,
            version_number=version.version_number,
            mapping_level_code=version.mapping_level.code,
            mapping_level_name=version.mapping_level.name,
            numeric_value=version.mapping_level.numeric_value,
            effective_date=version.effective_date,
            status=version.status,
            review_comments=version.review_comments,
            created_by=version.created_by,
            approved_by=version.approved_by,
            created_at=version.created_at,
            approved_at=version.approved_at,
        )


def _current_version(
    versions: list[CoPoMappingVersion],
) -> MappingVersionResponse | None:
    if not versions:
        return None
    approved = next(
        (
            version
            for version in reversed(versions)
            if version.status == MappingVersionStatus.APPROVED.value
        ),
        None,
    )
    return MappingVersionResponse.from_model(approved or versions[-1])


class MappingResponse(BaseModel):
    id: uuid.UUID
    curriculum_version_id: uuid.UUID
    course_outcome_id: uuid.UUID
    course_id: uuid.UUID
    course_code: str
    co_code: str
    program_outcome_id: uuid.UUID
    po_code: str
    status: str
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime
    current_version: MappingVersionResponse | None
    versions: list[MappingVersionResponse]

    @classmethod
    def from_model(cls, mapping: CoPoMapping) -> "MappingResponse":
        versions = sorted(mapping.versions, key=lambda item: item.version_number)
        return cls(
            id=mapping.id,
            curriculum_version_id=mapping.curriculum_version_id,
            course_outcome_id=mapping.course_outcome_id,
            course_id=mapping.course_outcome.course_id,
            course_code=mapping.course_outcome.course.course_code,
            co_code=mapping.course_outcome.co_code,
            program_outcome_id=mapping.program_outcome_id,
            po_code=mapping.program_outcome.po_code,
            status=mapping.status,
            created_by=mapping.created_by,
            created_at=mapping.created_at,
            updated_at=mapping.updated_at,
            current_version=_current_version(versions),
            versions=[MappingVersionResponse.from_model(version) for version in versions],
        )
