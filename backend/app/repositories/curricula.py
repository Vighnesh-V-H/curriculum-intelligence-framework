import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.academic import Curriculum, CurriculumVersion, Semester


class CurriculumRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, curriculum_id: uuid.UUID) -> Curriculum | None:
        return self._session.get(Curriculum, curriculum_id)

    def get_by_program_regulation(
        self, program_id: uuid.UUID, regulation: str
    ) -> Curriculum | None:
        statement = select(Curriculum).where(
            Curriculum.program_id == program_id,
            func.lower(Curriculum.regulation) == regulation.strip().lower(),
        )
        return self._session.scalars(statement).first()

    def list(self) -> list[Curriculum]:
        statement = select(Curriculum).order_by(
            Curriculum.academic_year.desc(), Curriculum.regulation.desc()
        )
        return list(self._session.scalars(statement))

    def add(self, curriculum: Curriculum) -> Curriculum:
        self._session.add(curriculum)
        self._session.flush()
        return curriculum


class CurriculumVersionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, version_id: uuid.UUID) -> CurriculumVersion | None:
        return self._session.get(CurriculumVersion, version_id)

    def list_by_curriculum(self, curriculum_id: uuid.UUID) -> list[CurriculumVersion]:
        statement = (
            select(CurriculumVersion)
            .where(CurriculumVersion.curriculum_id == curriculum_id)
            .order_by(CurriculumVersion.created_at)
        )
        return list(self._session.scalars(statement))

    def get_by_label(
        self, curriculum_id: uuid.UUID, version_label: str
    ) -> CurriculumVersion | None:
        statement = select(CurriculumVersion).where(
            CurriculumVersion.curriculum_id == curriculum_id,
            CurriculumVersion.version_label == version_label,
        )
        return self._session.scalars(statement).first()

    def get_latest(self, curriculum_id: uuid.UUID) -> CurriculumVersion | None:
        statement = (
            select(CurriculumVersion)
            .where(CurriculumVersion.curriculum_id == curriculum_id)
            .order_by(
                CurriculumVersion.created_at.desc(),
                CurriculumVersion.version_label.desc(),
            )
        )
        return self._session.scalars(statement).first()

    def add(self, version: CurriculumVersion) -> CurriculumVersion:
        self._session.add(version)
        self._session.flush()
        return version


class SemesterRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_number(
        self, curriculum_version_id: uuid.UUID, semester_number: int
    ) -> Semester | None:
        statement = select(Semester).where(
            Semester.curriculum_version_id == curriculum_version_id,
            Semester.semester_number == semester_number,
        )
        return self._session.scalars(statement).first()

    def add(self, semester: Semester) -> Semester:
        self._session.add(semester)
        self._session.flush()
        return semester
