import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.verification import (
    VerificationFinding,
    VerificationRun,
)


class VerificationRunRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, run_id: uuid.UUID) -> VerificationRun | None:
        return self._session.get(VerificationRun, run_id)

    def list_by_version(self, curriculum_version_id: uuid.UUID) -> list[VerificationRun]:
        statement = (
            select(VerificationRun)
            .where(VerificationRun.curriculum_version_id == curriculum_version_id)
            .order_by(VerificationRun.requested_at.desc())
        )
        return list(self._session.scalars(statement))

    def add(self, run: VerificationRun) -> VerificationRun:
        self._session.add(run)
        self._session.flush()
        return run


class VerificationFindingRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, finding_id: uuid.UUID) -> VerificationFinding | None:
        return self._session.get(VerificationFinding, finding_id)

    def list_by_run(
        self,
        run_id: uuid.UUID,
        category: str | None = None,
        severity: str | None = None,
    ) -> list[VerificationFinding]:
        statement = select(VerificationFinding).where(
            VerificationFinding.verification_run_id == run_id
        )
        if category is not None:
            statement = statement.where(VerificationFinding.category == category)
        if severity is not None:
            statement = statement.where(VerificationFinding.severity == severity)
        statement = statement.order_by(
            VerificationFinding.created_at,
            VerificationFinding.id,
        )
        return list(self._session.scalars(statement))

    def add(self, finding: VerificationFinding) -> VerificationFinding:
        self._session.add(finding)
        self._session.flush()
        return finding
