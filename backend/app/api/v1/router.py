from fastapi import APIRouter

from app.api.v1 import academic, auth, curricula, mappings, outcomes, prerequisites, users

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(academic.router)
api_router.include_router(curricula.router)
api_router.include_router(outcomes.router)
api_router.include_router(mappings.router)
api_router.include_router(prerequisites.router)
