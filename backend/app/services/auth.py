from sqlalchemy.orm import Session

from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.security import JwtService, PasswordService
from app.db.models.user import UserStatus, utc_now
from app.repositories.users import UserRepository
from app.schemas.auth import AuthResponse, LoginRequest
from app.schemas.user import UserResponse


class AuthService:
    def __init__(
        self,
        session: Session,
        users: UserRepository,
        passwords: PasswordService,
        tokens: JwtService,
    ) -> None:
        self._session = session
        self._users = users
        self._passwords = passwords
        self._tokens = tokens

    def login(self, request: LoginRequest) -> AuthResponse:
        user = self._users.get_by_identifier(request.username)
        if user is None:
            self._passwords.verify_dummy(request.password)
            raise UnauthorizedError("Invalid username or password", "invalid_credentials")
        if not self._passwords.verify(request.password, user.password_hash):
            raise UnauthorizedError("Invalid username or password", "invalid_credentials")
        if user.status != UserStatus.ACTIVE.value:
            raise ForbiddenError("User account is not active", "account_inactive")

        user.last_login_at = utc_now()
        self._session.commit()

        roles = sorted(assignment.role.code for assignment in user.role_assignments)
        access_token = self._tokens.create_access_token(user.id, user.username, roles)
        return AuthResponse(
            access_token=access_token,
            expires_in=self._tokens.expires_in_seconds,
            user=UserResponse.from_user(user),
        )
