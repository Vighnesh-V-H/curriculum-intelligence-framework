from fastapi import APIRouter, Depends, File, UploadFile

from app.api.deps import get_curriculum_draft_service, require_roles
from app.api.v1.academic import CURRICULUM_WRITE_ROLES
from app.db.models.user import User
from app.schemas.curriculum_draft import CurriculumDraftResponse
from app.services.curriculum_draft import CurriculumDraftService

router = APIRouter(tags=["curriculum-drafts"])


@router.post("/curriculum-drafts", response_model=CurriculumDraftResponse)
def generate_curriculum_draft(
    actor: User = Depends(require_roles(*CURRICULUM_WRITE_ROLES)),
    files: list[UploadFile] = File(default=[]),
    service: CurriculumDraftService = Depends(get_curriculum_draft_service),
) -> CurriculumDraftResponse:
    return service.generate(actor, files)
