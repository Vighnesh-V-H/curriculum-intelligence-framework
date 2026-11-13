import uuid
from datetime import date
from typing import Any

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.errors import BadRequestError, ConflictError, NotFoundError
from app.db.models.audit import AuditLog
from app.db.models.verification import VerificationReference
from app.repositories.audit import AuditLogRepository
from app.repositories.verification_references import VerificationReferenceRepository
from app.schemas.verification_reference import (
    VerificationReferenceCreate,
    VerificationReferenceResponse,
    VerificationReferenceUpdate,
    validate_reference_rules,
)


def _validation_message(error: ValidationError) -> str:
    parts = []
    for item in error.errors():
        location = ".".join(str(part) for part in item.get("loc", ())) or "rules"
        parts.append(f"{location}: {item.get('msg', 'invalid value')}")
    return "; ".join(parts)


class VerificationReferenceService:
    def __init__(
        self,
        session: Session,
        references: VerificationReferenceRepository,
        audit_logs: AuditLogRepository,
    ) -> None:
        self._session = session
        self._references = references
        self._audit_logs = audit_logs

    def list_references(
        self,
        program_id: uuid.UUID | None = None,
        reference_type: str | None = None,
        include_inactive: bool = False,
    ) -> list[VerificationReferenceResponse]:
        return [
            VerificationReferenceResponse.from_model(reference)
            for reference in self._references.list(
                program_id, reference_type, include_inactive
            )
        ]

    def create_reference(
        self,
        actor_id: uuid.UUID,
        payload: VerificationReferenceCreate,
    ) -> VerificationReferenceResponse:
        rules = self._validate_rules(payload.reference_type, payload.rules)
        duplicate = self._references.find_duplicate(
            payload.program_id,
            payload.reference_type,
            payload.code,
            payload.version_label,
        )
        if duplicate is not None:
            raise ConflictError(
                "A verification reference with this scope, code, and version already exists",
                "verification_reference_exists",
            )

        reference = VerificationReference(
            program_id=payload.program_id,
            reference_type=payload.reference_type,
            code=payload.code,
            title=payload.title,
            source=payload.source,
            version_label=payload.version_label,
            effective_date=payload.effective_date,
            severity=payload.severity,
            rules=rules,
            created_by=actor_id,
        )
        self._references.add(reference)
        self._audit(
            actor_id,
            "CREATE",
            reference,
            new_values=self._audit_values(reference),
        )
        self._session.commit()
        self._session.refresh(reference)
        return VerificationReferenceResponse.from_model(reference)

    def update_reference(
        self,
        actor_id: uuid.UUID,
        reference_id: uuid.UUID,
        payload: VerificationReferenceUpdate,
    ) -> VerificationReferenceResponse:
        reference = self._references.get_by_id(reference_id)
        if reference is None:
            raise NotFoundError("Verification reference not found")

        data = payload.model_dump(exclude_unset=True)
        if "rules" in data:
            if data["rules"] is None:
                raise BadRequestError(
                    "Reference rules cannot be null",
                    "invalid_reference_rules",
                )
            data["rules"] = self._validate_rules(reference.reference_type, data["rules"])

        if "version_label" in data:
            duplicate = self._references.find_duplicate(
                reference.program_id,
                reference.reference_type,
                reference.code,
                data["version_label"],
                exclude_id=reference.id,
            )
            if duplicate is not None:
                raise ConflictError(
                    "A verification reference with this scope, code, and version already exists",
                    "verification_reference_exists",
                )

        old_values = self._audit_values(reference)
        for field, value in data.items():
            setattr(reference, field, value)
        self._audit(
            actor_id,
            "UPDATE",
            reference,
            old_values=old_values,
            new_values=self._audit_values(reference),
        )
        self._session.commit()
        self._session.refresh(reference)
        return VerificationReferenceResponse.from_model(reference)

    def _validate_rules(
        self,
        reference_type: str,
        rules: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            return validate_reference_rules(reference_type, rules)
        except ValidationError as exc:
            raise BadRequestError(
                f"Invalid {reference_type} rules: {_validation_message(exc)}",
                "invalid_reference_rules",
            ) from exc
        except ValueError as exc:
            raise BadRequestError(str(exc), "invalid_reference_rules") from exc

    def _audit_values(self, reference: VerificationReference) -> dict[str, Any]:
        return {
            "reference_type": reference.reference_type,
            "code": reference.code,
            "title": reference.title,
            "source": reference.source,
            "version_label": reference.version_label,
            "effective_date": (
                reference.effective_date.isoformat()
                if reference.effective_date is not None
                else None
            ),
            "severity": reference.severity,
            "status": reference.status,
            "rules": reference.rules,
        }

    def _audit(
        self,
        actor_id: uuid.UUID,
        action: str,
        reference: VerificationReference,
        old_values: dict[str, Any] | None = None,
        new_values: dict[str, Any] | None = None,
    ) -> None:
        self._audit_logs.add(
            AuditLog(
                entity_type="verification_reference",
                entity_id=reference.id,
                action=action,
                actor_user_id=actor_id,
                old_values=old_values,
                new_values=new_values,
            )
        )


def resolve_applicable_references(
    references: list[VerificationReference],
) -> list[VerificationReference]:
    """Apply program overrides and keep the newest version per type/code."""

    chosen: dict[tuple[str, str], VerificationReference] = {}
    for reference in sorted(
        references,
        key=lambda item: (
            item.program_id is not None,
            item.effective_date or date.min,
            item.created_at,
        ),
    ):
        chosen[(reference.reference_type, reference.code)] = reference
    return sorted(
        chosen.values(),
        key=lambda item: (item.reference_type, item.code, item.version_label),
    )


__all__ = ["VerificationReferenceService", "resolve_applicable_references"]
