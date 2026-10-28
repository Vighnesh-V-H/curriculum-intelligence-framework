import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.academic import Course, CourseStatus


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

    def add(self, course: Course) -> Course:
        self._session.add(course)
        self._session.flush()
        return course
