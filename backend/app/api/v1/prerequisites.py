import uuid

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_current_user, get_prerequisite_service, require_roles
from app.api.v1.academic import CURRICULUM_WRITE_ROLES
from app.db.models.user import RoleCode, User
from app.schemas.prerequisite import (
    PrerequisiteCreate,
    PrerequisiteResponse,
    PrerequisiteStatusUpdate,
)
from app.services.prerequisites import PrerequisiteService

PREREQUISITE_REVIEW_ROLES = (RoleCode.ADMIN, RoleCode.COMMITTEE_MEMBER)

router = APIRouter(
    prefix="/curricula/{curriculum_id}/versions/{version_id}/prerequisites",
    tags=["prerequisites"],
)


@router.get("", response_model=list[PrerequisiteResponse])
def list_prerequisites(
    curriculum_id: uuid.UUID,
    version_id: uuid.UUID,
    course_id: uuid.UUID | None = Query(default=None),
    direction: str = Query(default="both", pattern="^(both|incoming|outgoing)$"),
    current_user: User = Depends(get_current_user),
    service: PrerequisiteService = Depends(get_prerequisite_service),
) -> list[PrerequisiteResponse]:
    return service.list_prerequisites(curriculum_id, version_id, course_id, direction)


@router.post("", response_model=PrerequisiteResponse, status_code=status.HTTP_201_CREATED)
def create_prerequisite(
    curriculum_id: uuid.UUID,
    version_id: uuid.UUID,
    payload: PrerequisiteCreate,
    actor: User = Depends(require_roles(*CURRICULUM_WRITE_ROLES)),
    service: PrerequisiteService = Depends(get_prerequisite_service),
) -> PrerequisiteResponse:
    return service.create_prerequisite(actor.id, curriculum_id, version_id, payload)


@router.get("/{prerequisite_id}", response_model=PrerequisiteResponse)
def get_prerequisite(
    curriculum_id: uuid.UUID,
    version_id: uuid.UUID,
    prerequisite_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: PrerequisiteService = Depends(get_prerequisite_service),
) -> PrerequisiteResponse:
    return service.get_prerequisite(curriculum_id, version_id, prerequisite_id)


@router.patch("/{prerequisite_id}/status", response_model=PrerequisiteResponse)
def update_prerequisite_status(
    curriculum_id: uuid.UUID,
    version_id: uuid.UUID,
    prerequisite_id: uuid.UUID,
    payload: PrerequisiteStatusUpdate,
    actor: User = Depends(require_roles(*PREREQUISITE_REVIEW_ROLES)),
    service: PrerequisiteService = Depends(get_prerequisite_service),
) -> PrerequisiteResponse:
    return service.update_prerequisite_status(
        actor.id, curriculum_id, version_id, prerequisite_id, payload
    )


@router.delete("/{prerequisite_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_prerequisite(
    curriculum_id: uuid.UUID,
    version_id: uuid.UUID,
    prerequisite_id: uuid.UUID,
    actor: User = Depends(require_roles(*CURRICULUM_WRITE_ROLES)),
    service: PrerequisiteService = Depends(get_prerequisite_service),
) -> None:
    service.remove_prerequisite(actor.id, curriculum_id, version_id, prerequisite_id)
