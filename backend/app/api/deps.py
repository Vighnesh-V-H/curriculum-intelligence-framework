import uuid

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.security import (
    JwtService,
    PasswordService,
    TokenError,
    get_jwt_service,
    get_password_service,
)
from app.db.models.user import RoleCode, User, UserStatus
from app.db.session import get_db
from app.repositories.roles import RoleRepository
from app.repositories.users import UserRepository
from app.services.auth import AuthService
from app.services.users import UserService

bearer_scheme = HTTPBearer(auto_error=False)


def get_user_repository(session: Session = Depends(get_db)) -> UserRepository:
    return UserRepository(session)


def get_role_repository(session: Session = Depends(get_db)) -> RoleRepository:
    return RoleRepository(session)


def get_auth_service(
    session: Session = Depends(get_db),
    users: UserRepository = Depends(get_user_repository),
    passwords: PasswordService = Depends(get_password_service),
    tokens: JwtService = Depends(get_jwt_service),
) -> AuthService:
    return AuthService(session, users, passwords, tokens)


def get_user_service(
    session: Session = Depends(get_db),
    users: UserRepository = Depends(get_user_repository),
    roles: RoleRepository = Depends(get_role_repository),
    passwords: PasswordService = Depends(get_password_service),
) -> UserService:
    return UserService(session, users, roles, passwords)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    users: UserRepository = Depends(get_user_repository),
    tokens: JwtService = Depends(get_jwt_service),
) -> User:
    if credentials is None:
        raise UnauthorizedError("Bearer token required")

    try:
        payload = tokens.decode_token(credentials.credentials)
    except TokenError as exc:
        raise UnauthorizedError("Invalid or expired token", "invalid_token") from exc

    try:
        user_id = uuid.UUID(payload.get("sub", ""))
    except (TypeError, ValueError) as exc:
        raise UnauthorizedError("Invalid token subject", "invalid_token") from exc

    user = users.get_by_id(user_id)
    if user is None or user.status != UserStatus.ACTIVE.value:
        raise UnauthorizedError("User is not active", "invalid_token")
    return user


def require_roles(*codes: RoleCode):
    allowed = {code.value for code in codes}

    def dependency(current_user: User = Depends(get_current_user)) -> User:
        granted = {assignment.role.code for assignment in current_user.role_assignments}
        if not allowed.intersection(granted):
            raise ForbiddenError("You do not have permission to perform this action")
        return current_user

    return dependency
