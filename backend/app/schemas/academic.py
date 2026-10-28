import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.db.models.academic import CourseType, Department, Program


class DepartmentCreate(BaseModel):
    code: str = Field(min_length=1, max_length=20, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=200)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return value.strip()


class DepartmentResponse(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    status: str
    created_at: datetime

    @classmethod
    def from_model(cls, department: Department) -> "DepartmentResponse":
        return cls(
            id=department.id,
            code=department.code,
            name=department.name,
            status=department.status,
            created_at=department.created_at,
        )


class ProgramCreate(BaseModel):
    department_id: uuid.UUID
    code: str = Field(min_length=1, max_length=20, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=200)
    degree_type: str | None = Field(default=None, max_length=50)
    duration_years: float = Field(gt=0, le=10)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("degree_type")
    @classmethod
    def normalize_degree_type(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class ProgramResponse(BaseModel):
    id: uuid.UUID
    department_id: uuid.UUID
    department_code: str
    department_name: str
    code: str
    name: str
    degree_type: str | None
    duration_years: float
    status: str
    created_at: datetime

    @classmethod
    def from_model(cls, program: Program) -> "ProgramResponse":
        return cls(
            id=program.id,
            department_id=program.department_id,
            department_code=program.department.code,
            department_name=program.department.name,
            code=program.code,
            name=program.name,
            degree_type=program.degree_type,
            duration_years=float(program.duration_years),
            status=program.status,
            created_at=program.created_at,
        )


class CourseTypeResponse(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    description: str | None

    @classmethod
    def from_model(cls, course_type: CourseType) -> "CourseTypeResponse":
        return cls(
            id=course_type.id,
            code=course_type.code,
            name=course_type.name,
            description=course_type.description,
        )


class SemesterCreate(BaseModel):
    semester_number: int = Field(gt=0, le=30)
    name: str | None = Field(default=None, max_length=100)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class SemesterResponse(BaseModel):
    id: uuid.UUID
    semester_number: int
    name: str | None
