from __future__ import annotations

import uuid

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models.verification import (
    VerificationReference,
    VerificationReferenceStatus,
)


class VerificationReferenceRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, reference_id: uuid.UUID) -> VerificationReference | None:
        return self._session.get(VerificationReference, reference_id)

    def list(
        self,
        program_id: uuid.UUID | None = None,
        reference_type: str | None = None,
        include_inactive: bool = False,
    ) -> list[VerificationReference]:
        statement = select(VerificationReference)
        if program_id is not None:
            statement = statement.where(
                or_(
                    VerificationReference.program_id == program_id,
                    VerificationReference.program_id.is_(None),
                )
            )
        if reference_type is not None:
            statement = statement.where(
                VerificationReference.reference_type == reference_type
            )
        if not include_inactive:
            statement = statement.where(
                VerificationReference.status == VerificationReferenceStatus.ACTIVE.value
            )
        statement = statement.order_by(
            VerificationReference.reference_type,
            VerificationReference.code,
            VerificationReference.version_label,
            VerificationReference.created_at,
        )
        return list(self._session.scalars(statement))

    def list_active_for_program(self, program_id: uuid.UUID) -> list[VerificationReference]:
        statement = (
            select(VerificationReference)
            .where(
                VerificationReference.status == VerificationReferenceStatus.ACTIVE.value,
                or_(
                    VerificationReference.program_id == program_id,
                    VerificationReference.program_id.is_(None),
                ),
            )
            .order_by(
                VerificationReference.reference_type,
                VerificationReference.code,
                VerificationReference.version_label,
            )
        )
        return list(self._session.scalars(statement))

    def find_duplicate(
        self,
        program_id: uuid.UUID | None,
        reference_type: str,
        code: str,
        version_label: str,
        exclude_id: uuid.UUID | None = None,
    ) -> VerificationReference | None:
        statement = select(VerificationReference).where(
            VerificationReference.reference_type == reference_type,
            VerificationReference.code == code,
            VerificationReference.version_label == version_label,
        )
        if program_id is None:
            statement = statement.where(VerificationReference.program_id.is_(None))
        else:
            statement = statement.where(VerificationReference.program_id == program_id)
        if exclude_id is not None:
            statement = statement.where(VerificationReference.id != exclude_id)
        return self._session.scalars(statement).first()

    def add(self, reference: VerificationReference) -> VerificationReference:
        self._session.add(reference)
        self._session.flush()
        return reference
