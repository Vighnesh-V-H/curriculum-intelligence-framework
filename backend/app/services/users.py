import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import BadRequestError, ConflictError, NotFoundError
from app.core.security import PasswordService
from app.db.models.user import Role, RoleCode, User, UserRole, UserStatus
from app.repositories.roles import RoleRepository
from app.repositories.users import UserRepository
from app.schemas.user import CreateUserRequest, UserResponse


class UserService:
    def __init__(
        self,
        session: Session,
        users: UserRepository,
        roles: RoleRepository,
        passwords: PasswordService,
    ) -> None:
        self._session = session
        self._users = users
        self._roles = roles
        self._passwords = passwords

    def create_user(self, actor_id: uuid.UUID, request: CreateUserRequest) -> UserResponse:
        if self._users.exists_username(request.username):
            raise ConflictError("Username is already registered", "username_taken")
        if self._users.exists_email(str(request.email)):
            raise ConflictError("Email is already registered", "email_taken")

        role_models = self._resolve_roles(request.roles)
        user = User(
            username=request.username,
            email=str(request.email),
            password_hash=self._passwords.hash(request.password),
            full_name=request.full_name,
            status=UserStatus.ACTIVE.value,
        )
        try:
            self._users.add(user)
            for role in role_models:
                self._users.add_role_assignment(
                    UserRole(user_id=user.id, role_id=role.id, assigned_by=actor_id)
                )
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise ConflictError("Username or email is already registered", "user_conflict") from exc

        created = self._users.get_by_id(user.id)
        if created is None:
            raise NotFoundError("User could not be loaded after creation")
        return UserResponse.from_user(created)

    def list_users(self) -> list[UserResponse]:
        return [UserResponse.from_user(user) for user in self._users.list()]

    def get_user(self, user_id: uuid.UUID) -> UserResponse:
        user = self._users.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found")
        return UserResponse.from_user(user)

    def assign_roles(
        self, actor_id: uuid.UUID, user_id: uuid.UUID, roles: list[RoleCode]
    ) -> UserResponse:
        user = self._users.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found")

        role_models = self._resolve_roles(roles)
        user.role_assignments.clear()
        try:
            self._session.flush()
            for role in role_models:
                user.role_assignments.append(
                    UserRole(user_id=user.id, role_id=role.id, assigned_by=actor_id)
                )
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise ConflictError("Roles could not be assigned", "role_conflict") from exc

        self._session.expire_all()
        updated = self._users.get_by_id(user_id)
        if updated is None:
            raise NotFoundError("User not found")
        return UserResponse.from_user(updated)

    def update_status(
        self, actor_id: uuid.UUID, user_id: uuid.UUID, status: UserStatus
    ) -> UserResponse:
        user = self._users.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found")

        user.status = status.value
        self._session.commit()
        updated = self._users.get_by_id(user_id)
        if updated is None:
            raise NotFoundError("User not found")
        return UserResponse.from_user(updated)

    def _resolve_roles(self, codes: list[RoleCode]) -> list[Role]:
        unique_codes = {code.value for code in codes}
        role_models = self._roles.get_by_codes(sorted(unique_codes))
        missing = unique_codes - {role.code for role in role_models}
        if missing:
            raise BadRequestError(
                f"Unknown role code(s): {', '.join(sorted(missing))}", "invalid_role"
            )
        return role_models
