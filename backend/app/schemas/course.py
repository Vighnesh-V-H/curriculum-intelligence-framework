import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.db.models.academic import Course


class CourseCreate(BaseModel):
    course_code: str = Field(min_length=1, max_length=30, pattern=r"^[A-Za-z0-9 ._-]+$")
    course_name: str = Field(min_length=1, max_length=200)
    course_type_code: str = Field(min_length=1, max_length=30)
    credits: float = Field(gt=0, le=30)
    semester_number: int = Field(gt=0, le=30)
    contact_hours: int | None = Field(default=None, ge=0, le=1000)
    description: str | None = None
    syllabus: str | None = None

    @field_validator("course_code", "course_type_code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("course_name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return value.strip()


class CourseUpdate(BaseModel):
    course_name: str | None = Field(default=None, min_length=1, max_length=200)
    course_type_code: str | None = Field(default=None, min_length=1, max_length=30)
    credits: float | None = Field(default=None, gt=0, le=30)
    semester_number: int | None = Field(default=None, gt=0, le=30)
    contact_hours: int | None = Field(default=None, ge=0, le=1000)
    description: str | None = None
    syllabus: str | None = None

    @field_validator("course_type_code")
    @classmethod
    def normalize_code(cls, value: str | None) -> str | None:
        return value.strip().upper() if value is not None else None

    @field_validator("course_name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class CourseResponse(BaseModel):
    id: uuid.UUID
    curriculum_version_id: uuid.UUID
    course_code: str
    course_name: str
    course_type_code: str
    course_type_name: str
    credits: float
    semester_number: int
    contact_hours: int | None
    description: str | None
    syllabus: str | None
    status: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, course: Course) -> "CourseResponse":
        return cls(
            id=course.id,
            curriculum_version_id=course.curriculum_version_id,
            course_code=course.course_code,
            course_name=course.course_name,
            course_type_code=course.course_type.code,
            course_type_name=course.course_type.name,
            credits=float(course.credits),
            semester_number=course.semester.semester_number,
            contact_hours=course.contact_hours,
            description=course.description,
            syllabus=course.syllabus,
            status=course.status,
            created_at=course.created_at,
            updated_at=course.updated_at,
        )
