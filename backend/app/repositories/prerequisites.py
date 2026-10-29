import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.academic import CoursePrerequisite, PrerequisiteStatus

ACTIVE_STATUSES = (
    PrerequisiteStatus.PROPOSED.value,
    PrerequisiteStatus.APPROVED.value,
)


class CoursePrerequisiteRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, prerequisite_id: uuid.UUID) -> CoursePrerequisite | None:
        return self._session.get(CoursePrerequisite, prerequisite_id)

    def get_active(
        self,
        curriculum_version_id: uuid.UUID,
        prerequisite_course_id: uuid.UUID,
        target_course_id: uuid.UUID,
    ) -> CoursePrerequisite | None:
        statement = select(CoursePrerequisite).where(
            CoursePrerequisite.curriculum_version_id == curriculum_version_id,
            CoursePrerequisite.prerequisite_course_id == prerequisite_course_id,
            CoursePrerequisite.target_course_id == target_course_id,
            CoursePrerequisite.status.in_(ACTIVE_STATUSES),
        )
        return self._session.scalars(statement).first()

    def list_by_version(
        self,
        curriculum_version_id: uuid.UUID,
    ) -> list[CoursePrerequisite]:
        statement = (
            select(CoursePrerequisite)
            .where(
                CoursePrerequisite.curriculum_version_id == curriculum_version_id,
                CoursePrerequisite.status != PrerequisiteStatus.REMOVED.value,
            )
            .order_by(CoursePrerequisite.created_at)
        )
        return list(self._session.scalars(statement))

    def list_by_course(
        self,
        curriculum_version_id: uuid.UUID,
        course_id: uuid.UUID,
    ) -> list[CoursePrerequisite]:
        statement = (
            select(CoursePrerequisite)
            .where(
                CoursePrerequisite.curriculum_version_id == curriculum_version_id,
                CoursePrerequisite.status != PrerequisiteStatus.REMOVED.value,
            )
            .where(
                (CoursePrerequisite.prerequisite_course_id == course_id)
                | (CoursePrerequisite.target_course_id == course_id)
            )
            .order_by(CoursePrerequisite.created_at)
        )
        return list(self._session.scalars(statement))

    def list_active_edges(
        self, curriculum_version_id: uuid.UUID
    ) -> list[tuple[uuid.UUID, uuid.UUID]]:
        statement = select(
            CoursePrerequisite.prerequisite_course_id,
            CoursePrerequisite.target_course_id,
        ).where(
            CoursePrerequisite.curriculum_version_id == curriculum_version_id,
            CoursePrerequisite.status.in_(ACTIVE_STATUSES),
        )
        return [
            (prerequisite_id, target_id)
            for prerequisite_id, target_id in self._session.execute(statement)
        ]

    def add(self, prerequisite: CoursePrerequisite) -> CoursePrerequisite:
        self._session.add(prerequisite)
        self._session.flush()
        return prerequisite
