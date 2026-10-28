import uuid

from fastapi import APIRouter, Depends, status

from app.api.deps import get_user_service, require_roles
from app.db.models.user import RoleCode, User
from app.schemas.user import (
    AssignRolesRequest,
    CreateUserRequest,
    UpdateUserStatusRequest,
    UserResponse,
)
from app.services.users import UserService

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: CreateUserRequest,
    actor: User = Depends(require_roles(RoleCode.ADMIN)),
    service: UserService = Depends(get_user_service),
) -> UserResponse:
    return service.create_user(actor.id, payload)


@router.get("", response_model=list[UserResponse])
def list_users(
    actor: User = Depends(require_roles(RoleCode.ADMIN)),
    service: UserService = Depends(get_user_service),
) -> list[UserResponse]:
    return service.list_users()


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: uuid.UUID,
    actor: User = Depends(require_roles(RoleCode.ADMIN)),
    service: UserService = Depends(get_user_service),
) -> UserResponse:
    return service.get_user(user_id)


@router.put("/{user_id}/roles", response_model=UserResponse)
def assign_roles(
    user_id: uuid.UUID,
    payload: AssignRolesRequest,
    actor: User = Depends(require_roles(RoleCode.ADMIN)),
    service: UserService = Depends(get_user_service),
) -> UserResponse:
    return service.assign_roles(actor.id, user_id, payload.roles)


@router.patch("/{user_id}/status", response_model=UserResponse)
def update_status(
    user_id: uuid.UUID,
    payload: UpdateUserStatusRequest,
    actor: User = Depends(require_roles(RoleCode.ADMIN)),
    service: UserService = Depends(get_user_service),
) -> UserResponse:
    return service.update_status(actor.id, user_id, payload.status)
