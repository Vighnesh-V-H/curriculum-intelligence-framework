import uuid
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import BadRequestError, ConflictError, NotFoundError
from app.db.models.academic import (
    Course,
    CourseOutcome,
    CourseOutcomeStatus,
    CourseStatus,
    Curriculum,
    CurriculumStatus,
    CurriculumVersion,
    Program,
    Semester,
    VersionStatus,
)
from app.db.models.audit import AuditLog
from app.db.models.mappings import (
    CoPoMapping,
    CoPoMappingVersion,
    CurriculumVersionPeo,
    CurriculumVersionProgramOutcome,
    MappingStatus,
    MappingVersionStatus,
)
from app.db.models.outcomes import (
    OutcomeStatus,
    OutcomeVersionStatus,
    PeoVersion,
    ProgramEducationalObjective,
    ProgramOutcome,
    ProgramOutcomeVersion,
)
from app.db.models.user import User, utc_now
from app.repositories.academic import CourseTypeRepository, ProgramRepository
from app.repositories.audit import AuditLogRepository
from app.repositories.courses import CourseOutcomeRepository, CourseRepository
from app.repositories.curricula import (
    CurriculumRepository,
    CurriculumVersionRepository,
    SemesterRepository,
)
from app.repositories.mappings import (
    CoPoMappingRepository,
    CoPoMappingVersionRepository,
    CurriculumVersionPeoRepository,
    CurriculumVersionProgramOutcomeRepository,
    MappingLevelRepository,
)
from app.repositories.outcomes import OutcomeRepository, OutcomeVersionRepository
from app.schemas.curriculum_draft import CurriculumDraftSaveRequest


class CurriculumDraftPersistenceService:
    def __init__(
        self,
        session: Session,
        programs: ProgramRepository,
        course_types: CourseTypeRepository,
        curricula: CurriculumRepository,
        versions: CurriculumVersionRepository,
        semesters: SemesterRepository,
        courses: CourseRepository,
        course_outcomes: CourseOutcomeRepository,
        program_outcomes: OutcomeRepository,
        program_outcome_versions: OutcomeVersionRepository,
        peos: OutcomeRepository,
        peo_versions: OutcomeVersionRepository,
        mapping_levels: MappingLevelRepository,
        version_outcomes: CurriculumVersionProgramOutcomeRepository,
        version_peos: CurriculumVersionPeoRepository,
        mappings: CoPoMappingRepository,
        mapping_versions: CoPoMappingVersionRepository,
        audit_logs: AuditLogRepository,
    ) -> None:
        self._session = session
        self._programs = programs
        self._course_types = course_types
        self._curricula = curricula
        self._versions = versions
        self._semesters = semesters
        self._courses = courses
        self._course_outcomes = course_outcomes
        self._program_outcomes = program_outcomes
        self._program_outcome_versions = program_outcome_versions
        self._peos = peos
        self._peo_versions = peo_versions
        self._mapping_levels = mapping_levels
        self._version_outcomes = version_outcomes
        self._version_peos = version_peos
        self._mappings = mappings
        self._mapping_versions = mapping_versions
        self._audit_logs = audit_logs

    def save(self, actor: User, request: CurriculumDraftSaveRequest) -> uuid.UUID:
        program = self._programs.get_by_id(request.program_id)
        if program is None:
            raise NotFoundError("Program not found")
        types = self._resolve_course_types(request)
        levels = {level.numeric_value: level for level in self._mapping_levels.list_active()}
        missing_levels = {mapping.level for mapping in request.draft.mappings} - levels.keys()
        if missing_levels:
            raise BadRequestError(
                "No active mapping level is configured for: "
                + ", ".join(str(value) for value in sorted(missing_levels)),
                "mapping_level_unavailable",
            )

        curriculum = Curriculum(
            program_id=program.id,
            academic_year=request.academic_year,
            regulation=request.regulation,
            title=request.title or request.draft.program.name or program.name,
            description=request.draft.program.summary,
            duration_years=program.duration_years,
            status=CurriculumStatus.ACTIVE.value,
            created_by=actor.id,
        )
        try:
            self._curricula.add(curriculum)
            version = CurriculumVersion(
                curriculum_id=curriculum.id,
                version_label="1.0",
                status=VersionStatus.APPROVED.value,
                change_summary="Created directly from AI-generated curriculum content.",
                created_by=actor.id,
            )
            self._versions.add(version)

            semesters: dict[int, Semester] = {}
            for item in request.draft.semesters:
                semester = Semester(
                    curriculum_version_id=version.id,
                    semester_number=item.semester_number,
                    name=item.semester_name,
                    focus=item.focus,
                )
                self._semesters.add(semester)
                semesters[semester.semester_number] = semester

            program_outcome_rows = self._persist_outcomes(
                actor.id,
                program,
                request.draft.pos,
                self._program_outcomes,
                self._program_outcome_versions,
                ProgramOutcome,
                ProgramOutcomeVersion,
                "po_code",
                "program_outcome",
            )
            peo_rows = self._persist_outcomes(
                actor.id,
                program,
                request.draft.peos,
                self._peos,
                self._peo_versions,
                ProgramEducationalObjective,
                PeoVersion,
                "peo_code",
                "peo",
            )
            for outcome, outcome_version in program_outcome_rows.values():
                self._version_outcomes.add(
                    CurriculumVersionProgramOutcome(
                        curriculum_version_id=version.id,
                        program_outcome_id=outcome.id,
                        program_outcome_version_id=outcome_version.id,
                        added_by=actor.id,
                    )
                )
            for peo, peo_version in peo_rows.values():
                self._version_peos.add(
                    CurriculumVersionPeo(
                        curriculum_version_id=version.id,
                        peo_id=peo.id,
                        peo_version_id=peo_version.id,
                        added_by=actor.id,
                    )
                )

            courses_by_code: dict[str, Course] = {}
            outcomes_by_key: dict[tuple[str, str], CourseOutcome] = {}
            for item in request.draft.semesters:
                for course_item in item.courses:
                    course_code = course_item.code.strip().upper()
                    course = Course(
                        curriculum_version_id=version.id,
                        semester_id=semesters[item.semester_number].id,
                        course_code=course_code,
                        course_name=course_item.title.strip(),
                        course_type_id=types[course_item.category.strip().casefold()].id,
                        credits=(
                            course_item.credits
                            if course_item.credits is not None
                            else request.credits_by_course_code[course_code]
                        ),
                        description=course_item.summary,
                        status=CourseStatus.ACTIVE.value,
                        created_by=actor.id,
                    )
                    self._courses.add(course)
                    courses_by_code[course_code] = course
                    self._audit(
                        actor.id,
                        "course",
                        course.id,
                        version.id,
                        "CREATE",
                        {
                            "course_code": course.course_code,
                            "course_name": course.course_name,
                            "semester_number": item.semester_number,
                            "course_type_id": str(course.course_type_id),
                            "credits": float(course.credits),
                        },
                    )
                    for co in course_item.outcomes:
                        outcome = CourseOutcome(
                            course_id=course.id,
                            curriculum_version_id=version.id,
                            co_code=co.code.strip().upper(),
                            description=co.statement.strip(),
                            status=CourseOutcomeStatus.ACTIVE.value,
                            created_by=actor.id,
                        )
                        self._course_outcomes.add(outcome)
                        outcomes_by_key[(course_code, outcome.co_code)] = outcome

            for mapping in request.draft.mappings:
                course_code = mapping.course_code.strip().upper()
                co_code = mapping.course_outcome_code.strip().upper()
                po_code = mapping.program_outcome_code.strip().upper()
                mapping_row = CoPoMapping(
                    curriculum_version_id=version.id,
                    course_outcome_id=outcomes_by_key[(course_code, co_code)].id,
                    program_outcome_id=program_outcome_rows[po_code][0].id,
                    status=MappingStatus.ACTIVE.value,
                    created_by=actor.id,
                )
                self._mappings.add(mapping_row)
                self._mapping_versions.add(
                    CoPoMappingVersion(
                        mapping_id=mapping_row.id,
                        version_number=1,
                        mapping_level_id=levels[mapping.level].id,
                        status=MappingVersionStatus.APPROVED.value,
                        approved_by=actor.id,
                        approved_at=utc_now(),
                        created_by=actor.id,
                    )
                )

            self._audit(
                actor.id,
                "curriculum",
                curriculum.id,
                version.id,
                "CREATE_FROM_AI_DRAFT",
                {
                    "academic_year": curriculum.academic_year,
                    "regulation": curriculum.regulation,
                    "title": curriculum.title,
                    "description": curriculum.description,
                    "version_label": version.version_label,
                    "course_count": len(courses_by_code),
                    "peo_count": len(peo_rows),
                    "po_count": len(program_outcome_rows),
                    "mapping_count": len(request.draft.mappings),
                },
            )
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise ConflictError(
                "The reviewed draft conflicts with existing curriculum or outcome data. "
                "No records were saved; check duplicate codes and try again.",
                "curriculum_draft_conflict",
            ) from exc
        except Exception:
            self._session.rollback()
            raise
        return curriculum.id

    def _resolve_course_types(self, request: CurriculumDraftSaveRequest) -> dict[str, Any]:
        result = {}
        for category, code in request.course_type_codes.items():
            course_type = self._course_types.get_by_code(code)
            if course_type is None or not course_type.is_active:
                raise BadRequestError(
                    f"Unknown or inactive course type: {code}", "invalid_course_type"
                )
            result[category] = course_type
        return result

    def _persist_outcomes(
        self,
        actor_id: uuid.UUID,
        program: Program,
        definitions: list[Any],
        outcomes: OutcomeRepository,
        versions: OutcomeVersionRepository,
        outcome_model: type[ProgramOutcome] | type[ProgramEducationalObjective],
        version_model: type[ProgramOutcomeVersion] | type[PeoVersion],
        code_field: str,
        entity_type: str,
    ) -> dict[str, tuple[Any, Any]]:
        rows: dict[str, tuple[Any, Any]] = {}
        for definition in definitions:
            code = definition.code.strip().upper()
            outcome = outcomes.get_by_code(program.id, code)
            if outcome is None:
                outcome = outcome_model(
                    program_id=program.id,
                    **{code_field: code},
                    status=OutcomeStatus.ACTIVE.value,
                    created_by=actor_id,
                )
                outcomes.add(outcome)
                version = version_model(
                    version_number=1,
                    description=definition.statement.strip(),
                    status=OutcomeVersionStatus.APPROVED.value,
                    approved_by=actor_id,
                    approved_at=utc_now(),
                    created_by=actor_id,
                )
                self._attach_version(outcome, version, entity_type)
                versions.add(version)
                self._audit(actor_id, entity_type, outcome.id, None, "CREATE", {code_field: code})
            else:
                existing_versions = versions.list_by_parent(outcome.id)
                if existing_versions:
                    version = existing_versions[-1]
                    version.description = definition.statement.strip()
                    version.status = OutcomeVersionStatus.APPROVED.value
                    version.approved_by = actor_id
                    version.approved_at = utc_now()
                else:
                    version = version_model(
                        version_number=1,
                        description=definition.statement.strip(),
                        status=OutcomeVersionStatus.APPROVED.value,
                        approved_by=actor_id,
                        approved_at=utc_now(),
                        created_by=actor_id,
                    )
                    self._attach_version(outcome, version, entity_type)
                    versions.add(version)
            rows[code] = (outcome, version)
        return rows

    def _attach_version(self, outcome: Any, version: Any, entity_type: str) -> None:
        if entity_type == "peo":
            version.program_educational_objective = outcome
        else:
            version.program_outcome = outcome

    def _audit(
        self,
        actor_id: uuid.UUID,
        entity_type: str,
        entity_id: uuid.UUID,
        version_id: uuid.UUID | None,
        action: str,
        values: dict[str, Any],
    ) -> None:
        self._audit_logs.add(
            AuditLog(
                entity_type=entity_type,
                entity_id=entity_id,
                action=action,
                actor_user_id=actor_id,
                curriculum_version_id=version_id,
                new_values=values,
            )
        )
