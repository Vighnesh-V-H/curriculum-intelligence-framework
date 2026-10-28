import uuid

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import (
    get_current_user,
    get_curriculum_service,
    require_roles,
)
from app.api.v1.academic import CURRICULUM_WRITE_ROLES
from app.db.models.user import User
from app.schemas.course import CourseCreate, CourseResponse, CourseUpdate
from app.schemas.curriculum import (
    CurriculumCreate,
    CurriculumDetailResponse,
    CurriculumResponse,
    CurriculumUpdate,
    CurriculumVersionResponse,
    VersionComparisonResponse,
    VersionCreateRequest,
    VersionStatusUpdateRequest,
)
from app.services.curriculum import CurriculumService

router = APIRouter(prefix="/curricula", tags=["curricula"])


@router.post("", response_model=CurriculumDetailResponse, status_code=status.HTTP_201_CREATED)
def create_curriculum(
    payload: CurriculumCreate,
    actor: User = Depends(require_roles(*CURRICULUM_WRITE_ROLES)),
    service: CurriculumService = Depends(get_curriculum_service),
) -> CurriculumDetailResponse:
    return service.create_curriculum(actor.id, payload)


@router.get("", response_model=list[CurriculumResponse])
def list_curricula(
    current_user: User = Depends(get_current_user),
    service: CurriculumService = Depends(get_curriculum_service),
) -> list[CurriculumResponse]:
    return service.list_curricula()


@router.get("/{curriculum_id}", response_model=CurriculumDetailResponse)
def get_curriculum(
    curriculum_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: CurriculumService = Depends(get_curriculum_service),
) -> CurriculumDetailResponse:
    return service.get_curriculum(curriculum_id)


@router.patch("/{curriculum_id}", response_model=CurriculumDetailResponse)
def update_curriculum(
    curriculum_id: uuid.UUID,
    payload: CurriculumUpdate,
    actor: User = Depends(require_roles(*CURRICULUM_WRITE_ROLES)),
    service: CurriculumService = Depends(get_curriculum_service),
) -> CurriculumDetailResponse:
    return service.update_curriculum(actor.id, curriculum_id, payload)


@router.get("/{curriculum_id}/versions", response_model=list[CurriculumVersionResponse])
def list_curriculum_versions(
    curriculum_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: CurriculumService = Depends(get_curriculum_service),
) -> list[CurriculumVersionResponse]:
    return service.list_versions(curriculum_id)


@router.post(
    "/{curriculum_id}/versions",
    response_model=CurriculumVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_curriculum_version(
    curriculum_id: uuid.UUID,
    payload: VersionCreateRequest,
    actor: User = Depends(require_roles(*CURRICULUM_WRITE_ROLES)),
    service: CurriculumService = Depends(get_curriculum_service),
) -> CurriculumVersionResponse:
    return service.create_version(actor.id, curriculum_id, payload)


@router.get(
    "/{curriculum_id}/versions/{version_id}",
    response_model=CurriculumVersionResponse,
)
def get_curriculum_version(
    curriculum_id: uuid.UUID,
    version_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: CurriculumService = Depends(get_curriculum_service),
) -> CurriculumVersionResponse:
    return service.get_version(curriculum_id, version_id)


@router.patch(
    "/{curriculum_id}/versions/{version_id}/status",
    response_model=CurriculumVersionResponse,
)
def update_curriculum_version_status(
    curriculum_id: uuid.UUID,
    version_id: uuid.UUID,
    payload: VersionStatusUpdateRequest,
    actor: User = Depends(require_roles(*CURRICULUM_WRITE_ROLES)),
    service: CurriculumService = Depends(get_curriculum_service),
) -> CurriculumVersionResponse:
    return service.update_version_status(actor.id, curriculum_id, version_id, payload)


@router.get(
    "/{curriculum_id}/compare",
    response_model=VersionComparisonResponse,
)
def compare_curriculum_versions(
    curriculum_id: uuid.UUID,
    base_version_id: uuid.UUID = Query(...),
    target_version_id: uuid.UUID = Query(...),
    current_user: User = Depends(get_current_user),
    service: CurriculumService = Depends(get_curriculum_service),
) -> VersionComparisonResponse:
    return service.compare_versions(curriculum_id, base_version_id, target_version_id)


@router.post(
    "/{curriculum_id}/versions/{version_id}/courses",
    response_model=CourseResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_course(
    curriculum_id: uuid.UUID,
    version_id: uuid.UUID,
    payload: CourseCreate,
    actor: User = Depends(require_roles(*CURRICULUM_WRITE_ROLES)),
    service: CurriculumService = Depends(get_curriculum_service),
) -> CourseResponse:
    return service.add_course(actor.id, curriculum_id, version_id, payload)


@router.patch(
    "/{curriculum_id}/versions/{version_id}/courses/{course_id}",
    response_model=CourseResponse,
)
def update_course(
    curriculum_id: uuid.UUID,
    version_id: uuid.UUID,
    course_id: uuid.UUID,
    payload: CourseUpdate,
    actor: User = Depends(require_roles(*CURRICULUM_WRITE_ROLES)),
    service: CurriculumService = Depends(get_curriculum_service),
) -> CourseResponse:
    return service.update_course(actor.id, curriculum_id, version_id, course_id, payload)
