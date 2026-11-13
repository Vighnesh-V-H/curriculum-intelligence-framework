import uuid

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_current_user, get_verification_reference_service, require_roles
from app.db.models.user import RoleCode, User
from app.schemas.verification_reference import (
    ReferenceTypeValue,
    VerificationReferenceCreate,
    VerificationReferenceResponse,
    VerificationReferenceUpdate,
)
from app.services.verification_references import VerificationReferenceService

router = APIRouter(prefix="/verification-references", tags=["curriculum-verification"])

REFERENCE_WRITE_ROLES = (RoleCode.ADMIN, RoleCode.COMMITTEE_MEMBER)


@router.get("", response_model=list[VerificationReferenceResponse])
def list_verification_references(
    program_id: uuid.UUID | None = Query(default=None),
    reference_type: ReferenceTypeValue | None = Query(default=None),
    include_inactive: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    service: VerificationReferenceService = Depends(get_verification_reference_service),
) -> list[VerificationReferenceResponse]:
    return service.list_references(program_id, reference_type, include_inactive)


@router.post(
    "",
    response_model=VerificationReferenceResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_verification_reference(
    payload: VerificationReferenceCreate,
    actor: User = Depends(require_roles(*REFERENCE_WRITE_ROLES)),
    service: VerificationReferenceService = Depends(get_verification_reference_service),
) -> VerificationReferenceResponse:
    return service.create_reference(actor.id, payload)


@router.patch("/{reference_id}", response_model=VerificationReferenceResponse)
def update_verification_reference(
    reference_id: uuid.UUID,
    payload: VerificationReferenceUpdate,
    actor: User = Depends(require_roles(*REFERENCE_WRITE_ROLES)),
    service: VerificationReferenceService = Depends(get_verification_reference_service),
) -> VerificationReferenceResponse:
    return service.update_reference(actor.id, reference_id, payload)
