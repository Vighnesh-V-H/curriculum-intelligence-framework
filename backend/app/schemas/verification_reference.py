from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.db.models.verification import (
    FindingSeverity,
    VerificationReference,
    VerificationReferenceStatus,
    VerificationReferenceType,
)

SeverityValue = Literal["INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL"]
ReferenceTypeValue = Literal["OBE", "ACCREDITATION", "INDUSTRY", "INSTITUTIONAL"]
ReferenceStatusValue = Literal["ACTIVE", "INACTIVE"]


class NumericRange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min: float | None = Field(default=None, ge=0)
    max: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_bounds(self) -> NumericRange:
        if self.min is not None and self.max is not None and self.min > self.max:
            raise ValueError("min must not be greater than max")
        return self


class InstitutionalRules(BaseModel):
    """Institutional credit, load, and distribution targets."""

    model_config = ConfigDict(extra="forbid")

    total_credits: NumericRange | None = None
    semester_credits: NumericRange | None = None
    semester_count: NumericRange | None = None
    course_type_credits: dict[str, NumericRange] = Field(default_factory=dict)
    course_type_share: dict[str, NumericRange] = Field(default_factory=dict)

    @field_validator("course_type_credits", "course_type_share", mode="before")
    @classmethod
    def normalize_course_types(cls, value: Any) -> Any:
        if isinstance(value, dict):
            return {str(key).strip().upper(): item for key, item in value.items()}
        return value


class ObeRules(BaseModel):
    """Outcome-based education coverage targets."""

    model_config = ConfigDict(extra="forbid")

    required_po_codes: list[str] = Field(default_factory=list)
    required_peo_codes: list[str] = Field(default_factory=list)
    min_po_coverage_ratio: float | None = Field(default=None, ge=0, le=1)
    min_approved_mapping_ratio: float | None = Field(default=None, ge=0, le=1)

    @field_validator("required_po_codes", "required_peo_codes")
    @classmethod
    def normalize_codes(cls, value: list[str]) -> list[str]:
        return sorted({item.strip().upper() for item in value if item.strip()})


class AccreditationRules(BaseModel):
    """Accreditation criterion requirements evaluated against curriculum evidence."""

    model_config = ConfigDict(extra="forbid")

    criterion: str = Field(min_length=1, max_length=300)
    required_po_codes: list[str] = Field(default_factory=list)
    required_course_types: list[str] = Field(default_factory=list)
    min_po_coverage_ratio: float | None = Field(default=None, ge=0, le=1)
    min_approved_mapping_ratio: float | None = Field(default=None, ge=0, le=1)

    @field_validator("required_po_codes", "required_course_types")
    @classmethod
    def normalize_codes(cls, value: list[str]) -> list[str]:
        return sorted({item.strip().upper() for item in value if item.strip()})

    @field_validator("criterion")
    @classmethod
    def normalize_criterion(cls, value: str) -> str:
        return value.strip()


class IndustrySkill(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=50)
    label: str = Field(min_length=1, max_length=200)
    keywords: list[str] = Field(min_length=1)
    required: bool = True
    min_courses: int = Field(default=1, ge=1, le=100)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("label")
    @classmethod
    def normalize_label(cls, value: str) -> str:
        return value.strip()

    @field_validator("keywords")
    @classmethod
    def normalize_keywords(cls, value: list[str]) -> list[str]:
        normalized = sorted({item.strip().lower() for item in value if item.strip()})
        if not normalized:
            raise ValueError("at least one non-blank keyword is required")
        return normalized


class IndustryRules(BaseModel):
    """Industry competency evidence targets."""

    model_config = ConfigDict(extra="forbid")

    skills: list[IndustrySkill] = Field(min_length=1)
    min_required_skill_coverage_ratio: float | None = Field(default=None, ge=0, le=1)


RULE_MODELS: dict[str, type[BaseModel]] = {
    VerificationReferenceType.INSTITUTIONAL.value: InstitutionalRules,
    VerificationReferenceType.OBE.value: ObeRules,
    VerificationReferenceType.ACCREDITATION.value: AccreditationRules,
    VerificationReferenceType.INDUSTRY.value: IndustryRules,
}


def validate_reference_rules(reference_type: str, rules: dict[str, Any]) -> dict[str, Any]:
    model = RULE_MODELS.get(reference_type)
    if model is None:
        raise ValueError(f"Unsupported verification reference type: {reference_type}")
    parsed = model.model_validate(rules)
    return parsed.model_dump(mode="json", exclude_none=True)


class VerificationReferenceCreate(BaseModel):
    program_id: uuid.UUID | None = None
    reference_type: ReferenceTypeValue
    code: str = Field(min_length=1, max_length=50, pattern=r"^[A-Za-z0-9_.-]+$")
    title: str = Field(min_length=1, max_length=200)
    source: str = Field(min_length=1, max_length=300)
    version_label: str = Field(default="1.0", min_length=1, max_length=50)
    effective_date: date | None = None
    severity: SeverityValue = FindingSeverity.MEDIUM.value
    rules: dict[str, Any]

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("title", "source", "version_label")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return value.strip()


class VerificationReferenceUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    source: str | None = Field(default=None, min_length=1, max_length=300)
    version_label: str | None = Field(default=None, min_length=1, max_length=50)
    effective_date: date | None = None
    severity: SeverityValue | None = None
    status: ReferenceStatusValue | None = None
    rules: dict[str, Any] | None = None

    @field_validator("title", "source", "version_label")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class VerificationReferenceResponse(BaseModel):
    id: uuid.UUID
    program_id: uuid.UUID | None
    reference_type: str
    code: str
    title: str
    source: str
    version_label: str
    effective_date: date | None
    severity: str
    status: str
    rules: dict[str, Any]
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, reference: VerificationReference) -> VerificationReferenceResponse:
        return cls(
            id=reference.id,
            program_id=reference.program_id,
            reference_type=reference.reference_type,
            code=reference.code,
            title=reference.title,
            source=reference.source,
            version_label=reference.version_label,
            effective_date=reference.effective_date,
            severity=reference.severity,
            status=reference.status,
            rules=reference.rules or {},
            created_by=reference.created_by,
            created_at=reference.created_at,
            updated_at=reference.updated_at,
        )


__all__ = [
    "AccreditationRules",
    "IndustryRules",
    "IndustrySkill",
    "InstitutionalRules",
    "NumericRange",
    "ObeRules",
    "VerificationReferenceCreate",
    "VerificationReferenceResponse",
    "VerificationReferenceStatus",
    "VerificationReferenceType",
    "VerificationReferenceUpdate",
    "validate_reference_rules",
]
