from fastapi import APIRouter, Depends, status

from app.api.deps import get_auth_service, get_current_user, get_user_service
from app.db.models.user import User
from app.schemas.auth import AuthResponse, LoginRequest, RegisterRequest
from app.schemas.user import UserResponse
from app.services.auth import AuthService
from app.services.users import UserService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest,
    service: UserService = Depends(get_user_service),
) -> UserResponse:
    return service.register_user(payload)


@router.post("/login", response_model=AuthResponse)
def login(
    payload: LoginRequest,
    service: AuthService = Depends(get_auth_service),
) -> AuthResponse:
    return service.login(payload)


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.from_user(current_user)
