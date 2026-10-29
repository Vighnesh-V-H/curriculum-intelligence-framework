import uuid

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import (
    get_current_user,
    get_verification_service,
    require_roles,
)
from app.db.models.user import RoleCode, User
from app.schemas.verification import (
    FindingResponse,
    VerificationRunResponse,
)
from app.services.verification import VerificationService

VERIFICATION_RUN_ROLES = (
    RoleCode.ADMIN,
    RoleCode.COMMITTEE_MEMBER,
    RoleCode.REVIEWER,
)

router = APIRouter(
    prefix="/curricula/{curriculum_id}/versions/{version_id}/verification-runs",
    tags=["prerequisite-verification"],
)


@router.post("", response_model=VerificationRunResponse, status_code=status.HTTP_201_CREATED)
def run_verification(
    curriculum_id: uuid.UUID,
    version_id: uuid.UUID,
    actor: User = Depends(require_roles(*VERIFICATION_RUN_ROLES)),
    service: VerificationService = Depends(get_verification_service),
) -> VerificationRunResponse:
    return service.run_verification(actor.id, curriculum_id, version_id)


@router.get("", response_model=list[VerificationRunResponse])
def list_verification_runs(
    curriculum_id: uuid.UUID,
    version_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: VerificationService = Depends(get_verification_service),
) -> list[VerificationRunResponse]:
    return service.list_runs(curriculum_id, version_id)


run_router = APIRouter(prefix="/verification-runs", tags=["prerequisite-verification"])


@run_router.get("/{run_id}", response_model=VerificationRunResponse)
def get_verification_run(
    run_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: VerificationService = Depends(get_verification_service),
) -> VerificationRunResponse:
    return service.get_run(run_id)


@run_router.get("/{run_id}/findings", response_model=list[FindingResponse])
def list_run_findings(
    run_id: uuid.UUID,
    category: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    service: VerificationService = Depends(get_verification_service),
) -> list[FindingResponse]:
    return service.list_findings(run_id, category, severity)


finding_router = APIRouter(prefix="/verification-findings", tags=["prerequisite-verification"])


@finding_router.get("/{finding_id}", response_model=FindingResponse)
def get_verification_finding(
    finding_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: VerificationService = Depends(get_verification_service),
) -> FindingResponse:
    return service.get_finding(finding_id)
