from sqlalchemy import event, select
from sqlalchemy.orm import Session

from app.db.models import (
    CoPoMapping,
    CoPoMappingVersion,
    Course,
    CourseOutcome,
    CoursePrerequisite,
    Curriculum,
    CurriculumVersion,
    CurriculumVersionPeo,
    CurriculumVersionProgramOutcome,
    GraphProjectionJob,
    PeoVersion,
    Program,
    ProgramEducationalObjective,
    ProgramOutcome,
    ProgramOutcomeVersion,
    Semester,
)


def _versions_for(session: Session, entity: object) -> set:
    direct_id = getattr(entity, "curriculum_version_id", None)
    if direct_id:
        return {direct_id}
    if isinstance(entity, CurriculumVersion):
        return {entity.id} if entity.id else set()
    if isinstance(entity, Curriculum):
        if not entity.id:
            return set()
        return set(
            session.scalars(
                select(CurriculumVersion.id).where(CurriculumVersion.curriculum_id == entity.id)
            ).all()
        )
    if isinstance(entity, Program):
        return set(
            session.scalars(
                select(CurriculumVersion.id)
                .join(Curriculum, Curriculum.id == CurriculumVersion.curriculum_id)
                .where(Curriculum.program_id == entity.id)
            ).all()
        )
    if isinstance(entity, (ProgramOutcome, ProgramOutcomeVersion)):
        outcome_id = entity.id if isinstance(entity, ProgramOutcome) else entity.program_outcome_id
        pin_query = select(CurriculumVersionProgramOutcome.curriculum_version_id).where(
            CurriculumVersionProgramOutcome.program_outcome_id == outcome_id
        )
        if isinstance(entity, ProgramOutcomeVersion):
            pin_query = pin_query.where(
                CurriculumVersionProgramOutcome.program_outcome_version_id == entity.id
            )
        return set(session.scalars(pin_query).all())
    if isinstance(entity, (ProgramEducationalObjective, PeoVersion)):
        peo_id = entity.id if isinstance(entity, ProgramEducationalObjective) else entity.peo_id
        pin_query = select(CurriculumVersionPeo.curriculum_version_id).where(
            CurriculumVersionPeo.peo_id == peo_id
        )
        if isinstance(entity, PeoVersion):
            pin_query = pin_query.where(CurriculumVersionPeo.peo_version_id == entity.id)
        return set(session.scalars(pin_query).all())
    if isinstance(entity, CoPoMappingVersion):
        mapping = session.get(CoPoMapping, entity.mapping_id)
        return {mapping.curriculum_version_id} if mapping else set()
    return set()


def _before_flush(session: Session, _flush_context: object, _instances: object) -> None:
    touched = session.info.setdefault("graph_projection_touched", [])
    for entity in session.new.union(session.dirty).union(session.deleted):
        if isinstance(entity, GraphProjectionJob):
            continue
        if isinstance(
            entity,
            (
                CoPoMapping,
                CoPoMappingVersion,
                Course,
                CourseOutcome,
                CoursePrerequisite,
                Curriculum,
                CurriculumVersion,
                CurriculumVersionPeo,
                CurriculumVersionProgramOutcome,
                PeoVersion,
                Program,
                ProgramEducationalObjective,
                ProgramOutcome,
                ProgramOutcomeVersion,
                Semester,
            ),
        ):
            if entity not in touched:
                touched.append(entity)


def _after_flush_postexec(session: Session, _flush_context: object) -> None:
    touched = session.info.pop("graph_projection_touched", [])
    version_ids: set = set()
    for entity in touched:
        version_ids.update(_versions_for(session, entity))
    for version_id in version_ids:
        session.add(GraphProjectionJob(curriculum_version_id=version_id))


event.listen(Session, "before_flush", _before_flush)
event.listen(Session, "after_flush_postexec", _after_flush_postexec)
