import uuid

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_current_user, get_mapping_service, require_roles
from app.api.v1.academic import CURRICULUM_WRITE_ROLES
from app.db.models.user import RoleCode, User
from app.schemas.mappings import (
    MappingCreate,
    MappingLevelResponse,
    MappingResponse,
    MappingUpdate,
    MappingVersionResponse,
    MappingVersionStatusUpdate,
)
from app.services.mappings import MappingService

MAPPING_REVIEW_ROLES = (RoleCode.ADMIN, RoleCode.COMMITTEE_MEMBER)

router = APIRouter(tags=["co-po-mappings"])


@router.get("/mapping-levels", response_model=list[MappingLevelResponse])
def list_mapping_levels(
    current_user: User = Depends(get_current_user),
    service: MappingService = Depends(get_mapping_service),
) -> list[MappingLevelResponse]:
    return service.list_mapping_levels()


@router.get(
    "/curricula/{curriculum_id}/versions/{version_id}/mappings",
    response_model=list[MappingResponse],
)
def list_mappings(
    curriculum_id: uuid.UUID,
    version_id: uuid.UUID,
    course_outcome_id: uuid.UUID | None = Query(default=None),
    program_outcome_id: uuid.UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    service: MappingService = Depends(get_mapping_service),
) -> list[MappingResponse]:
    return service.list_mappings(curriculum_id, version_id, course_outcome_id, program_outcome_id)


@router.post(
    "/curricula/{curriculum_id}/versions/{version_id}/mappings",
    response_model=MappingResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_mapping(
    curriculum_id: uuid.UUID,
    version_id: uuid.UUID,
    payload: MappingCreate,
    actor: User = Depends(require_roles(*CURRICULUM_WRITE_ROLES)),
    service: MappingService = Depends(get_mapping_service),
) -> MappingResponse:
    return service.create_mapping(actor.id, curriculum_id, version_id, payload)


@router.get("/mappings/{mapping_id}", response_model=MappingResponse)
def get_mapping(
    mapping_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: MappingService = Depends(get_mapping_service),
) -> MappingResponse:
    return service.get_mapping(mapping_id)


@router.patch("/mappings/{mapping_id}", response_model=MappingResponse)
def update_mapping(
    mapping_id: uuid.UUID,
    payload: MappingUpdate,
    actor: User = Depends(require_roles(*CURRICULUM_WRITE_ROLES)),
    service: MappingService = Depends(get_mapping_service),
) -> MappingResponse:
    return service.update_mapping(actor.id, mapping_id, payload)


@router.delete("/mappings/{mapping_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_mapping(
    mapping_id: uuid.UUID,
    actor: User = Depends(require_roles(*CURRICULUM_WRITE_ROLES)),
    service: MappingService = Depends(get_mapping_service),
) -> None:
    service.remove_mapping(actor.id, mapping_id)


@router.get(
    "/mappings/{mapping_id}/versions",
    response_model=list[MappingVersionResponse],
)
def list_mapping_versions(
    mapping_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: MappingService = Depends(get_mapping_service),
) -> list[MappingVersionResponse]:
    return service.list_mapping_versions(mapping_id)


@router.patch(
    "/mappings/{mapping_id}/versions/{version_id}/status",
    response_model=MappingVersionResponse,
)
def update_mapping_version_status(
    mapping_id: uuid.UUID,
    version_id: uuid.UUID,
    payload: MappingVersionStatusUpdate,
    actor: User = Depends(require_roles(*MAPPING_REVIEW_ROLES)),
    service: MappingService = Depends(get_mapping_service),
) -> MappingVersionResponse:
    return service.update_mapping_version_status(actor.id, mapping_id, version_id, payload)
