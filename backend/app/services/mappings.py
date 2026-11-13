import uuid
from datetime import date
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import BadRequestError, ConflictError, NotFoundError
from app.db.models.academic import (
    CourseOutcomeStatus,
    Curriculum,
    CurriculumVersion,
)
from app.db.models.audit import AuditLog
from app.db.models.mappings import (
    CoPoMapping,
    CoPoMappingVersion,
    CurriculumVersionProgramOutcome,
    MappingLevel,
    MappingStatus,
    MappingVersionStatus,
)
from app.db.models.outcomes import (
    OutcomeStatus,
    OutcomeVersionStatus,
    ProgramOutcome,
    ProgramOutcomeVersion,
)
from app.db.models.user import utc_now
from app.repositories.audit import AuditLogRepository
from app.repositories.courses import CourseOutcomeRepository
from app.repositories.curricula import (
    CurriculumRepository,
    CurriculumVersionRepository,
)
from app.repositories.mappings import (
    CoPoMappingRepository,
    CoPoMappingVersionRepository,
    CurriculumVersionProgramOutcomeRepository,
    MappingLevelRepository,
)
from app.repositories.outcomes import OutcomeRepository, OutcomeVersionRepository
from app.schemas.mappings import (
    MappingCreate,
    MappingLevelResponse,
    MappingResponse,
    MappingUpdate,
    MappingVersionResponse,
    MappingVersionStatusUpdate,
)

MAPPING_VERSION_TRANSITIONS: dict[MappingVersionStatus, set[MappingVersionStatus]] = {
    MappingVersionStatus.DRAFT: {MappingVersionStatus.PROPOSED},
    MappingVersionStatus.PROPOSED: {
        MappingVersionStatus.APPROVED,
        MappingVersionStatus.REJECTED,
    },
    MappingVersionStatus.REJECTED: {MappingVersionStatus.DRAFT},
    MappingVersionStatus.APPROVED: set(),
    MappingVersionStatus.SUPERSEDED: set(),
}


def _version_snapshot(version: CoPoMappingVersion) -> dict[str, Any]:
    return {
        "version_number": version.version_number,
        "mapping_level_id": str(version.mapping_level_id),
        "effective_date": (version.effective_date.isoformat() if version.effective_date else None),
        "status": version.status,
    }


class MappingService:
    def __init__(
        self,
        session: Session,
        curricula: CurriculumRepository,
        versions: CurriculumVersionRepository,
        course_outcomes: CourseOutcomeRepository,
        program_outcomes: OutcomeRepository,
        program_outcome_versions: OutcomeVersionRepository,
        levels: MappingLevelRepository,
        pins: CurriculumVersionProgramOutcomeRepository,
        mappings: CoPoMappingRepository,
        mapping_versions: CoPoMappingVersionRepository,
        audit_logs: AuditLogRepository,
    ) -> None:
        self._session = session
        self._curricula = curricula
        self._versions = versions
        self._course_outcomes = course_outcomes
        self._program_outcomes = program_outcomes
        self._program_outcome_versions = program_outcome_versions
        self._levels = levels
        self._pins = pins
        self._mappings = mappings
        self._mapping_versions = mapping_versions
        self._audit_logs = audit_logs

    def list_mapping_levels(self) -> list[MappingLevelResponse]:
        return [MappingLevelResponse.from_model(level) for level in self._levels.list_active()]

    def list_mappings(
        self,
        curriculum_id: uuid.UUID,
        version_id: uuid.UUID,
        course_outcome_id: uuid.UUID | None = None,
        program_outcome_id: uuid.UUID | None = None,
    ) -> list[MappingResponse]:
        self._get_version_or_404(curriculum_id, version_id)
        return [
            MappingResponse.from_model(mapping)
            for mapping in self._mappings.list_by_version(
                version_id, course_outcome_id, program_outcome_id
            )
        ]

    def get_mapping(self, mapping_id: uuid.UUID) -> MappingResponse:
        mapping = self._get_mapping_or_404(mapping_id)
        return MappingResponse.from_model(mapping)

    def create_mapping(
        self,
        actor_id: uuid.UUID,
        curriculum_id: uuid.UUID,
        version_id: uuid.UUID,
        request: MappingCreate,
    ) -> MappingResponse:
        curriculum, version = self._get_curriculum_and_version(curriculum_id, version_id)
        self._ensure_editable(version)

        course_outcome = self._course_outcomes.get_by_id(request.course_outcome_id)
        if (
            course_outcome is None
            or course_outcome.curriculum_version_id != version.id
            or course_outcome.status != CourseOutcomeStatus.ACTIVE.value
        ):
            raise NotFoundError("Course outcome not found in this curriculum version")

        program_outcome = self._program_outcomes.get_by_id(request.program_outcome_id)
        if (
            program_outcome is None
            or program_outcome.program_id != curriculum.program_id
            or program_outcome.status != OutcomeStatus.ACTIVE.value
        ):
            raise NotFoundError("Program outcome not found or not active for this program")

        outcome_versions = self._program_outcome_versions.list_by_parent(program_outcome.id)
        approved_version = outcome_versions[-1] if outcome_versions else None
        if (
            approved_version is not None
            and approved_version.status != OutcomeVersionStatus.APPROVED.value
        ):
            approved_version.status = OutcomeVersionStatus.APPROVED.value
            approved_version.approved_by = actor_id
            approved_version.approved_at = utc_now()
        if approved_version is None:
            raise BadRequestError("Program outcome needs a description before it can be mapped")

        level = self._get_level_or_404(request.mapping_level_code)
        if self._mappings.get_active(version.id, course_outcome.id, program_outcome.id) is not None:
            raise ConflictError(
                "An active mapping already exists for this course outcome and program outcome",
                "mapping_exists",
            )

        self._pin_outcome_version(actor_id, version.id, program_outcome, approved_version)
        mapping = CoPoMapping(
            curriculum_version_id=version.id,
            course_outcome_id=course_outcome.id,
            program_outcome_id=program_outcome.id,
            status=MappingStatus.ACTIVE.value,
            created_by=actor_id,
        )
        mapping_version = CoPoMappingVersion(
            mapping=mapping,
            version_number=1,
            mapping_level_id=level.id,
            effective_date=request.effective_date,
            status=MappingVersionStatus.APPROVED.value,
            approved_by=actor_id,
            approved_at=utc_now(),
            created_by=actor_id,
        )
        try:
            self._mappings.add(mapping)
            self._mapping_versions.add(mapping_version)
            self._audit(
                actor_id,
                "co_po_mapping",
                mapping.id,
                "CREATE",
                curriculum_version_id=version.id,
                new_values={
                    "course_outcome_id": str(course_outcome.id),
                    "program_outcome_id": str(program_outcome.id),
                    "status": mapping.status,
                },
            )
            self._audit(
                actor_id,
                "co_po_mapping_version",
                mapping_version.id,
                "CREATE",
                curriculum_version_id=version.id,
                new_values=_version_snapshot(mapping_version),
            )
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise ConflictError(
                "An active mapping already exists for this course outcome and program outcome",
                "mapping_exists",
            ) from exc

        return self.get_mapping(mapping.id)

    def update_mapping(
        self,
        actor_id: uuid.UUID,
        mapping_id: uuid.UUID,
        request: MappingUpdate,
    ) -> MappingResponse:
        mapping = self._get_mapping_or_404(mapping_id)
        version = self._get_version_model_or_404(mapping.curriculum_version_id)
        self._ensure_editable(version)
        if mapping.status != MappingStatus.ACTIVE.value:
            raise ConflictError("Mapping is not active", "mapping_inactive")

        changes = request.model_fields_set
        if not changes:
            return MappingResponse.from_model(mapping)

        level: MappingLevel | None = None
        if "mapping_level_code" in changes:
            if request.mapping_level_code is None:
                raise BadRequestError("Mapping level cannot be empty")
            level = self._get_level_or_404(request.mapping_level_code)

        latest = max(mapping.versions, key=lambda item: item.version_number, default=None)
        if latest is None:
            raise NotFoundError("Mapping version not found")
        old_values = _version_snapshot(latest)
        if level is not None:
            latest.mapping_level_id = level.id
            latest.mapping_level = level
        if "effective_date" in changes:
            latest.effective_date = request.effective_date
        latest.status = MappingVersionStatus.APPROVED.value
        latest.approved_by = actor_id
        latest.approved_at = utc_now()
        latest.review_comments = None
        self._audit(
            actor_id,
            "co_po_mapping_version",
            latest.id,
            "UPDATE",
            curriculum_version_id=version.id,
            old_values=old_values,
            new_values=_version_snapshot(latest),
        )

        self._session.commit()
        return self.get_mapping(mapping.id)

    def remove_mapping(self, actor_id: uuid.UUID, mapping_id: uuid.UUID) -> None:
        mapping = self._get_mapping_or_404(mapping_id)
        version = self._get_version_model_or_404(mapping.curriculum_version_id)
        self._ensure_editable(version)
        if mapping.status != MappingStatus.ACTIVE.value:
            raise ConflictError("Mapping is already inactive", "mapping_inactive")

        old_values = {
            "status": mapping.status,
            "course_outcome_id": str(mapping.course_outcome_id),
            "program_outcome_id": str(mapping.program_outcome_id),
        }
        mapping.status = MappingStatus.INACTIVE.value
        self._audit(
            actor_id,
            "co_po_mapping",
            mapping.id,
            "REMOVE",
            curriculum_version_id=version.id,
            old_values=old_values,
            new_values={"status": mapping.status},
        )
        self._session.commit()

    def list_mapping_versions(self, mapping_id: uuid.UUID) -> list[MappingVersionResponse]:
        self._get_mapping_or_404(mapping_id)
        return [
            MappingVersionResponse.from_model(version)
            for version in self._mapping_versions.list_by_mapping(mapping_id)
        ]

    def update_mapping_version_status(
        self,
        actor_id: uuid.UUID,
        mapping_id: uuid.UUID,
        version_id: uuid.UUID,
        request: MappingVersionStatusUpdate,
    ) -> MappingVersionResponse:
        mapping = self._get_mapping_or_404(mapping_id)
        curriculum_version = self._get_version_model_or_404(mapping.curriculum_version_id)
        self._ensure_editable(curriculum_version)
        version = self._mapping_versions.get_by_id(version_id)
        if version is None or version.mapping_id != mapping.id:
            raise NotFoundError("Mapping version not found")

        current_status = MappingVersionStatus(version.status)
        target_status = request.status
        if target_status == current_status:
            raise BadRequestError(
                "Mapping version already has the requested status",
                "mapping_version_status_unchanged",
            )
        if target_status not in MAPPING_VERSION_TRANSITIONS[current_status]:
            raise ConflictError(
                f"Cannot change mapping version status from {current_status.value} "
                f"to {target_status.value}",
                "invalid_mapping_version_transition",
            )

        old_values = _version_snapshot(version)
        if target_status == MappingVersionStatus.APPROVED:
            for other in mapping.versions:
                if other.id != version.id and other.status == MappingVersionStatus.APPROVED.value:
                    other.status = MappingVersionStatus.SUPERSEDED.value
                    self._audit(
                        actor_id,
                        "co_po_mapping_version",
                        other.id,
                        "STATUS_CHANGE",
                        curriculum_version_id=curriculum_version.id,
                        old_values={"status": MappingVersionStatus.APPROVED.value},
                        new_values={"status": MappingVersionStatus.SUPERSEDED.value},
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
            "co_po_mapping_version",
            version.id,
            "STATUS_CHANGE",
            curriculum_version_id=curriculum_version.id,
            old_values=old_values,
            new_values=_version_snapshot(version),
        )
        self._session.commit()
        return MappingVersionResponse.from_model(version)

    def _pin_outcome_version(
        self,
        actor_id: uuid.UUID,
        curriculum_version_id: uuid.UUID,
        program_outcome: ProgramOutcome,
        approved_version: ProgramOutcomeVersion,
    ) -> None:
        pin = self._pins.get(curriculum_version_id, program_outcome.id)
        if pin is None:
            self._pins.add(
                CurriculumVersionProgramOutcome(
                    curriculum_version_id=curriculum_version_id,
                    program_outcome_id=program_outcome.id,
                    program_outcome_version_id=approved_version.id,
                    added_by=actor_id,
                )
            )
            return
        if pin.program_outcome_version_id != approved_version.id:
            pin.program_outcome_version_id = approved_version.id

    def _get_curriculum_and_version(
        self, curriculum_id: uuid.UUID, version_id: uuid.UUID
    ) -> tuple[Curriculum, CurriculumVersion]:
        curriculum = self._curricula.get_by_id(curriculum_id)
        if curriculum is None:
            raise NotFoundError("Curriculum not found")
        version = self._versions.get_by_id(version_id)
        if version is None or version.curriculum_id != curriculum.id:
            raise NotFoundError("Curriculum version not found")
        return curriculum, version

    def _get_version_model_or_404(self, version_id: uuid.UUID) -> CurriculumVersion:
        version = self._versions.get_by_id(version_id)
        if version is None:
            raise NotFoundError("Curriculum version not found")
        return version

    def _get_version_or_404(
        self, curriculum_id: uuid.UUID, version_id: uuid.UUID
    ) -> CurriculumVersion:
        _, version = self._get_curriculum_and_version(curriculum_id, version_id)
        return version

    def _get_mapping_or_404(self, mapping_id: uuid.UUID) -> CoPoMapping:
        mapping = self._mappings.get_by_id(mapping_id)
        if mapping is None:
            raise NotFoundError("CO-PO mapping not found")
        return mapping

    def _get_level_or_404(self, code: str) -> MappingLevel:
        level = self._levels.get_by_code(code)
        if level is None:
            raise NotFoundError(f"Mapping level {code} not found")
        return level

    def _ensure_editable(self, version: CurriculumVersion) -> None:
        # Active curriculum content is mutable; no draft/approval gate applies.
        return None

    def _audit(
        self,
        actor_id: uuid.UUID,
        entity_type: str,
        entity_id: uuid.UUID,
        action: str,
        curriculum_version_id: uuid.UUID,
        old_values: dict[str, Any] | None = None,
        new_values: dict[str, Any] | None = None,
    ) -> None:
        self._audit_logs.add(
            AuditLog(
                entity_type=entity_type,
                entity_id=entity_id,
                action=action,
                actor_user_id=actor_id,
                curriculum_version_id=curriculum_version_id,
                old_values=old_values,
                new_values=new_values,
            )
        )
