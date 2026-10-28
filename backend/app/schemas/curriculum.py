import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from app.db.models.academic import (
    Curriculum,
    CurriculumVersion,
    Semester,
    VersionStatus,
)
from app.schemas.academic import SemesterCreate, SemesterResponse
from app.schemas.course import CourseCreate, CourseResponse


class CurriculumCreate(BaseModel):
    program_id: uuid.UUID
    academic_year: str = Field(min_length=1, max_length=20)
    regulation: str = Field(min_length=1, max_length=50)
    title: str | None = Field(default=None, max_length=200)
    duration_years: float = Field(gt=0, le=10)
    semesters: list[SemesterCreate] = Field(min_length=1)
    courses: list[CourseCreate] = Field(default_factory=list)

    @field_validator("academic_year", "regulation")
    @classmethod
    def normalize_short_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @model_validator(mode="after")
    def validate_structure(self) -> "CurriculumCreate":
        semester_numbers = [semester.semester_number for semester in self.semesters]
        if len(set(semester_numbers)) != len(semester_numbers):
            raise ValueError("Semester numbers must be unique")
        course_codes = [course.course_code for course in self.courses]
        if len(set(course_codes)) != len(course_codes):
            raise ValueError("Course codes must be unique within a curriculum version")
        unknown_semesters = {
            course.semester_number
            for course in self.courses
            if course.semester_number not in set(semester_numbers)
        }
        if unknown_semesters:
            raise ValueError(
                "Courses reference semesters that are not defined: "
                + ", ".join(str(number) for number in sorted(unknown_semesters))
            )
        return self


class CurriculumUpdate(BaseModel):
    academic_year: str | None = Field(default=None, min_length=1, max_length=20)
    regulation: str | None = Field(default=None, min_length=1, max_length=50)
    title: str | None = Field(default=None, max_length=200)
    duration_years: float | None = Field(default=None, gt=0, le=10)

    @field_validator("academic_year", "regulation")
    @classmethod
    def normalize_short_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class CurriculumVersionSummary(BaseModel):
    id: uuid.UUID
    version_label: str
    status: str
    previous_version_id: uuid.UUID | None
    created_at: datetime
    published_at: datetime | None

    @classmethod
    def from_model(cls, version: CurriculumVersion) -> "CurriculumVersionSummary":
        return cls(
            id=version.id,
            version_label=version.version_label,
            status=version.status,
            previous_version_id=version.previous_version_id,
            created_at=version.created_at,
            published_at=version.published_at,
        )


class CurriculumResponse(BaseModel):
    id: uuid.UUID
    program_id: uuid.UUID
    program_code: str
    program_name: str
    academic_year: str
    regulation: str
    title: str | None
    duration_years: float
    status: str
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime
    latest_version: CurriculumVersionSummary | None

    @classmethod
    def from_model(
        cls,
        curriculum: Curriculum,
        latest_version: CurriculumVersion | None,
    ) -> "CurriculumResponse":
        return cls(
            id=curriculum.id,
            program_id=curriculum.program_id,
            program_code=curriculum.program.code,
            program_name=curriculum.program.name,
            academic_year=curriculum.academic_year,
            regulation=curriculum.regulation,
            title=curriculum.title,
            duration_years=float(curriculum.duration_years),
            status=curriculum.status,
            created_by=curriculum.created_by,
            created_at=curriculum.created_at,
            updated_at=curriculum.updated_at,
            latest_version=(
                CurriculumVersionSummary.from_model(latest_version)
                if latest_version is not None
                else None
            ),
        )


def semester_response(semester: Semester) -> SemesterResponse:
    return SemesterResponse(
        id=semester.id,
        semester_number=semester.semester_number,
        name=semester.name,
    )


class CurriculumVersionResponse(BaseModel):
    id: uuid.UUID
    curriculum_id: uuid.UUID
    version_label: str
    status: str
    previous_version_id: uuid.UUID | None
    change_summary: str | None
    created_by: uuid.UUID
    published_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    published_at: datetime | None
    semesters: list[SemesterResponse]
    courses: list[CourseResponse]

    @classmethod
    def from_model(cls, version: CurriculumVersion) -> "CurriculumVersionResponse":
        return cls(
            id=version.id,
            curriculum_id=version.curriculum_id,
            version_label=version.version_label,
            status=version.status,
            previous_version_id=version.previous_version_id,
            change_summary=version.change_summary,
            created_by=version.created_by,
            published_by=version.published_by,
            created_at=version.created_at,
            updated_at=version.updated_at,
            published_at=version.published_at,
            semesters=[
                semester_response(semester)
                for semester in sorted(version.semesters, key=lambda item: item.semester_number)
            ],
            courses=[
                CourseResponse.from_model(course)
                for course in sorted(
                    (course for course in version.courses if course.status == "ACTIVE"),
                    key=lambda item: item.course_code,
                )
            ],
        )


class CurriculumDetailResponse(CurriculumResponse):
    versions: list[CurriculumVersionResponse]

    @classmethod
    def from_curriculum(
        cls,
        curriculum: Curriculum,
        versions: list[CurriculumVersion],
    ) -> "CurriculumDetailResponse":
        latest = versions[-1] if versions else None
        base = CurriculumResponse.from_model(curriculum, latest)
        return cls(
            **base.model_dump(),
            versions=[CurriculumVersionResponse.from_model(version) for version in versions],
        )


class VersionCreateRequest(BaseModel):
    version_label: str | None = Field(default=None, max_length=20, pattern=r"^\d+\.\d+$")
    change_summary: str | None = Field(default=None, max_length=2000)

    @field_validator("change_summary")
    @classmethod
    def normalize_summary(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class VersionStatusUpdateRequest(BaseModel):
    status: VersionStatus


class FieldChange(BaseModel):
    before: Any = None
    after: Any = None


class ModifiedCourse(BaseModel):
    course_code: str
    course_name: str
    changes: dict[str, FieldChange]


class VersionComparisonResponse(BaseModel):
    curriculum_id: uuid.UUID
    base_version: CurriculumVersionSummary
    target_version: CurriculumVersionSummary
    added_courses: list[CourseResponse]
    removed_courses: list[CourseResponse]
    modified_courses: list[ModifiedCourse]
