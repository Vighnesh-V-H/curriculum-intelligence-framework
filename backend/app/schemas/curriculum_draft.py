import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from app.core.errors import BadRequestError

_INVALID_DRAFT_MESSAGE_MAX_CHARS = 200


def _normalize_code(value: str) -> str:
    return value.strip().upper()


class DraftOutcomeDefinition(BaseModel):
    code: str = Field(min_length=1)
    statement: str = Field(min_length=1)


class DraftCourse(BaseModel):
    code: str = Field(min_length=1)
    title: str = Field(min_length=1)
    credits: int | None = None
    category: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    outcomes: list[DraftOutcomeDefinition]


class DraftSemester(BaseModel):
    semester_number: int
    semester_name: str = Field(min_length=1)
    focus: str = Field(min_length=1)
    courses: list[DraftCourse]


class DraftProgram(BaseModel):
    name: str | None = None
    degree: str | None = None
    duration_years: int | None = None
    summary: str = Field(min_length=1)


class DraftMapping(BaseModel):
    course_code: str = Field(min_length=1)
    course_outcome_code: str = Field(min_length=1)
    program_outcome_code: str = Field(min_length=1)
    level: Literal[1, 2, 3]


class CurriculumDraftResponse(BaseModel):
    program: DraftProgram
    semesters: list[DraftSemester]
    peos: list[DraftOutcomeDefinition] = Field(min_length=1)
    pos: list[DraftOutcomeDefinition] = Field(min_length=1)
    mappings: list[DraftMapping] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_consistency(self) -> "CurriculumDraftResponse":
        if not self.semesters:
            raise ValueError("At least one semester is required")

        semester_numbers = [semester.semester_number for semester in self.semesters]
        if semester_numbers != list(range(1, len(semester_numbers) + 1)):
            raise ValueError(
                "Semester numbers must be sequential positive integers starting at 1 without gaps"
            )

        course_outcomes: dict[str, set[str]] = {}
        for semester in self.semesters:
            for course in semester.courses:
                course_key = _normalize_code(course.code)
                if course_key in course_outcomes:
                    raise ValueError(f"Course code '{course.code}' is duplicated across semesters")
                outcome_codes = {_normalize_code(outcome.code) for outcome in course.outcomes}
                if not outcome_codes:
                    raise ValueError(
                        f"Course '{course.code}' must define at least one course outcome"
                    )
                if len(outcome_codes) != len(course.outcomes):
                    raise ValueError(f"Course '{course.code}' has duplicated outcome codes")
                course_outcomes[course_key] = outcome_codes

        if not course_outcomes:
            raise ValueError("At least one course with course outcomes is required")

        for label, definitions in (("PEO", self.peos), ("PO", self.pos)):
            codes = [_normalize_code(definition.code) for definition in definitions]
            if len(set(codes)) != len(codes):
                raise ValueError(f"{label} codes must be unique")

        po_codes = {_normalize_code(definition.code) for definition in self.pos}
        mapped_course_outcomes: set[tuple[str, str]] = set()
        for mapping in self.mappings:
            course_key = _normalize_code(mapping.course_code)
            if course_key not in course_outcomes:
                raise ValueError(f"Mapping references unknown course '{mapping.course_code}'")
            if _normalize_code(mapping.course_outcome_code) not in course_outcomes[course_key]:
                raise ValueError(
                    f"Mapping references unknown course outcome "
                    f"'{mapping.course_outcome_code}' for course "
                    f"'{mapping.course_code}'"
                )
            if _normalize_code(mapping.program_outcome_code) not in po_codes:
                raise ValueError(
                    f"Mapping references unknown program outcome '{mapping.program_outcome_code}'"
                )
            mapped_course_outcomes.add((course_key, _normalize_code(mapping.course_outcome_code)))

        for course_code, outcome_codes in course_outcomes.items():
            for outcome_code in outcome_codes:
                if (course_code, outcome_code) not in mapped_course_outcomes:
                    raise ValueError(
                        f"Course outcome '{outcome_code}' for course "
                        f"'{course_code}' has no program outcome mapping"
                    )
        return self

    @classmethod
    def from_llm_payload(cls, payload: dict[str, Any]) -> "CurriculumDraftResponse":
        try:
            return cls.model_validate(payload)
        except ValidationError as exc:
            raise BadRequestError(_draft_validation_message(exc), "invalid_draft") from exc


class CurriculumDraftSaveRequest(BaseModel):
    program_id: uuid.UUID
    academic_year: str = Field(min_length=1, max_length=20)
    regulation: str = Field(min_length=1, max_length=50)
    title: str | None = Field(default=None, max_length=200)
    course_type_codes: dict[str, str] = Field(min_length=1)
    credits_by_course_code: dict[str, float] = Field(default_factory=dict)
    draft: CurriculumDraftResponse

    @field_validator("academic_year", "regulation")
    @classmethod
    def normalize_short_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @field_validator("course_type_codes")
    @classmethod
    def normalize_course_type_codes(cls, values: dict[str, str]) -> dict[str, str]:
        return {
            category.strip().casefold(): code.strip().upper() for category, code in values.items()
        }

    @model_validator(mode="after")
    def validate_category_mapping(self) -> "CurriculumDraftSaveRequest":
        categories = {
            course.category.strip().casefold()
            for semester in self.draft.semesters
            for course in semester.courses
        }
        missing = categories - self.course_type_codes.keys()
        if missing:
            raise ValueError("Select a course type for every generated category")
        credits = {
            code.strip().upper(): value for code, value in self.credits_by_course_code.items()
        }
        missing_credits = {
            course.code.strip().upper()
            for semester in self.draft.semesters
            for course in semester.courses
            if course.credits is None and course.code.strip().upper() not in credits
        }
        if missing_credits:
            raise ValueError("Enter credits for every generated course without a credit value")
        if any(value <= 0 or value > 30 for value in credits.values()):
            raise ValueError("Course credits must be greater than 0 and at most 30")
        self.credits_by_course_code = credits
        return self


def _draft_validation_message(exc: ValidationError) -> str:
    error = exc.errors()[0]
    location = ".".join(str(part) for part in error.get("loc", ()))
    detail = str(error.get("msg", "invalid draft payload"))
    return (f"LLM draft payload is invalid: {detail} (at '{location}')")[
        :_INVALID_DRAFT_MESSAGE_MAX_CHARS
    ]
