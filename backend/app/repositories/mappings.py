import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.mappings import (
    CoPoMapping,
    CoPoMappingVersion,
    CurriculumVersionProgramOutcome,
    MappingLevel,
    MappingStatus,
)


class MappingLevelRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, level_id: uuid.UUID) -> MappingLevel | None:
        return self._session.get(MappingLevel, level_id)

    def get_by_code(self, code: str) -> MappingLevel | None:
        statement = select(MappingLevel).where(
            func.upper(MappingLevel.code) == code.strip().upper(),
            MappingLevel.is_active.is_(True),
        )
        return self._session.scalars(statement).first()

    def list_active(self) -> list[MappingLevel]:
        statement = (
            select(MappingLevel)
            .where(MappingLevel.is_active.is_(True))
            .order_by(MappingLevel.sort_order, MappingLevel.code)
        )
        return list(self._session.scalars(statement))


class CurriculumVersionProgramOutcomeRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(
        self, curriculum_version_id: uuid.UUID, program_outcome_id: uuid.UUID
    ) -> CurriculumVersionProgramOutcome | None:
        return self._session.get(
            CurriculumVersionProgramOutcome,
            (curriculum_version_id, program_outcome_id),
        )

    def add(self, pin: CurriculumVersionProgramOutcome) -> CurriculumVersionProgramOutcome:
        self._session.add(pin)
        self._session.flush()
        return pin


class CoPoMappingRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, mapping_id: uuid.UUID) -> CoPoMapping | None:
        return self._session.get(CoPoMapping, mapping_id)

    def get_active(
        self,
        curriculum_version_id: uuid.UUID,
        course_outcome_id: uuid.UUID,
        program_outcome_id: uuid.UUID,
    ) -> CoPoMapping | None:
        statement = select(CoPoMapping).where(
            CoPoMapping.curriculum_version_id == curriculum_version_id,
            CoPoMapping.course_outcome_id == course_outcome_id,
            CoPoMapping.program_outcome_id == program_outcome_id,
            CoPoMapping.status == MappingStatus.ACTIVE.value,
        )
        return self._session.scalars(statement).first()

    def list_by_version(
        self,
        curriculum_version_id: uuid.UUID,
        course_outcome_id: uuid.UUID | None = None,
        program_outcome_id: uuid.UUID | None = None,
    ) -> list[CoPoMapping]:
        statement = select(CoPoMapping).where(
            CoPoMapping.curriculum_version_id == curriculum_version_id,
            CoPoMapping.status == MappingStatus.ACTIVE.value,
        )
        if course_outcome_id is not None:
            statement = statement.where(CoPoMapping.course_outcome_id == course_outcome_id)
        if program_outcome_id is not None:
            statement = statement.where(CoPoMapping.program_outcome_id == program_outcome_id)
        return list(self._session.scalars(statement))

    def add(self, mapping: CoPoMapping) -> CoPoMapping:
        self._session.add(mapping)
        self._session.flush()
        return mapping


class CoPoMappingVersionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, version_id: uuid.UUID) -> CoPoMappingVersion | None:
        return self._session.get(CoPoMappingVersion, version_id)

    def list_by_mapping(self, mapping_id: uuid.UUID) -> list[CoPoMappingVersion]:
        statement = (
            select(CoPoMappingVersion)
            .where(CoPoMappingVersion.mapping_id == mapping_id)
            .order_by(CoPoMappingVersion.version_number)
        )
        return list(self._session.scalars(statement))

    def next_version_number(self, mapping_id: uuid.UUID) -> int:
        statement = select(func.max(CoPoMappingVersion.version_number)).where(
            CoPoMappingVersion.mapping_id == mapping_id
        )
        current = self._session.scalar(statement)
        return int(current or 0) + 1

    def add(self, version: CoPoMappingVersion) -> CoPoMappingVersion:
        self._session.add(version)
        self._session.flush()
        return version
