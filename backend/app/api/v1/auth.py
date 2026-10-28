from fastapi import APIRouter, Depends

from app.api.deps import get_auth_service, get_current_user
from app.db.models.user import User
from app.schemas.auth import AuthResponse, LoginRequest
from app.schemas.user import UserResponse
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=AuthResponse)
def login(
    payload: LoginRequest,
    service: AuthService = Depends(get_auth_service),
) -> AuthResponse:
    return service.login(payload)


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.from_user(current_user)
