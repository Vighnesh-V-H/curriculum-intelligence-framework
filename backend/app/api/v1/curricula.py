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
from app.schemas.course_outcome import (
    CourseOutcomeCreate,
    CourseOutcomeResponse,
    CourseOutcomeUpdate,
)
from app.schemas.curriculum import (
    CurriculumCreate,
    CurriculumDetailResponse,
    CurriculumResponse,
    CurriculumUpdate,
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


@router.delete(
    "/{curriculum_id}/versions/{version_id}/courses/{course_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_course(
    curriculum_id: uuid.UUID,
    version_id: uuid.UUID,
    course_id: uuid.UUID,
    force: bool = Query(default=False),
    actor: User = Depends(require_roles(*CURRICULUM_WRITE_ROLES)),
    service: CurriculumService = Depends(get_curriculum_service),
) -> None:
    service.remove_course(actor.id, curriculum_id, version_id, course_id, force=force)


@router.get(
    "/{curriculum_id}/versions/{version_id}/courses/{course_id}/outcomes",
    response_model=list[CourseOutcomeResponse],
)
def list_course_outcomes(
    curriculum_id: uuid.UUID,
    version_id: uuid.UUID,
    course_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: CurriculumService = Depends(get_curriculum_service),
) -> list[CourseOutcomeResponse]:
    return service.list_course_outcomes(curriculum_id, version_id, course_id)


@router.post(
    "/{curriculum_id}/versions/{version_id}/courses/{course_id}/outcomes",
    response_model=CourseOutcomeResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_course_outcome(
    curriculum_id: uuid.UUID,
    version_id: uuid.UUID,
    course_id: uuid.UUID,
    payload: CourseOutcomeCreate,
    actor: User = Depends(require_roles(*CURRICULUM_WRITE_ROLES)),
    service: CurriculumService = Depends(get_curriculum_service),
) -> CourseOutcomeResponse:
    return service.add_course_outcome(actor.id, curriculum_id, version_id, course_id, payload)


@router.patch(
    "/{curriculum_id}/versions/{version_id}/courses/{course_id}/outcomes/{outcome_id}",
    response_model=CourseOutcomeResponse,
)
def update_course_outcome(
    curriculum_id: uuid.UUID,
    version_id: uuid.UUID,
    course_id: uuid.UUID,
    outcome_id: uuid.UUID,
    payload: CourseOutcomeUpdate,
    actor: User = Depends(require_roles(*CURRICULUM_WRITE_ROLES)),
    service: CurriculumService = Depends(get_curriculum_service),
) -> CourseOutcomeResponse:
    return service.update_course_outcome(
        actor.id, curriculum_id, version_id, course_id, outcome_id, payload
    )


@router.delete(
    "/{curriculum_id}/versions/{version_id}/courses/{course_id}/outcomes/{outcome_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_course_outcome(
    curriculum_id: uuid.UUID,
    version_id: uuid.UUID,
    course_id: uuid.UUID,
    outcome_id: uuid.UUID,
    actor: User = Depends(require_roles(*CURRICULUM_WRITE_ROLES)),
    service: CurriculumService = Depends(get_curriculum_service),
) -> None:
    service.remove_course_outcome(actor.id, curriculum_id, version_id, course_id, outcome_id)
