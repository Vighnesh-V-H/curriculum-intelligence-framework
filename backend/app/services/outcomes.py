import uuid
from datetime import date
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import BadRequestError, ConflictError, NotFoundError
from app.db.models.academic import Program, ProgramStatus
from app.db.models.audit import AuditLog
from app.db.models.outcomes import (
    OutcomeStatus,
    OutcomeVersionStatus,
    PeoVersion,
    ProgramEducationalObjective,
    ProgramOutcome,
    ProgramOutcomeVersion,
)
from app.db.models.user import utc_now
from app.repositories.academic import ProgramRepository
from app.repositories.audit import AuditLogRepository
from app.repositories.outcomes import OutcomeRepository, OutcomeVersionRepository
from app.schemas.outcomes import (
    OutcomeStatusUpdate,
    OutcomeVersionResponse,
    OutcomeVersionStatusUpdate,
    ProgramEducationalObjectiveCreate,
    ProgramEducationalObjectiveResponse,
    ProgramEducationalObjectiveUpdate,
    ProgramOutcomeCreate,
    ProgramOutcomeResponse,
    ProgramOutcomeUpdate,
)

OUTCOME_VERSION_TRANSITIONS: dict[OutcomeVersionStatus, set[OutcomeVersionStatus]] = {
    OutcomeVersionStatus.DRAFT: {OutcomeVersionStatus.PROPOSED},
    OutcomeVersionStatus.PROPOSED: {
        OutcomeVersionStatus.APPROVED,
        OutcomeVersionStatus.REJECTED,
    },
    OutcomeVersionStatus.REJECTED: {OutcomeVersionStatus.DRAFT},
    OutcomeVersionStatus.APPROVED: set(),
    OutcomeVersionStatus.SUPERSEDED: set(),
}


def _version_snapshot(version: ProgramOutcomeVersion | PeoVersion) -> dict[str, Any]:
    return {
        "version_number": version.version_number,
        "description": version.description,
        "effective_date": (version.effective_date.isoformat() if version.effective_date else None),
        "status": version.status,
    }


class OutcomeService:
    def __init__(
        self,
        session: Session,
        programs: ProgramRepository,
        program_outcomes: OutcomeRepository,
        program_outcome_versions: OutcomeVersionRepository,
        peos: OutcomeRepository,
        peo_versions: OutcomeVersionRepository,
        audit_logs: AuditLogRepository,
    ) -> None:
        self._session = session
        self._programs = programs
        self._program_outcomes = program_outcomes
        self._program_outcome_versions = program_outcome_versions
        self._peos = peos
        self._peo_versions = peo_versions
        self._audit_logs = audit_logs

    def create_program_outcome(
        self,
        actor_id: uuid.UUID,
        program_id: uuid.UUID,
        request: ProgramOutcomeCreate,
    ) -> ProgramOutcomeResponse:
        program = self._get_active_program(program_id)
        if self._program_outcomes.get_by_code(program_id, request.po_code) is not None:
            raise ConflictError(
                f"Program outcome {request.po_code} already exists for this program",
                "program_outcome_exists",
            )

        outcome = ProgramOutcome(
            program_id=program.id,
            po_code=request.po_code,
            status=OutcomeStatus.ACTIVE.value,
            created_by=actor_id,
        )
        version = ProgramOutcomeVersion(
            program_outcome=outcome,
            version_number=1,
            description=request.description,
            effective_date=request.effective_date,
            status=OutcomeVersionStatus.DRAFT.value,
            created_by=actor_id,
        )
        try:
            self._program_outcomes.add(outcome)
            self._program_outcome_versions.add(version)
            self._audit(
                actor_id,
                "program_outcome",
                outcome.id,
                "CREATE",
                new_values={
                    "po_code": outcome.po_code,
                    "program_id": str(outcome.program_id),
                    "status": outcome.status,
                },
            )
            self._audit(
                actor_id,
                "program_outcome_version",
                version.id,
                "CREATE",
                new_values=_version_snapshot(version),
            )
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise ConflictError(
                f"Program outcome {request.po_code} already exists for this program",
                "program_outcome_exists",
            ) from exc

        return self.get_program_outcome(outcome.id)

    def list_program_outcomes(self, program_id: uuid.UUID) -> list[ProgramOutcomeResponse]:
        self._get_program_or_404(program_id)
        return [
            ProgramOutcomeResponse.from_model(outcome)
            for outcome in self._program_outcomes.list_by_program(program_id)
        ]

    def get_program_outcome(self, outcome_id: uuid.UUID) -> ProgramOutcomeResponse:
        outcome = self._get_program_outcome_or_404(outcome_id)
        return ProgramOutcomeResponse.from_model(outcome)

    def update_program_outcome(
        self,
        actor_id: uuid.UUID,
        outcome_id: uuid.UUID,
        request: ProgramOutcomeUpdate,
    ) -> ProgramOutcomeResponse:
        outcome = self._get_program_outcome_or_404(outcome_id)
        changes = request.model_fields_set
        if not changes:
            return ProgramOutcomeResponse.from_model(outcome)

        old_values = {
            "po_code": outcome.po_code,
            "status": outcome.status,
        }
        if "po_code" in changes:
            if request.po_code is None:
                raise BadRequestError("PO identifier cannot be empty")
            duplicate = self._program_outcomes.get_by_code(outcome.program_id, request.po_code)
            if duplicate is not None and duplicate.id != outcome.id:
                raise ConflictError(
                    f"Program outcome {request.po_code} already exists for this program",
                    "program_outcome_exists",
                )
            outcome.po_code = request.po_code

        if "description" in changes or "effective_date" in changes:
            self._update_outcome_version(
                actor_id=actor_id,
                parent=outcome,
                versions=outcome.versions,
                description=request.description,
                effective_date=request.effective_date,
                description_provided="description" in changes,
                version_repository=self._program_outcome_versions,
                version_model=ProgramOutcomeVersion,
                entity_type="program_outcome_version",
                parent_field="program_outcome",
            )

        self._audit(
            actor_id,
            "program_outcome",
            outcome.id,
            "UPDATE",
            old_values=old_values,
            new_values={"po_code": outcome.po_code, "status": outcome.status},
        )
        try:
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise ConflictError(
                "Program outcome could not be updated because of conflicting data",
                "program_outcome_conflict",
            ) from exc

        return self.get_program_outcome(outcome.id)

    def update_program_outcome_status(
        self,
        actor_id: uuid.UUID,
        outcome_id: uuid.UUID,
        request: OutcomeStatusUpdate,
    ) -> ProgramOutcomeResponse:
        outcome = self._get_program_outcome_or_404(outcome_id)
        self._update_outcome_status(actor_id, outcome, request, "program_outcome", "po_code")
        self._session.commit()
        return self.get_program_outcome(outcome.id)

    def list_program_outcome_versions(self, outcome_id: uuid.UUID) -> list[OutcomeVersionResponse]:
        self._get_program_outcome_or_404(outcome_id)
        return [
            OutcomeVersionResponse.from_model(version)
            for version in self._program_outcome_versions.list_by_parent(outcome_id)
        ]

    def update_program_outcome_version_status(
        self,
        actor_id: uuid.UUID,
        outcome_id: uuid.UUID,
        version_id: uuid.UUID,
        request: OutcomeVersionStatusUpdate,
    ) -> OutcomeVersionResponse:
        outcome = self._get_program_outcome_or_404(outcome_id)
        version = self._program_outcome_versions.get_by_id(version_id)
        if version is None or version.program_outcome_id != outcome.id:
            raise NotFoundError("Program outcome version not found")
        self._update_version_status(
            actor_id,
            version,
            request,
            approved_versions=outcome.versions,
            entity_type="program_outcome_version",
        )
        self._session.commit()
        return OutcomeVersionResponse.from_model(version)

    def create_peo(
        self,
        actor_id: uuid.UUID,
        program_id: uuid.UUID,
        request: ProgramEducationalObjectiveCreate,
    ) -> ProgramEducationalObjectiveResponse:
        program = self._get_active_program(program_id)
        if self._peos.get_by_code(program_id, request.peo_code) is not None:
            raise ConflictError(
                f"Program educational objective {request.peo_code} already exists for this program",
                "peo_exists",
            )

        objective = ProgramEducationalObjective(
            program_id=program.id,
            peo_code=request.peo_code,
            status=OutcomeStatus.ACTIVE.value,
            created_by=actor_id,
        )
        version = PeoVersion(
            program_educational_objective=objective,
            version_number=1,
            description=request.description,
            effective_date=request.effective_date,
            status=OutcomeVersionStatus.DRAFT.value,
            created_by=actor_id,
        )
        try:
            self._peos.add(objective)
            self._peo_versions.add(version)
            self._audit(
                actor_id,
                "peo",
                objective.id,
                "CREATE",
                new_values={
                    "peo_code": objective.peo_code,
                    "program_id": str(objective.program_id),
                    "status": objective.status,
                },
            )
            self._audit(
                actor_id,
                "peo_version",
                version.id,
                "CREATE",
                new_values=_version_snapshot(version),
            )
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise ConflictError(
                f"Program educational objective {request.peo_code} already exists for this program",
                "peo_exists",
            ) from exc

        return self.get_peo(objective.id)

    def list_peos(self, program_id: uuid.UUID) -> list[ProgramEducationalObjectiveResponse]:
        self._get_program_or_404(program_id)
        return [
            ProgramEducationalObjectiveResponse.from_model(objective)
            for objective in self._peos.list_by_program(program_id)
        ]

    def get_peo(self, peo_id: uuid.UUID) -> ProgramEducationalObjectiveResponse:
        objective = self._get_peo_or_404(peo_id)
        return ProgramEducationalObjectiveResponse.from_model(objective)

    def update_peo(
        self,
        actor_id: uuid.UUID,
        peo_id: uuid.UUID,
        request: ProgramEducationalObjectiveUpdate,
    ) -> ProgramEducationalObjectiveResponse:
        objective = self._get_peo_or_404(peo_id)
        changes = request.model_fields_set
        if not changes:
            return ProgramEducationalObjectiveResponse.from_model(objective)

        old_values = {
            "peo_code": objective.peo_code,
            "status": objective.status,
        }
        if "peo_code" in changes:
            if request.peo_code is None:
                raise BadRequestError("PEO identifier cannot be empty")
            duplicate = self._peos.get_by_code(objective.program_id, request.peo_code)
            if duplicate is not None and duplicate.id != objective.id:
                raise ConflictError(
                    f"Program educational objective {request.peo_code} already exists "
                    "for this program",
                    "peo_exists",
                )
            objective.peo_code = request.peo_code

        if "description" in changes or "effective_date" in changes:
            self._update_outcome_version(
                actor_id=actor_id,
                parent=objective,
                versions=objective.versions,
                description=request.description,
                effective_date=request.effective_date,
                description_provided="description" in changes,
                version_repository=self._peo_versions,
                version_model=PeoVersion,
                entity_type="peo_version",
                parent_field="program_educational_objective",
            )

        self._audit(
            actor_id,
            "peo",
            objective.id,
            "UPDATE",
            old_values=old_values,
            new_values={"peo_code": objective.peo_code, "status": objective.status},
        )
        try:
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise ConflictError(
                "Program educational objective could not be updated because of conflicting data",
                "peo_conflict",
            ) from exc

        return self.get_peo(objective.id)

    def update_peo_status(
        self,
        actor_id: uuid.UUID,
        peo_id: uuid.UUID,
        request: OutcomeStatusUpdate,
    ) -> ProgramEducationalObjectiveResponse:
        objective = self._get_peo_or_404(peo_id)
        self._update_outcome_status(actor_id, objective, request, "peo", "peo_code")
        self._session.commit()
        return self.get_peo(objective.id)

    def list_peo_versions(self, peo_id: uuid.UUID) -> list[OutcomeVersionResponse]:
        self._get_peo_or_404(peo_id)
        return [
            OutcomeVersionResponse.from_model(version)
            for version in self._peo_versions.list_by_parent(peo_id)
        ]

    def update_peo_version_status(
        self,
        actor_id: uuid.UUID,
        peo_id: uuid.UUID,
        version_id: uuid.UUID,
        request: OutcomeVersionStatusUpdate,
    ) -> OutcomeVersionResponse:
        objective = self._get_peo_or_404(peo_id)
        version = self._peo_versions.get_by_id(version_id)
        if version is None or version.peo_id != objective.id:
            raise NotFoundError("PEO version not found")
        self._update_version_status(
            actor_id,
            version,
            request,
            approved_versions=objective.versions,
            entity_type="peo_version",
        )
        self._session.commit()
        return OutcomeVersionResponse.from_model(version)

    def _update_outcome_version(
        self,
        actor_id: uuid.UUID,
        parent: ProgramOutcome | ProgramEducationalObjective,
        versions: list[ProgramOutcomeVersion] | list[PeoVersion],
        description: str | None,
        effective_date: date | None,
        description_provided: bool,
        version_repository: OutcomeVersionRepository,
        version_model: type[ProgramOutcomeVersion] | type[PeoVersion],
        entity_type: str,
        parent_field: str,
    ) -> None:
        ordered = sorted(versions, key=lambda item: item.version_number)
        latest = ordered[-1] if ordered else None
        if latest is not None and latest.status == OutcomeVersionStatus.PROPOSED.value:
            raise ConflictError(
                "The latest version is under review and cannot be modified",
                "outcome_version_under_review",
            )
        if latest is not None and latest.status in (
            OutcomeVersionStatus.DRAFT.value,
            OutcomeVersionStatus.REJECTED.value,
        ):
            old_values = _version_snapshot(latest)
            if description_provided and description is not None:
                latest.description = description
            if effective_date is not None:
                latest.effective_date = effective_date
            latest.status = OutcomeVersionStatus.DRAFT.value
            latest.review_comments = None
            self._audit(
                actor_id,
                entity_type,
                latest.id,
                "UPDATE",
                old_values=old_values,
                new_values=_version_snapshot(latest),
            )
            return

        if not description_provided or description is None:
            raise BadRequestError(
                "A new version requires a description",
                "description_required",
            )
        version = version_model(
            **{
                parent_field: parent,
                "version_number": version_repository.next_version_number(parent.id),
                "description": description,
                "effective_date": effective_date,
                "status": OutcomeVersionStatus.DRAFT.value,
                "created_by": actor_id,
            }
        )
        version_repository.add(version)
        self._audit(
            actor_id,
            entity_type,
            version.id,
            "CREATE",
            new_values=_version_snapshot(version),
        )

    def _update_outcome_status(
        self,
        actor_id: uuid.UUID,
        outcome: ProgramOutcome | ProgramEducationalObjective,
        request: OutcomeStatusUpdate,
        entity_type: str,
        code_field: str,
    ) -> None:
        target = request.status.value
        if target == outcome.status:
            raise BadRequestError(
                f"Outcome is already {target.lower()}",
                "outcome_status_unchanged",
            )
        old_values = {code_field: getattr(outcome, code_field), "status": outcome.status}
        outcome.status = target
        self._audit(
            actor_id,
            entity_type,
            outcome.id,
            "STATUS_CHANGE",
            old_values=old_values,
            new_values={
                code_field: getattr(outcome, code_field),
                "status": outcome.status,
            },
        )

    def _update_version_status(
        self,
        actor_id: uuid.UUID,
        version: ProgramOutcomeVersion | PeoVersion,
        request: OutcomeVersionStatusUpdate,
        approved_versions: list[ProgramOutcomeVersion] | list[PeoVersion],
        entity_type: str,
    ) -> None:
        current_status = OutcomeVersionStatus(version.status)
        target_status = request.status
        if target_status == current_status:
            raise BadRequestError(
                "Version already has the requested status",
                "outcome_version_status_unchanged",
            )
        if target_status not in OUTCOME_VERSION_TRANSITIONS[current_status]:
            raise ConflictError(
                f"Cannot change outcome version status from {current_status.value} "
                f"to {target_status.value}",
                "invalid_outcome_version_transition",
            )

        old_values = _version_snapshot(version)
        if target_status == OutcomeVersionStatus.APPROVED:
            for other in approved_versions:
                if other.id != version.id and other.status == OutcomeVersionStatus.APPROVED.value:
                    other.status = OutcomeVersionStatus.SUPERSEDED.value
                    self._audit(
                        actor_id,
                        entity_type,
                        other.id,
                        "STATUS_CHANGE",
                        old_values={"status": OutcomeVersionStatus.APPROVED.value},
                        new_values={"status": OutcomeVersionStatus.SUPERSEDED.value},
                    )
            self._session.flush()
            version.approved_by = actor_id
            version.approved_at = utc_now()
            if version.effective_date is None:
                version.effective_date = date.today()
        version.status = target_status.value
        if request.review_comments is not None:
            version.review_comments = request.review_comments
        self._audit(
            actor_id,
            entity_type,
            version.id,
            "STATUS_CHANGE",
            old_values=old_values,
            new_values=_version_snapshot(version),
        )

    def _get_active_program(self, program_id: uuid.UUID) -> Program:
        program = self._get_program_or_404(program_id)
        if program.status != ProgramStatus.ACTIVE.value:
            raise BadRequestError("Program is not active", "inactive_program")
        return program

    def _get_program_or_404(self, program_id: uuid.UUID) -> Program:
        program = self._programs.get_by_id(program_id)
        if program is None:
            raise NotFoundError("Program not found")
        return program

    def _get_program_outcome_or_404(self, outcome_id: uuid.UUID) -> ProgramOutcome:
        outcome = self._program_outcomes.get_by_id(outcome_id)
        if outcome is None:
            raise NotFoundError("Program outcome not found")
        return outcome

    def _get_peo_or_404(self, peo_id: uuid.UUID) -> ProgramEducationalObjective:
        objective = self._peos.get_by_id(peo_id)
        if objective is None:
            raise NotFoundError("Program educational objective not found")
        return objective

    def _audit(
        self,
        actor_id: uuid.UUID,
        entity_type: str,
        entity_id: uuid.UUID,
        action: str,
        old_values: dict[str, Any] | None = None,
        new_values: dict[str, Any] | None = None,
    ) -> None:
        self._audit_logs.add(
            AuditLog(
                entity_type=entity_type,
                entity_id=entity_id,
                action=action,
                actor_user_id=actor_id,
                old_values=old_values,
                new_values=new_values,
            )
        )
