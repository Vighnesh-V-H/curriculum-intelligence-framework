from fastapi import APIRouter

from app.api.v1 import (
    academic,
    auth,
    curricula,
    curriculum_drafts,
    documents,
    knowledge_graph,
    mappings,
    outcomes,
    prerequisites,
    users,
    verification,
    verification_references,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(academic.router)
api_router.include_router(curricula.router)
api_router.include_router(curriculum_drafts.router)
api_router.include_router(documents.router)
api_router.include_router(knowledge_graph.router)
api_router.include_router(outcomes.router)
api_router.include_router(mappings.router)
api_router.include_router(prerequisites.router)
api_router.include_router(verification.router)
api_router.include_router(verification.run_router)
api_router.include_router(verification.finding_router)
api_router.include_router(verification_references.router)
