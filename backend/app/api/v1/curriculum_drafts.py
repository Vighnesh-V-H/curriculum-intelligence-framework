from fastapi import APIRouter, Depends, File, UploadFile

from app.api.deps import (
    get_curriculum_draft_persistence_service,
    get_curriculum_draft_service,
    get_curriculum_service,
    require_roles,
)
from app.api.v1.academic import CURRICULUM_WRITE_ROLES
from app.db.models.user import User
from app.schemas.curriculum import CurriculumDetailResponse
from app.schemas.curriculum_draft import CurriculumDraftResponse, CurriculumDraftSaveRequest
from app.services.curriculum import CurriculumService
from app.services.curriculum_draft import CurriculumDraftService
from app.services.curriculum_draft_persistence import CurriculumDraftPersistenceService

router = APIRouter(tags=["curriculum-drafts"])


@router.post("/curriculum-drafts", response_model=CurriculumDraftResponse)
def generate_curriculum_draft(
    actor: User = Depends(require_roles(*CURRICULUM_WRITE_ROLES)),
    files: list[UploadFile] = File(default=[]),
    service: CurriculumDraftService = Depends(get_curriculum_draft_service),
) -> CurriculumDraftResponse:
    return service.generate(actor, files)


@router.post(
    "/curriculum-drafts/save",
    response_model=CurriculumDetailResponse,
    status_code=201,
)
def save_curriculum_draft(
    payload: CurriculumDraftSaveRequest,
    actor: User = Depends(require_roles(*CURRICULUM_WRITE_ROLES)),
    persistence: CurriculumDraftPersistenceService = Depends(
        get_curriculum_draft_persistence_service
    ),
    curricula: CurriculumService = Depends(get_curriculum_service),
) -> CurriculumDetailResponse:
    curriculum_id = persistence.save(actor, payload)
    return curricula.get_curriculum(curriculum_id)
