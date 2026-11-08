import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.db.models import (
    CoPoMapping,
    CoursePrerequisite,
    Curriculum,
    CurriculumVersion,
    CurriculumVersionPeo,
    CurriculumVersionProgramOutcome,
    PeoVersion,
    ProgramOutcomeVersion,
)
from app.services.knowledge_graph import KnowledgeGraphRepository


def _value(value: Any) -> Any:
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    return value


class KnowledgeGraphProjectionService:
    def __init__(self, session: Session, graph: KnowledgeGraphRepository) -> None:
        self._session = session
        self._graph = graph

    def rebuild(self, curriculum_id: uuid.UUID, version_id: uuid.UUID) -> dict[str, Any]:
        version = self._session.scalar(
            select(CurriculumVersion).where(
                CurriculumVersion.id == version_id,
                CurriculumVersion.curriculum_id == curriculum_id,
            )
        )
        if version is None:
            raise NotFoundError("Curriculum version not found")

        curriculum = self._session.get(Curriculum, curriculum_id)
        program = curriculum.program
        version_key = str(version.id)
        nodes: list[dict[str, Any]] = [
            {"label": "Program", "id": str(program.id), "code": program.code, "name": program.name},
            {
                "label": "Curriculum",
                "id": str(curriculum.id),
                "program_id": str(program.id),
                "regulation": curriculum.regulation,
                "academic_year": curriculum.academic_year,
                "title": curriculum.title,
            },
            {
                "label": "CurriculumVersion",
                "id": version_key,
                "curriculum_version_id": version_key,
                "curriculum_id": str(curriculum.id),
                "version_label": version.version_label,
                "status": version.status,
            },
        ]
        relationships: list[dict[str, Any]] = []

        def edge(
            kind: str,
            source_label: str,
            source: uuid.UUID | str,
            target_label: str,
            target: uuid.UUID | str,
            **properties: Any,
        ):
            source_id = str(source)
            target_id = str(target)
            relationships.append(
                {
                    "type": kind,
                    "id": f"{kind}:{source_id}:{target_id}",
                    "source_label": source_label,
                    "source_id": source_id,
                    "target_label": target_label,
                    "target_id": target_id,
                    "properties": {key: _value(value) for key, value in properties.items()},
                }
            )

        edge("HAS_VERSION", "Curriculum", curriculum.id, "CurriculumVersion", version.id)
        edge("FOR_PROGRAM", "Curriculum", curriculum.id, "Program", program.id)

        for semester in version.semesters:
            nodes.append(
                {
                    "label": "Semester",
                    "id": str(semester.id),
                    "curriculum_version_id": version_key,
                    "semester_number": semester.semester_number,
                    "name": semester.name,
                }
            )
            edge("HAS_SEMESTER", "CurriculumVersion", version.id, "Semester", semester.id)

        courses = list(version.courses)
        for course in courses:
            nodes.append(
                {
                    "label": "Course",
                    "id": str(course.id),
                    "curriculum_version_id": version_key,
                    "course_code": course.course_code,
                    "course_name": course.course_name,
                    "credits": _value(course.credits),
                    "status": course.status,
                }
            )
            edge("HAS_COURSE", "CurriculumVersion", version.id, "Course", course.id)
            edge("SCHEDULED_IN", "Course", course.id, "Semester", course.semester_id)
            for outcome in course.outcomes:
                nodes.append(
                    {
                        "label": "CourseOutcome",
                        "id": str(outcome.id),
                        "curriculum_version_id": version_key,
                        "co_code": outcome.co_code,
                        "description": outcome.description,
                        "status": outcome.status,
                    }
                )
                edge("HAS_OUTCOME", "Course", course.id, "CourseOutcome", outcome.id)

        prerequisites = self._session.scalars(
            select(CoursePrerequisite).where(CoursePrerequisite.curriculum_version_id == version.id)
        ).all()
        for item in prerequisites:
            edge(
                "PREREQUISITE_OF",
                "Course",
                item.prerequisite_course_id,
                "Course",
                item.target_course_id,
                status=item.status,
            )
            relationships[-1]["id"] = str(item.id)

        for pin in self._session.scalars(
            select(CurriculumVersionProgramOutcome).where(
                CurriculumVersionProgramOutcome.curriculum_version_id == version.id
            )
        ).all():
            outcome = pin.program_outcome
            outcome_version = self._session.get(
                ProgramOutcomeVersion, pin.program_outcome_version_id
            )
            nodes.append(
                {
                    "label": "ProgramOutcome",
                    "id": str(outcome.id),
                    "curriculum_version_id": version_key,
                    "program_id": str(outcome.program_id),
                    "po_code": outcome.po_code,
                    "description": outcome_version.description,
                    "outcome_version_id": str(outcome_version.id),
                    "status": outcome.status,
                }
            )
            edge("USES_PO", "CurriculumVersion", version.id, "ProgramOutcome", outcome.id)

        peo_pins = self._session.scalars(
            select(CurriculumVersionPeo).where(
                CurriculumVersionPeo.curriculum_version_id == version.id
            )
        ).all()
        for pin in peo_pins:
            outcome = pin.peo
            outcome_version = self._session.get(PeoVersion, pin.peo_version_id)
            nodes.append(
                {
                    "label": "PEO",
                    "id": str(outcome.id),
                    "curriculum_version_id": version_key,
                    "program_id": str(outcome.program_id),
                    "peo_code": outcome.peo_code,
                    "description": outcome_version.description,
                    "outcome_version_id": str(outcome_version.id),
                    "status": outcome.status,
                }
            )
            edge("USES_PEO", "CurriculumVersion", version.id, "PEO", outcome.id)

        for mapping in self._session.scalars(
            select(CoPoMapping).where(CoPoMapping.curriculum_version_id == version.id)
        ).all():
            current = max(mapping.versions, key=lambda item: item.version_number, default=None)
            properties: dict[str, Any] = {"status": mapping.status}
            if current:
                properties.update(
                    mapping_version_id=str(current.id),
                    mapping_version_status=current.status,
                    level_code=current.mapping_level.code,
                    level_value=current.mapping_level.numeric_value,
                )
            relationships.append(
                {
                    "type": "CONTRIBUTES_TO",
                    "id": str(mapping.id),
                    "source_label": "CourseOutcome",
                    "source_id": str(mapping.course_outcome_id),
                    "target_label": "ProgramOutcome",
                    "target_id": str(mapping.program_outcome_id),
                    "properties": properties,
                }
            )

        snapshot = {"nodes": nodes, "relationships": relationships}
        self._graph.replace_version(version.id, snapshot)
        return {
            "curriculum_id": str(curriculum_id),
            "curriculum_version_id": version_key,
            "node_count": len(nodes),
            "relationship_count": len(relationships),
        }

    def read(
        self, curriculum_id: uuid.UUID, version_id: uuid.UUID, limit: int = 1000
    ) -> dict[str, Any]:
        version = self._session.scalar(
            select(CurriculumVersion.id).where(
                CurriculumVersion.id == version_id,
                CurriculumVersion.curriculum_id == curriculum_id,
            )
        )
        if version is None:
            raise NotFoundError("Curriculum version not found")
        return self._graph.get_version_graph(version_id, limit=limit)
