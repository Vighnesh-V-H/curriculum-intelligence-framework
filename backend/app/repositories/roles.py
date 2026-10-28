from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.user import Role


class RoleRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_code(self, code: str) -> Role | None:
        return self._session.scalars(select(Role).where(Role.code == code)).first()

    def get_by_codes(self, codes: list[str]) -> list[Role]:
        statement = select(Role).where(Role.code.in_(codes))
        return list(self._session.scalars(statement).all())

    def list(self) -> list[Role]:
        return list(self._session.scalars(select(Role).order_by(Role.code)).all())
