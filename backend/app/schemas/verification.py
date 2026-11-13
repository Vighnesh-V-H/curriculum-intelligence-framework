from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.db.models.verification import (
    ReviewStatus,
    VerificationFinding,
    VerificationFindingReference,
    VerificationRun,
)


class FindingReferenceResponse(BaseModel):
    id: uuid.UUID
    entity_type: str
    entity_id: uuid.UUID
    note: str | None

    @classmethod
    def from_model(cls, reference: VerificationFindingReference) -> FindingReferenceResponse:
        return cls(
            id=reference.id,
            entity_type=reference.entity_type,
            entity_id=reference.entity_id,
            note=reference.note,
        )


class FindingResponse(BaseModel):
    id: uuid.UUID
    verification_run_id: uuid.UUID
    category: str
    severity: str
    confidence: float | None
    title: str
    description: str | None
    evidence: str | None
    recommendation: str | None
    requires_human_review: bool
    review_status: str
    reviewed_by: uuid.UUID | None
    reviewed_at: datetime | None
    review_comments: str | None
    created_at: datetime
    references: list[FindingReferenceResponse]

    @classmethod
    def from_model(cls, finding: VerificationFinding) -> FindingResponse:
        return cls(
            id=finding.id,
            verification_run_id=finding.verification_run_id,
            category=finding.category,
            severity=finding.severity,
            confidence=(float(finding.confidence) if finding.confidence is not None else None),
            title=finding.title,
            description=finding.description,
            evidence=finding.evidence,
            recommendation=finding.recommendation,
            requires_human_review=finding.requires_human_review,
            review_status=finding.review_status,
            reviewed_by=finding.reviewed_by,
            reviewed_at=finding.reviewed_at,
            review_comments=finding.review_comments,
            created_at=finding.created_at,
            references=[
                FindingReferenceResponse.from_model(reference) for reference in finding.references
            ],
        )


class VerificationReportGroup(BaseModel):
    key: str
    count: int
    findings: list[FindingResponse]


class VerificationReportResponse(BaseModel):
    run: VerificationRunResponse
    total_findings: int
    groups: list[VerificationReportGroup]
    counts_by_category: dict[str, int]
    counts_by_severity: dict[str, int]
    counts_by_review_status: dict[str, int]


class FindingReviewRequest(BaseModel):
    review_status: Literal[
        ReviewStatus.ACCEPTED.value,
        ReviewStatus.REJECTED.value,
        ReviewStatus.MODIFIED.value,
    ]
    review_comments: str | None = Field(default=None, max_length=5000)


class VerificationRunResponse(BaseModel):
    id: uuid.UUID
    curriculum_version_id: uuid.UUID
    requested_by: uuid.UUID
    status: str
    requested_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None
    summary: dict[str, Any] | None
    input_fingerprint: str | None = None
    is_stale: bool = False

    @classmethod
    def from_model(
        cls,
        run: VerificationRun,
        *,
        is_stale: bool = False,
    ) -> VerificationRunResponse:
        summary = run.summary or {}
        fingerprint = summary.get("input_fingerprint")
        return cls(
            id=run.id,
            curriculum_version_id=run.curriculum_version_id,
            requested_by=run.requested_by,
            status=run.status,
            requested_at=run.requested_at,
            started_at=run.started_at,
            completed_at=run.completed_at,
            error_message=run.error_message,
            summary=run.summary,
            input_fingerprint=fingerprint if isinstance(fingerprint, str) else None,
            is_stale=is_stale,
        )
