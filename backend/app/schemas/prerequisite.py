import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator

from app.db.models.academic import (
    Course,
    CoursePrerequisite,
    PrerequisiteStatus,
)


def _normalize_comments(value: str | None) -> str | None:
    return value.strip() if value is not None else None


class PrerequisiteCreate(BaseModel):
    prerequisite_course_id: uuid.UUID
    target_course_id: uuid.UUID


class PrerequisiteStatusUpdate(BaseModel):
    status: PrerequisiteStatus
    review_comments: str | None = None

    @field_validator("review_comments")
    @classmethod
    def normalize_comments(cls, value: str | None) -> str | None:
        return _normalize_comments(value)


class PrerequisiteResponse(BaseModel):
    id: uuid.UUID
    curriculum_version_id: uuid.UUID
    prerequisite_course_id: uuid.UUID
    prerequisite_course_code: str
    target_course_id: uuid.UUID
    target_course_code: str
    status: str
    review_comments: str | None
    created_by: uuid.UUID
    approved_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    approved_at: datetime | None

    @classmethod
    def from_model(cls, prerequisite: CoursePrerequisite) -> "PrerequisiteResponse":
        prerequisite_course: Course = prerequisite.prerequisite_course
        target_course: Course = prerequisite.target_course
        return cls(
            id=prerequisite.id,
            curriculum_version_id=prerequisite.curriculum_version_id,
            prerequisite_course_id=prerequisite.prerequisite_course_id,
            prerequisite_course_code=prerequisite_course.course_code,
            target_course_id=prerequisite.target_course_id,
            target_course_code=target_course.course_code,
            status=prerequisite.status,
            review_comments=prerequisite.review_comments,
            created_by=prerequisite.created_by,
            approved_by=prerequisite.approved_by,
            created_at=prerequisite.created_at,
            updated_at=prerequisite.updated_at,
            approved_at=prerequisite.approved_at,
        )
