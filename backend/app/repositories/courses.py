import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.academic import (
    Course,
    CourseOutcome,
    CourseOutcomeStatus,
    CoursePrerequisite,
    CourseStatus,
)


class CourseRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, course_id: uuid.UUID) -> Course | None:
        return self._session.get(Course, course_id)

    def get_by_code(self, curriculum_version_id: uuid.UUID, course_code: str) -> Course | None:
        statement = select(Course).where(
            Course.curriculum_version_id == curriculum_version_id,
            func.upper(Course.course_code) == course_code.strip().upper(),
            Course.status == CourseStatus.ACTIVE.value,
        )
        return self._session.scalars(statement).first()

    def list_by_version(
        self, curriculum_version_id: uuid.UUID, active_only: bool = True
    ) -> list[Course]:
        statement = select(Course).where(Course.curriculum_version_id == curriculum_version_id)
        if active_only:
            statement = statement.where(Course.status == CourseStatus.ACTIVE.value)
        statement = statement.order_by(Course.course_code)
        return list(self._session.scalars(statement))

    def get_referencing_prerequisites(self, course_id: uuid.UUID) -> list[Course]:
        statement = (
            select(Course)
            .join(CoursePrerequisite, CoursePrerequisite.target_course_id == Course.id)
            .where(
                CoursePrerequisite.prerequisite_course_id == course_id,
                CoursePrerequisite.status.in_(("PROPOSED", "APPROVED")),
            )
            .order_by(Course.course_code)
        )
        return list(self._session.scalars(statement))

    def add(self, course: Course) -> Course:
        self._session.add(course)
        self._session.flush()
        return course


class CourseOutcomeRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, outcome_id: uuid.UUID) -> CourseOutcome | None:
        return self._session.get(CourseOutcome, outcome_id)

    def get_by_code(self, course_id: uuid.UUID, co_code: str) -> CourseOutcome | None:
        statement = select(CourseOutcome).where(
            CourseOutcome.course_id == course_id,
            func.upper(CourseOutcome.co_code) == co_code.strip().upper(),
            CourseOutcome.status == CourseOutcomeStatus.ACTIVE.value,
        )
        return self._session.scalars(statement).first()

    def list_by_course(self, course_id: uuid.UUID, active_only: bool = True) -> list[CourseOutcome]:
        statement = select(CourseOutcome).where(CourseOutcome.course_id == course_id)
        if active_only:
            statement = statement.where(CourseOutcome.status == CourseOutcomeStatus.ACTIVE.value)
        statement = statement.order_by(CourseOutcome.co_code)
        return list(self._session.scalars(statement))

    def add(self, outcome: CourseOutcome) -> CourseOutcome:
        self._session.add(outcome)
        self._session.flush()
        return outcome
