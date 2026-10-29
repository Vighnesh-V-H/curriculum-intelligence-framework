import uuid

from fastapi import APIRouter, Depends, status

from app.api.deps import get_current_user, get_outcome_service, require_roles
from app.db.models.user import RoleCode, User
from app.schemas.outcomes import (
    OutcomeStatusUpdate,
    OutcomeVersionResponse,
    OutcomeVersionStatusUpdate,
    ProgramEducationalObjectiveCreate,
    ProgramEducationalObjectiveResponse,
    ProgramEducationalObjectiveUpdate,
    ProgramOutcomeCreate,
    ProgramOutcomeResponse,
    ProgramOutcomeUpdate,
)
from app.services.outcomes import OutcomeService

router = APIRouter(tags=["program-outcomes"])

OUTCOME_WRITE_ROLES = (RoleCode.ADMIN, RoleCode.COMMITTEE_MEMBER)


@router.post(
    "/programs/{program_id}/program-outcomes",
    response_model=ProgramOutcomeResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_program_outcome(
    program_id: uuid.UUID,
    payload: ProgramOutcomeCreate,
    actor: User = Depends(require_roles(*OUTCOME_WRITE_ROLES)),
    service: OutcomeService = Depends(get_outcome_service),
) -> ProgramOutcomeResponse:
    return service.create_program_outcome(actor.id, program_id, payload)


@router.get(
    "/programs/{program_id}/program-outcomes",
    response_model=list[ProgramOutcomeResponse],
)
def list_program_outcomes(
    program_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: OutcomeService = Depends(get_outcome_service),
) -> list[ProgramOutcomeResponse]:
    return service.list_program_outcomes(program_id)


@router.get(
    "/program-outcomes/{outcome_id}",
    response_model=ProgramOutcomeResponse,
)
def get_program_outcome(
    outcome_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: OutcomeService = Depends(get_outcome_service),
) -> ProgramOutcomeResponse:
    return service.get_program_outcome(outcome_id)


@router.patch(
    "/program-outcomes/{outcome_id}",
    response_model=ProgramOutcomeResponse,
)
def update_program_outcome(
    outcome_id: uuid.UUID,
    payload: ProgramOutcomeUpdate,
    actor: User = Depends(require_roles(*OUTCOME_WRITE_ROLES)),
    service: OutcomeService = Depends(get_outcome_service),
) -> ProgramOutcomeResponse:
    return service.update_program_outcome(actor.id, outcome_id, payload)


@router.patch(
    "/program-outcomes/{outcome_id}/status",
    response_model=ProgramOutcomeResponse,
)
def update_program_outcome_status(
    outcome_id: uuid.UUID,
    payload: OutcomeStatusUpdate,
    actor: User = Depends(require_roles(*OUTCOME_WRITE_ROLES)),
    service: OutcomeService = Depends(get_outcome_service),
) -> ProgramOutcomeResponse:
    return service.update_program_outcome_status(actor.id, outcome_id, payload)


@router.get(
    "/program-outcomes/{outcome_id}/versions",
    response_model=list[OutcomeVersionResponse],
)
def list_program_outcome_versions(
    outcome_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: OutcomeService = Depends(get_outcome_service),
) -> list[OutcomeVersionResponse]:
    return service.list_program_outcome_versions(outcome_id)


@router.patch(
    "/program-outcomes/{outcome_id}/versions/{version_id}/status",
    response_model=OutcomeVersionResponse,
)
def update_program_outcome_version_status(
    outcome_id: uuid.UUID,
    version_id: uuid.UUID,
    payload: OutcomeVersionStatusUpdate,
    actor: User = Depends(require_roles(*OUTCOME_WRITE_ROLES)),
    service: OutcomeService = Depends(get_outcome_service),
) -> OutcomeVersionResponse:
    return service.update_program_outcome_version_status(actor.id, outcome_id, version_id, payload)


@router.post(
    "/programs/{program_id}/peos",
    response_model=ProgramEducationalObjectiveResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_peo(
    program_id: uuid.UUID,
    payload: ProgramEducationalObjectiveCreate,
    actor: User = Depends(require_roles(*OUTCOME_WRITE_ROLES)),
    service: OutcomeService = Depends(get_outcome_service),
) -> ProgramEducationalObjectiveResponse:
    return service.create_peo(actor.id, program_id, payload)


@router.get(
    "/programs/{program_id}/peos",
    response_model=list[ProgramEducationalObjectiveResponse],
)
def list_peos(
    program_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: OutcomeService = Depends(get_outcome_service),
) -> list[ProgramEducationalObjectiveResponse]:
    return service.list_peos(program_id)


@router.get(
    "/peos/{peo_id}",
    response_model=ProgramEducationalObjectiveResponse,
)
def get_peo(
    peo_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: OutcomeService = Depends(get_outcome_service),
) -> ProgramEducationalObjectiveResponse:
    return service.get_peo(peo_id)


@router.patch(
    "/peos/{peo_id}",
    response_model=ProgramEducationalObjectiveResponse,
)
def update_peo(
    peo_id: uuid.UUID,
    payload: ProgramEducationalObjectiveUpdate,
    actor: User = Depends(require_roles(*OUTCOME_WRITE_ROLES)),
    service: OutcomeService = Depends(get_outcome_service),
) -> ProgramEducationalObjectiveResponse:
    return service.update_peo(actor.id, peo_id, payload)


@router.patch(
    "/peos/{peo_id}/status",
    response_model=ProgramEducationalObjectiveResponse,
)
def update_peo_status(
    peo_id: uuid.UUID,
    payload: OutcomeStatusUpdate,
    actor: User = Depends(require_roles(*OUTCOME_WRITE_ROLES)),
    service: OutcomeService = Depends(get_outcome_service),
) -> ProgramEducationalObjectiveResponse:
    return service.update_peo_status(actor.id, peo_id, payload)


@router.get(
    "/peos/{peo_id}/versions",
    response_model=list[OutcomeVersionResponse],
)
def list_peo_versions(
    peo_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: OutcomeService = Depends(get_outcome_service),
) -> list[OutcomeVersionResponse]:
    return service.list_peo_versions(peo_id)


@router.patch(
    "/peos/{peo_id}/versions/{version_id}/status",
    response_model=OutcomeVersionResponse,
)
def update_peo_version_status(
    peo_id: uuid.UUID,
    version_id: uuid.UUID,
    payload: OutcomeVersionStatusUpdate,
    actor: User = Depends(require_roles(*OUTCOME_WRITE_ROLES)),
    service: OutcomeService = Depends(get_outcome_service),
) -> OutcomeVersionResponse:
    return service.update_peo_version_status(actor.id, peo_id, version_id, payload)
