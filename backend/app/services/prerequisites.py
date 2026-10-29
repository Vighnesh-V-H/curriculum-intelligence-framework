import uuid
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import BadRequestError, ConflictError, NotFoundError
from app.db.models.academic import (
    Course,
    CoursePrerequisite,
    CourseStatus,
    Curriculum,
    CurriculumVersion,
    PrerequisiteStatus,
    VersionStatus,
)
from app.db.models.audit import AuditLog
from app.db.models.user import utc_now
from app.repositories.audit import AuditLogRepository
from app.repositories.courses import CourseRepository
from app.repositories.curricula import (
    CurriculumRepository,
    CurriculumVersionRepository,
)
from app.repositories.prerequisites import CoursePrerequisiteRepository
from app.schemas.prerequisite import (
    PrerequisiteCreate,
    PrerequisiteResponse,
    PrerequisiteStatusUpdate,
)

REVIEW_TRANSITIONS: dict[PrerequisiteStatus, set[PrerequisiteStatus]] = {
    PrerequisiteStatus.PROPOSED: {
        PrerequisiteStatus.APPROVED,
        PrerequisiteStatus.REJECTED,
    },
    PrerequisiteStatus.APPROVED: set(),
    PrerequisiteStatus.REJECTED: set(),
    PrerequisiteStatus.REMOVED: set(),
}


def _edge_snapshot(prerequisite: CoursePrerequisite) -> dict[str, Any]:
    return {
        "prerequisite_course_id": str(prerequisite.prerequisite_course_id),
        "target_course_id": str(prerequisite.target_course_id),
        "status": prerequisite.status,
    }


def _would_create_cycle(
    edges: list[tuple[uuid.UUID, uuid.UUID]],
    prerequisite_course_id: uuid.UUID,
    target_course_id: uuid.UUID,
) -> bool:
    adjacency: dict[uuid.UUID, list[uuid.UUID]] = {}
    for source, destination in edges:
        adjacency.setdefault(source, []).append(destination)
    adjacency.setdefault(prerequisite_course_id, []).append(target_course_id)

    # A cycle exists when the target course can reach the prerequisite
    # course through the dependency graph (prerequisite -> dependent).
    stack = [target_course_id]
    visited: set[uuid.UUID] = set()
    while stack:
        current = stack.pop()
        if current == prerequisite_course_id:
            return True
        if current in visited:
            continue
        visited.add(current)
        stack.extend(adjacency.get(current, []))
    return False


class PrerequisiteService:
    def __init__(
        self,
        session: Session,
        curricula: CurriculumRepository,
        versions: CurriculumVersionRepository,
        courses: CourseRepository,
        prerequisites: CoursePrerequisiteRepository,
        audit_logs: AuditLogRepository,
    ) -> None:
        self._session = session
        self._curricula = curricula
        self._versions = versions
        self._courses = courses
        self._prerequisites = prerequisites
        self._audit_logs = audit_logs

    def list_prerequisites(
        self,
        curriculum_id: uuid.UUID,
        version_id: uuid.UUID,
        course_id: uuid.UUID | None = None,
        direction: str = "both",
    ) -> list[PrerequisiteResponse]:
        self._get_version_or_404(curriculum_id, version_id)
        if course_id is None:
            relationships = self._prerequisites.list_by_version(version_id)
        else:
            self._get_course_in_version_or_404(version_id, course_id)
            relationships = self._prerequisites.list_by_course(version_id, course_id)
            if direction == "incoming":
                relationships = [
                    item for item in relationships if item.target_course_id == course_id
                ]
            elif direction == "outgoing":
                relationships = [
                    item for item in relationships if item.prerequisite_course_id == course_id
                ]
        return [PrerequisiteResponse.from_model(item) for item in relationships]

    def get_prerequisite(
        self,
        curriculum_id: uuid.UUID,
        version_id: uuid.UUID,
        prerequisite_id: uuid.UUID,
    ) -> PrerequisiteResponse:
        self._get_version_or_404(curriculum_id, version_id)
        prerequisite = self._prerequisites.get_by_id(prerequisite_id)
        if prerequisite is None or prerequisite.curriculum_version_id != version_id:
            raise NotFoundError("Prerequisite relationship not found")
        return PrerequisiteResponse.from_model(prerequisite)

    def create_prerequisite(
        self,
        actor_id: uuid.UUID,
        curriculum_id: uuid.UUID,
        version_id: uuid.UUID,
        request: PrerequisiteCreate,
    ) -> PrerequisiteResponse:
        self._get_version_or_404(curriculum_id, version_id)
        self._ensure_draft(version_id)

        prerequisite_course = self._get_course_in_version_or_404(
            version_id, request.prerequisite_course_id
        )
        target_course = self._get_course_in_version_or_404(version_id, request.target_course_id)
        if prerequisite_course.id == target_course.id:
            raise BadRequestError("A course cannot be its own prerequisite", "self_prerequisite")
        if (
            self._prerequisites.get_active(version_id, prerequisite_course.id, target_course.id)
            is not None
        ):
            raise ConflictError(
                f"{prerequisite_course.course_code} is already a prerequisite "
                f"of {target_course.course_code}",
                "prerequisite_exists",
            )
        edges = self._prerequisites.list_active_edges(version_id)
        if _would_create_cycle(edges, prerequisite_course.id, target_course.id):
            raise ConflictError(
                "This prerequisite would create a circular dependency",
                "circular_prerequisite",
            )

        prerequisite = CoursePrerequisite(
            curriculum_version_id=version_id,
            prerequisite_course_id=prerequisite_course.id,
            target_course_id=target_course.id,
            status=PrerequisiteStatus.PROPOSED.value,
            created_by=actor_id,
        )
        try:
            self._prerequisites.add(prerequisite)
            self._audit(
                actor_id,
                "course_prerequisite",
                prerequisite.id,
                "CREATE",
                curriculum_version_id=version_id,
                new_values=_edge_snapshot(prerequisite),
            )
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise ConflictError(
                "Prerequisite relationship could not be created because of conflicting data",
                "prerequisite_conflict",
            ) from exc

        return PrerequisiteResponse.from_model(prerequisite)

    def update_prerequisite_status(
        self,
        actor_id: uuid.UUID,
        curriculum_id: uuid.UUID,
        version_id: uuid.UUID,
        prerequisite_id: uuid.UUID,
        request: PrerequisiteStatusUpdate,
    ) -> PrerequisiteResponse:
        self._get_version_or_404(curriculum_id, version_id)
        self._ensure_draft(version_id)
        prerequisite = self._prerequisites.get_by_id(prerequisite_id)
        if prerequisite is None or prerequisite.curriculum_version_id != version_id:
            raise NotFoundError("Prerequisite relationship not found")

        current_status = PrerequisiteStatus(prerequisite.status)
        target_status = request.status
        if target_status not in (
            PrerequisiteStatus.APPROVED,
            PrerequisiteStatus.REJECTED,
        ):
            raise BadRequestError(
                "Prerequisite status can only be set to APPROVED or REJECTED",
                "invalid_prerequisite_status",
            )
        if target_status == current_status:
            raise BadRequestError(
                "Prerequisite already has the requested status",
                "prerequisite_status_unchanged",
            )
        if target_status not in REVIEW_TRANSITIONS[current_status]:
            raise ConflictError(
                f"Cannot change prerequisite status from {current_status.value} "
                f"to {target_status.value}",
                "invalid_prerequisite_transition",
            )

        old_values = _edge_snapshot(prerequisite)
        prerequisite.status = target_status.value
        if request.review_comments is not None:
            prerequisite.review_comments = request.review_comments
        if target_status == PrerequisiteStatus.APPROVED:
            prerequisite.approved_by = actor_id
            prerequisite.approved_at = utc_now()
        self._audit(
            actor_id,
            "course_prerequisite",
            prerequisite.id,
            "STATUS_CHANGE",
            curriculum_version_id=version_id,
            old_values=old_values,
            new_values=_edge_snapshot(prerequisite),
        )
        self._session.commit()
        return PrerequisiteResponse.from_model(prerequisite)

    def remove_prerequisite(
        self,
        actor_id: uuid.UUID,
        curriculum_id: uuid.UUID,
        version_id: uuid.UUID,
        prerequisite_id: uuid.UUID,
    ) -> None:
        self._get_version_or_404(curriculum_id, version_id)
        self._ensure_draft(version_id)
        prerequisite = self._prerequisites.get_by_id(prerequisite_id)
        if (
            prerequisite is None
            or prerequisite.curriculum_version_id != version_id
            or prerequisite.status == PrerequisiteStatus.REMOVED.value
        ):
            raise NotFoundError("Prerequisite relationship not found")

        old_values = _edge_snapshot(prerequisite)
        prerequisite.status = PrerequisiteStatus.REMOVED.value
        self._audit(
            actor_id,
            "course_prerequisite",
            prerequisite.id,
            "REMOVE",
            curriculum_version_id=version_id,
            old_values=old_values,
            new_values={"status": prerequisite.status},
        )
        self._session.commit()

    def _get_curriculum_or_404(self, curriculum_id: uuid.UUID) -> Curriculum:
        curriculum = self._curricula.get_by_id(curriculum_id)
        if curriculum is None:
            raise NotFoundError("Curriculum not found")
        return curriculum

    def _get_version_or_404(
        self, curriculum_id: uuid.UUID, version_id: uuid.UUID
    ) -> CurriculumVersion:
        if self._curricula.get_by_id(curriculum_id) is None:
            raise NotFoundError("Curriculum not found")
        version = self._versions.get_by_id(version_id)
        if version is None or version.curriculum_id != curriculum_id:
            raise NotFoundError("Curriculum version not found")
        return version

    def _get_course_in_version_or_404(self, version_id: uuid.UUID, course_id: uuid.UUID) -> Course:
        course = self._courses.get_by_id(course_id)
        if (
            course is None
            or course.curriculum_version_id != version_id
            or course.status != CourseStatus.ACTIVE.value
        ):
            raise NotFoundError("Course not found in this curriculum version")
        return course

    def _ensure_draft(self, version_id: uuid.UUID) -> None:
        version = self._versions.get_by_id(version_id)
        if version is not None and version.status != VersionStatus.DRAFT.value:
            raise ConflictError(
                "Only draft curriculum versions can be modified",
                "curriculum_version_not_editable",
            )

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
