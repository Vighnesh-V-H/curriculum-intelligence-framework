from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError, model_validator

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
    pos: list[DraftOutcomeDefinition]
    mappings: list[DraftMapping]

    @model_validator(mode="after")
    def validate_consistency(self) -> "CurriculumDraftResponse":
        semester_numbers = [semester.semester_number for semester in self.semesters]
        if semester_numbers != list(range(1, len(semester_numbers) + 1)):
            raise ValueError(
                "Semester numbers must be sequential positive integers "
                "starting at 1 without gaps"
            )

        course_outcomes: dict[str, set[str]] = {}
        for semester in self.semesters:
            for course in semester.courses:
                course_key = _normalize_code(course.code)
                if course_key in course_outcomes:
                    raise ValueError(
                        f"Course code '{course.code}' is duplicated across semesters"
                    )
                outcome_codes = {
                    _normalize_code(outcome.code) for outcome in course.outcomes
                }
                if not outcome_codes:
                    raise ValueError(
                        f"Course '{course.code}' must define at least one course outcome"
                    )
                if len(outcome_codes) != len(course.outcomes):
                    raise ValueError(
                        f"Course '{course.code}' has duplicated outcome codes"
                    )
                course_outcomes[course_key] = outcome_codes

        for label, definitions in (("PEO", self.peos), ("PO", self.pos)):
            codes = [_normalize_code(definition.code) for definition in definitions]
            if len(set(codes)) != len(codes):
                raise ValueError(f"{label} codes must be unique")

        po_codes = {_normalize_code(definition.code) for definition in self.pos}
        for mapping in self.mappings:
            course_key = _normalize_code(mapping.course_code)
            if course_key not in course_outcomes:
                raise ValueError(
                    f"Mapping references unknown course '{mapping.course_code}'"
                )
            if (
                _normalize_code(mapping.course_outcome_code)
                not in course_outcomes[course_key]
            ):
                raise ValueError(
                    f"Mapping references unknown course outcome "
                    f"'{mapping.course_outcome_code}' for course "
                    f"'{mapping.course_code}'"
                )
            if _normalize_code(mapping.program_outcome_code) not in po_codes:
                raise ValueError(
                    f"Mapping references unknown program outcome "
                    f"'{mapping.program_outcome_code}'"
                )
        return self

    @classmethod
    def from_llm_payload(cls, payload: dict[str, Any]) -> "CurriculumDraftResponse":
        try:
            return cls.model_validate(payload)
        except ValidationError as exc:
            raise BadRequestError(
                _draft_validation_message(exc), "invalid_draft"
            ) from exc


def _draft_validation_message(exc: ValidationError) -> str:
    error = exc.errors()[0]
    location = ".".join(str(part) for part in error.get("loc", ()))
    detail = str(error.get("msg", "invalid draft payload"))
    return (
        f"LLM draft payload is invalid: {detail} (at '{location}')"
    )[:_INVALID_DRAFT_MESSAGE_MAX_CHARS]
