import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.outcomes import (
    OutcomeVersionStatus,
    PeoVersion,
    ProgramEducationalObjective,
    ProgramOutcome,
    ProgramOutcomeVersion,
)


class OutcomeRepository:
    def __init__(
        self,
        session: Session,
        model: type[ProgramOutcome] | type[ProgramEducationalObjective],
        code_field: str,
    ) -> None:
        self._session = session
        self._model = model
        self._code_field = code_field

    def get_by_id(
        self, outcome_id: uuid.UUID
    ) -> ProgramOutcome | ProgramEducationalObjective | None:
        return self._session.get(self._model, outcome_id)

    def get_by_code(
        self, program_id: uuid.UUID, code: str
    ) -> ProgramOutcome | ProgramEducationalObjective | None:
        code_column = getattr(self._model, self._code_field)
        statement = select(self._model).where(
            self._model.program_id == program_id,
            func.upper(code_column) == code.strip().upper(),
        )
        return self._session.scalars(statement).first()

    def list_by_program(
        self, program_id: uuid.UUID
    ) -> list[ProgramOutcome | ProgramEducationalObjective]:
        code_column = getattr(self._model, self._code_field)
        statement = (
            select(self._model).where(self._model.program_id == program_id).order_by(code_column)
        )
        return list(self._session.scalars(statement))

    def add(
        self, outcome: ProgramOutcome | ProgramEducationalObjective
    ) -> ProgramOutcome | ProgramEducationalObjective:
        self._session.add(outcome)
        self._session.flush()
        return outcome


class OutcomeVersionRepository:
    def __init__(
        self,
        session: Session,
        model: type[ProgramOutcomeVersion] | type[PeoVersion],
        parent_field: str,
    ) -> None:
        self._session = session
        self._model = model
        self._parent_field = parent_field

    def get_by_id(self, version_id: uuid.UUID) -> ProgramOutcomeVersion | PeoVersion | None:
        return self._session.get(self._model, version_id)

    def list_by_parent(self, parent_id: uuid.UUID) -> list[ProgramOutcomeVersion | PeoVersion]:
        parent_column = getattr(self._model, self._parent_field)
        statement = (
            select(self._model)
            .where(parent_column == parent_id)
            .order_by(self._model.version_number)
        )
        return list(self._session.scalars(statement))

    def get_approved(self, parent_id: uuid.UUID) -> ProgramOutcomeVersion | PeoVersion | None:
        parent_column = getattr(self._model, self._parent_field)
        statement = select(self._model).where(
            parent_column == parent_id,
            self._model.status == OutcomeVersionStatus.APPROVED.value,
        )
        return self._session.scalars(statement).first()

    def next_version_number(self, parent_id: uuid.UUID) -> int:
        parent_column = getattr(self._model, self._parent_field)
        statement = select(func.max(self._model.version_number)).where(parent_column == parent_id)
        current = self._session.scalar(statement)
        return int(current or 0) + 1

    def add(self, version: ProgramOutcomeVersion | PeoVersion) -> Any:
        self._session.add(version)
        self._session.flush()
        return version
