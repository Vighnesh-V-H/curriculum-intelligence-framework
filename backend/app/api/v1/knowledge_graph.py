import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query

from app.api.deps import (
    get_current_user,
    get_knowledge_graph_service,
    require_roles,
)
from app.api.v1.academic import CURRICULUM_WRITE_ROLES
from app.db.models.user import User
from app.services.knowledge_graph_projection import KnowledgeGraphProjectionService

router = APIRouter(prefix="/curricula", tags=["knowledge-graph"])


@router.post("/{curriculum_id}/versions/{version_id}/graph/rebuild")
def rebuild_curriculum_graph(
    curriculum_id: uuid.UUID,
    version_id: uuid.UUID,
    _actor: User = Depends(require_roles(*CURRICULUM_WRITE_ROLES)),
    service: KnowledgeGraphProjectionService = Depends(get_knowledge_graph_service),
) -> dict[str, Any]:
    return service.rebuild(curriculum_id, version_id)


@router.get("/{curriculum_id}/versions/{version_id}/graph")
def get_curriculum_graph(
    curriculum_id: uuid.UUID,
    version_id: uuid.UUID,
    limit: int = Query(default=1000, ge=1, le=5000),
    _current_user: User = Depends(get_current_user),
    service: KnowledgeGraphProjectionService = Depends(get_knowledge_graph_service),
) -> dict[str, Any]:
    return service.read(curriculum_id, version_id, limit=limit)
