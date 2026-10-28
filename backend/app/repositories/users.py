import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.db.models.user import User, UserRole


class UserRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    @staticmethod
    def _with_roles():
        return selectinload(User.role_assignments).selectinload(UserRole.role)

    def get_by_id(self, user_id: uuid.UUID) -> User | None:
        statement = select(User).where(User.id == user_id).options(self._with_roles())
        return self._session.scalars(statement).first()

    def get_by_username(self, username: str) -> User | None:
        statement = (
            select(User)
            .where(func.lower(User.username) == username.strip().lower())
            .options(self._with_roles())
        )
        return self._session.scalars(statement).first()

    def get_by_identifier(self, identifier: str) -> User | None:
        normalized = identifier.strip().lower()
        statement = (
            select(User)
            .where(
                or_(
                    func.lower(User.username) == normalized,
                    func.lower(User.email) == normalized,
                )
            )
            .options(self._with_roles())
        )
        return self._session.scalars(statement).first()

    def exists_username(self, username: str) -> bool:
        statement = select(User.id).where(func.lower(User.username) == username.strip().lower())
        return self._session.scalars(statement).first() is not None

    def exists_email(self, email: str) -> bool:
        statement = select(User.id).where(func.lower(User.email) == email.strip().lower())
        return self._session.scalars(statement).first() is not None

    def list(self) -> list[User]:
        statement = select(User).options(self._with_roles()).order_by(User.created_at)
        return list(self._session.scalars(statement).all())

    def add(self, user: User) -> User:
        self._session.add(user)
        self._session.flush()
        return user

    def add_role_assignment(self, assignment: UserRole) -> None:
        self._session.add(assignment)

    def clear_roles(self, user: User) -> None:
        user.role_assignments.clear()
