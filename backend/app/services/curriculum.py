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
    CourseType,
    Curriculum,
    CurriculumStatus,
    CurriculumVersion,
    Semester,
    VersionStatus,
)
from app.db.models.audit import AuditLog
from app.db.models.user import utc_now
from app.repositories.academic import CourseTypeRepository, ProgramRepository
from app.repositories.audit import AuditLogRepository
from app.repositories.courses import CourseOutcomeRepository, CourseRepository
from app.repositories.curricula import (
    CurriculumRepository,
    CurriculumVersionRepository,
    SemesterRepository,
)
from app.schemas.course import CourseCreate, CourseResponse, CourseUpdate
from app.schemas.course_outcome import (
    CourseOutcomeCreate,
    CourseOutcomeResponse,
    CourseOutcomeUpdate,
)
from app.schemas.curriculum import (
    CurriculumCreate,
    CurriculumDetailResponse,
    CurriculumResponse,
    CurriculumUpdate,
    CurriculumVersionResponse,
    CurriculumVersionSummary,
    FieldChange,
    ModifiedCourse,
    VersionComparisonResponse,
    VersionCreateRequest,
    VersionStatusUpdateRequest,
)

ALLOWED_STATUS_TRANSITIONS: dict[VersionStatus, set[VersionStatus]] = {
    VersionStatus.DRAFT: {VersionStatus.UNDER_REVIEW},
    VersionStatus.UNDER_REVIEW: {VersionStatus.DRAFT, VersionStatus.APPROVED},
    VersionStatus.APPROVED: {VersionStatus.PUBLISHED},
    VersionStatus.PUBLISHED: {VersionStatus.ARCHIVED},
    VersionStatus.ARCHIVED: set(),
}

LOCKED_FOR_NEW_VERSION = {VersionStatus.DRAFT, VersionStatus.UNDER_REVIEW}
EDITABLE_FOR_NEW_VERSION = {
    VersionStatus.APPROVED,
    VersionStatus.PUBLISHED,
    VersionStatus.ARCHIVED,
}


def _course_snapshot(course: Course) -> dict[str, Any]:
    return {
        "course_code": course.course_code,
        "course_name": course.course_name,
        "course_type_code": course.course_type.code,
        "credits": float(course.credits),
        "semester_number": course.semester.semester_number,
        "contact_hours": course.contact_hours,
        "description": course.description,
        "syllabus": course.syllabus,
        "status": course.status,
    }


def _curriculum_snapshot(curriculum: Curriculum) -> dict[str, Any]:
    return {
        "academic_year": curriculum.academic_year,
        "regulation": curriculum.regulation,
        "title": curriculum.title,
        "description": curriculum.description,
        "duration_years": float(curriculum.duration_years),
        "status": curriculum.status,
    }


class CurriculumService:
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
        self._audit_logs = audit_logs

    def create_curriculum(
        self, actor_id: uuid.UUID, request: CurriculumCreate
    ) -> CurriculumDetailResponse:
        program = self._programs.get_by_id(request.program_id)
        if program is None:
            raise NotFoundError("Program not found")
        if (
            self._curricula.get_by_program_regulation(request.program_id, request.regulation)
            is not None
        ):
            raise ConflictError(
                "A curriculum with this regulation already exists for the program",
                "curriculum_exists",
            )

        course_types = self._resolve_course_types(request)
        curriculum = Curriculum(
            program_id=request.program_id,
            academic_year=request.academic_year,
            regulation=request.regulation,
            title=request.title,
            description=request.description,
            duration_years=request.duration_years,
            status=CurriculumStatus.ACTIVE.value,
            created_by=actor_id,
        )

        try:
            self._curricula.add(curriculum)
            version = CurriculumVersion(
                curriculum_id=curriculum.id,
                version_label="1.0",
                status=VersionStatus.DRAFT.value,
                created_by=actor_id,
            )
            self._versions.add(version)

            semesters: dict[int, Semester] = {}
            for semester_request in request.semesters:
                semester = Semester(
                    curriculum_version_id=version.id,
                    semester_number=semester_request.semester_number,
                    name=semester_request.name,
                    focus=semester_request.focus,
                )
                self._semesters.add(semester)
                semesters[semester.semester_number] = semester

            created_courses: list[Course] = []
            for course_request in request.courses:
                course = Course(
                    curriculum_version_id=version.id,
                    semester_id=semesters[course_request.semester_number].id,
                    course_code=course_request.course_code,
                    course_name=course_request.course_name,
                    course_type_id=course_types[course_request.course_type_code].id,
                    credits=course_request.credits,
                    contact_hours=course_request.contact_hours,
                    description=course_request.description,
                    syllabus=course_request.syllabus,
                    status=CourseStatus.ACTIVE.value,
                    created_by=actor_id,
                )
                self._courses.add(course)
                created_courses.append(course)

            self._audit(
                actor_id=actor_id,
                entity_type="curriculum",
                entity_id=curriculum.id,
                action="CREATE",
                curriculum_version_id=version.id,
                new_values={
                    **_curriculum_snapshot(curriculum),
                    "version_label": version.version_label,
                },
            )
            for course in created_courses:
                self._audit(
                    actor_id=actor_id,
                    entity_type="course",
                    entity_id=course.id,
                    action="CREATE",
                    curriculum_version_id=version.id,
                    new_values=_course_snapshot(course),
                )
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise ConflictError(
                "Curriculum could not be created because of conflicting data",
                "curriculum_conflict",
            ) from exc

        return self.get_curriculum(curriculum.id)

    def _resolve_course_types(self, request: CurriculumCreate) -> dict[str, CourseType]:
        resolved: dict[str, CourseType] = {}
        for course_request in request.courses:
            if course_request.course_type_code in resolved:
                continue
            course_type = self._resolve_course_type(course_request.course_type_code)
            resolved[course_request.course_type_code] = course_type
        return resolved

    def _resolve_course_type(self, course_type_code: str) -> CourseType:
        course_type = self._course_types.get_by_code(course_type_code)
        if course_type is None or not course_type.is_active:
            raise BadRequestError(
                f"Unknown or inactive course type: {course_type_code}",
                "invalid_course_type",
            )
        return course_type

    def list_curricula(self) -> list[CurriculumResponse]:
        return [
            CurriculumResponse.from_model(curriculum, self._latest(curriculum.id))
            for curriculum in self._curricula.list()
        ]

    def get_curriculum(self, curriculum_id: uuid.UUID) -> CurriculumDetailResponse:
        curriculum = self._get_curriculum_or_404(curriculum_id)
        versions = self._versions.list_by_curriculum(curriculum_id)
        return CurriculumDetailResponse.from_curriculum(curriculum, versions)

    def update_curriculum(
        self,
        actor_id: uuid.UUID,
        curriculum_id: uuid.UUID,
        request: CurriculumUpdate,
    ) -> CurriculumDetailResponse:
        curriculum = self._get_curriculum_or_404(curriculum_id)
        latest = self._versions.get_latest(curriculum_id)
        if latest is not None and latest.status != VersionStatus.DRAFT.value:
            raise ConflictError(
                "This curriculum has no editable draft. "
                "Create a new version before making changes.",
                "version_not_editable",
            )

        changes = request.model_fields_set
        if not changes:
            return self.get_curriculum(curriculum_id)

        if "regulation" in changes and request.regulation is not None:
            duplicate = self._curricula.get_by_program_regulation(
                curriculum.program_id, request.regulation
            )
            if duplicate is not None and duplicate.id != curriculum.id:
                raise ConflictError(
                    "A curriculum with this regulation already exists for the program",
                    "curriculum_exists",
                )

        old_values = _curriculum_snapshot(curriculum)
        for field in ("academic_year", "regulation", "title", "description", "duration_years"):
            if field in changes:
                setattr(curriculum, field, getattr(request, field))

        try:
            self._audit(
                actor_id=actor_id,
                entity_type="curriculum",
                entity_id=curriculum.id,
                action="UPDATE",
                curriculum_version_id=latest.id if latest is not None else None,
                old_values=old_values,
                new_values=_curriculum_snapshot(curriculum),
            )
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise ConflictError(
                "Curriculum could not be updated because of conflicting data",
                "curriculum_conflict",
            ) from exc

        return self.get_curriculum(curriculum_id)

    def list_versions(self, curriculum_id: uuid.UUID) -> list[CurriculumVersionResponse]:
        self._get_curriculum_or_404(curriculum_id)
        return [
            CurriculumVersionResponse.from_model(version)
            for version in self._versions.list_by_curriculum(curriculum_id)
        ]

    def get_version(
        self, curriculum_id: uuid.UUID, version_id: uuid.UUID
    ) -> CurriculumVersionResponse:
        version = self._get_version_or_404(curriculum_id, version_id)
        return CurriculumVersionResponse.from_model(version)

    def create_version(
        self,
        actor_id: uuid.UUID,
        curriculum_id: uuid.UUID,
        request: VersionCreateRequest,
    ) -> CurriculumVersionResponse:
        self._get_curriculum_or_404(curriculum_id)
        source = self._versions.get_latest(curriculum_id)
        if source is None:
            raise NotFoundError("Curriculum has no versions to copy")
        source_status = VersionStatus(source.status)
        if source_status in LOCKED_FOR_NEW_VERSION:
            raise ConflictError(
                "A new version can only be created from an approved or published version.",
                "version_not_finalized",
            )
        if source_status not in EDITABLE_FOR_NEW_VERSION:
            raise ConflictError(
                "The current version is not finalized, so it cannot be versioned.",
                "version_not_finalized",
            )

        version_label = request.version_label or self._next_version_label(source)
        if self._versions.get_by_label(curriculum_id, version_label) is not None:
            raise ConflictError(
                f"Version {version_label} already exists for this curriculum",
                "version_exists",
            )

        version = CurriculumVersion(
            curriculum_id=curriculum_id,
            version_label=version_label,
            status=VersionStatus.DRAFT.value,
            previous_version_id=source.id,
            change_summary=request.change_summary,
            created_by=actor_id,
        )

        try:
            self._versions.add(version)
            semester_map: dict[uuid.UUID, Semester] = {}
            for source_semester in sorted(source.semesters, key=lambda item: item.semester_number):
                semester = Semester(
                    curriculum_version_id=version.id,
                    semester_number=source_semester.semester_number,
                    name=source_semester.name,
                )
                self._semesters.add(semester)
                semester_map[source_semester.id] = semester

            for source_course in source.courses:
                if source_course.status != CourseStatus.ACTIVE.value:
                    continue
                self._courses.add(
                    Course(
                        curriculum_version_id=version.id,
                        semester_id=semester_map[source_course.semester_id].id,
                        course_code=source_course.course_code,
                        course_name=source_course.course_name,
                        course_type_id=source_course.course_type_id,
                        credits=source_course.credits,
                        contact_hours=source_course.contact_hours,
                        description=source_course.description,
                        syllabus=source_course.syllabus,
                        status=CourseStatus.ACTIVE.value,
                        created_by=actor_id,
                    )
                )

            self._audit(
                actor_id=actor_id,
                entity_type="curriculum_version",
                entity_id=version.id,
                action="CREATE",
                curriculum_version_id=version.id,
                new_values={
                    "version_label": version.version_label,
                    "previous_version_id": str(source.id),
                    "change_summary": version.change_summary,
                },
            )
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise ConflictError(
                "The new curriculum version could not be created",
                "version_conflict",
            ) from exc

        return self.get_version(curriculum_id, version.id)

    def update_version_status(
        self,
        actor_id: uuid.UUID,
        curriculum_id: uuid.UUID,
        version_id: uuid.UUID,
        request: VersionStatusUpdateRequest,
    ) -> CurriculumVersionResponse:
        version = self._get_version_or_404(curriculum_id, version_id)
        current_status = VersionStatus(version.status)
        target_status = request.status
        if target_status == current_status:
            return CurriculumVersionResponse.from_model(version)
        if target_status not in ALLOWED_STATUS_TRANSITIONS[current_status]:
            raise ConflictError(
                f"Cannot change version status from {current_status.value} "
                f"to {target_status.value}",
                "invalid_status_transition",
            )

        version.status = target_status.value
        if target_status == VersionStatus.PUBLISHED:
            version.published_by = actor_id
            version.published_at = utc_now()
            for other in self._versions.list_by_curriculum(curriculum_id):
                if other.id != version.id and other.status == VersionStatus.PUBLISHED.value:
                    other.status = VersionStatus.ARCHIVED.value

        self._audit(
            actor_id=actor_id,
            entity_type="curriculum_version",
            entity_id=version.id,
            action="STATUS_CHANGE",
            curriculum_version_id=version.id,
            old_values={"status": current_status.value},
            new_values={"status": target_status.value},
        )
        self._session.commit()
        return CurriculumVersionResponse.from_model(version)

    def compare_versions(
        self,
        curriculum_id: uuid.UUID,
        base_version_id: uuid.UUID,
        target_version_id: uuid.UUID,
    ) -> VersionComparisonResponse:
        base = self._get_version_or_404(curriculum_id, base_version_id)
        target = self._get_version_or_404(curriculum_id, target_version_id)

        base_courses = {
            course.course_code: course
            for course in base.courses
            if course.status == CourseStatus.ACTIVE.value
        }
        target_courses = {
            course.course_code: course
            for course in target.courses
            if course.status == CourseStatus.ACTIVE.value
        }

        added_codes = sorted(set(target_courses) - set(base_courses))
        removed_codes = sorted(set(base_courses) - set(target_courses))
        common_codes = sorted(set(base_courses) & set(target_courses))

        modified_courses: list[ModifiedCourse] = []
        for code in common_codes:
            before_course = base_courses[code]
            after_course = target_courses[code]
            comparisons = (
                ("course_name", before_course.course_name, after_course.course_name),
                (
                    "course_type_code",
                    before_course.course_type.code,
                    after_course.course_type.code,
                ),
                ("credits", float(before_course.credits), float(after_course.credits)),
                (
                    "semester_number",
                    before_course.semester.semester_number,
                    after_course.semester.semester_number,
                ),
                (
                    "contact_hours",
                    before_course.contact_hours,
                    after_course.contact_hours,
                ),
                ("description", before_course.description, after_course.description),
                ("syllabus", before_course.syllabus, after_course.syllabus),
            )
            changes = {
                field: FieldChange(before=before, after=after)
                for field, before, after in comparisons
                if before != after
            }
            if changes:
                modified_courses.append(
                    ModifiedCourse(
                        course_code=code,
                        course_name=after_course.course_name,
                        changes=changes,
                    )
                )

        return VersionComparisonResponse(
            curriculum_id=curriculum_id,
            base_version=CurriculumVersionSummary.from_model(base),
            target_version=CurriculumVersionSummary.from_model(target),
            added_courses=[CourseResponse.from_model(target_courses[code]) for code in added_codes],
            removed_courses=[
                CourseResponse.from_model(base_courses[code]) for code in removed_codes
            ],
            modified_courses=modified_courses,
        )

    def add_course(
        self,
        actor_id: uuid.UUID,
        curriculum_id: uuid.UUID,
        version_id: uuid.UUID,
        request: CourseCreate,
    ) -> CourseResponse:
        version = self._get_version_or_404(curriculum_id, version_id)
        self._ensure_editable(version)

        course_type = self._resolve_course_type(request.course_type_code)
        semester = self._semesters.get_by_number(version_id, request.semester_number)
        if semester is None:
            raise BadRequestError(
                f"Semester {request.semester_number} does not belong to this curriculum version",
                "invalid_semester",
            )
        if self._courses.get_by_code(version_id, request.course_code) is not None:
            raise ConflictError(
                f"Course code {request.course_code} already exists in this version",
                "course_exists",
            )

        course = Course(
            curriculum_version_id=version.id,
            semester=semester,
            course_code=request.course_code,
            course_name=request.course_name,
            course_type=course_type,
            credits=request.credits,
            contact_hours=request.contact_hours,
            description=request.description,
            syllabus=request.syllabus,
            status=CourseStatus.ACTIVE.value,
            created_by=actor_id,
        )
        try:
            self._courses.add(course)
            self._audit(
                actor_id=actor_id,
                entity_type="course",
                entity_id=course.id,
                action="CREATE",
                curriculum_version_id=version.id,
                new_values=_course_snapshot(course),
            )
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise ConflictError(
                f"Course code {request.course_code} already exists in this version",
                "course_exists",
            ) from exc

        return CourseResponse.from_model(course)

    def update_course(
        self,
        actor_id: uuid.UUID,
        curriculum_id: uuid.UUID,
        version_id: uuid.UUID,
        course_id: uuid.UUID,
        request: CourseUpdate,
    ) -> CourseResponse:
        version = self._get_version_or_404(curriculum_id, version_id)
        self._ensure_editable(version)
        course = self._courses.get_by_id(course_id)
        if (
            course is None
            or course.curriculum_version_id != version.id
            or course.status != CourseStatus.ACTIVE.value
        ):
            raise NotFoundError("Course not found in this curriculum version")

        changes = request.model_fields_set
        if not changes:
            return CourseResponse.from_model(course)

        required_fields = ("course_name", "course_type_code", "credits", "semester_number")
        for field in required_fields:
            if field in changes and getattr(request, field) is None:
                raise BadRequestError(
                    f"{field.replace('_', ' ').title()} cannot be empty",
                    "invalid_course",
                )

        old_values = _course_snapshot(course)
        if "course_name" in changes:
            course.course_name = request.course_name
        if "course_type_code" in changes:
            course.course_type = self._resolve_course_type(request.course_type_code)
        if "credits" in changes:
            course.credits = request.credits
        if "semester_number" in changes:
            semester = self._semesters.get_by_number(version.id, request.semester_number)
            if semester is None:
                raise BadRequestError(
                    f"Semester {request.semester_number} does not belong to this "
                    "curriculum version",
                    "invalid_semester",
                )
            course.semester = semester
        if "contact_hours" in changes:
            course.contact_hours = request.contact_hours
        if "description" in changes:
            course.description = request.description
        if "syllabus" in changes:
            course.syllabus = request.syllabus
        course.updated_by = actor_id

        try:
            self._audit(
                actor_id=actor_id,
                entity_type="course",
                entity_id=course.id,
                action="UPDATE",
                curriculum_version_id=version.id,
                old_values=old_values,
                new_values=_course_snapshot(course),
            )
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise ConflictError(
                "The course could not be updated because of conflicting data",
                "course_conflict",
            ) from exc

        return CourseResponse.from_model(course)

    def list_course_outcomes(
        self,
        curriculum_id: uuid.UUID,
        version_id: uuid.UUID,
        course_id: uuid.UUID,
    ) -> list[CourseOutcomeResponse]:
        version = self._get_version_or_404(curriculum_id, version_id)
        course = self._get_active_course_or_404(version, course_id)
        return [
            CourseOutcomeResponse.from_model(outcome)
            for outcome in self._course_outcomes.list_by_course(course.id)
        ]

    def add_course_outcome(
        self,
        actor_id: uuid.UUID,
        curriculum_id: uuid.UUID,
        version_id: uuid.UUID,
        course_id: uuid.UUID,
        request: CourseOutcomeCreate,
    ) -> CourseOutcomeResponse:
        version = self._get_version_or_404(curriculum_id, version_id)
        self._ensure_editable(version)
        course = self._get_active_course_or_404(version, course_id)
        if self._course_outcomes.get_by_code(course.id, request.co_code) is not None:
            raise ConflictError(
                f"Course outcome {request.co_code} already exists for this course",
                "course_outcome_exists",
            )

        outcome = CourseOutcome(
            course_id=course.id,
            curriculum_version_id=version.id,
            co_code=request.co_code,
            description=request.description,
            status=CourseOutcomeStatus.ACTIVE.value,
            created_by=actor_id,
        )
        try:
            self._course_outcomes.add(outcome)
            self._audit(
                actor_id,
                "course_outcome",
                outcome.id,
                "CREATE",
                curriculum_version_id=version.id,
                new_values={
                    "course_id": str(course.id),
                    "co_code": outcome.co_code,
                    "description": outcome.description,
                    "status": outcome.status,
                },
            )
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise ConflictError(
                f"Course outcome {request.co_code} already exists for this course",
                "course_outcome_exists",
            ) from exc

        return CourseOutcomeResponse.from_model(outcome)

    def update_course_outcome(
        self,
        actor_id: uuid.UUID,
        curriculum_id: uuid.UUID,
        version_id: uuid.UUID,
        course_id: uuid.UUID,
        outcome_id: uuid.UUID,
        request: CourseOutcomeUpdate,
    ) -> CourseOutcomeResponse:
        version = self._get_version_or_404(curriculum_id, version_id)
        self._ensure_editable(version)
        course = self._get_active_course_or_404(version, course_id)
        outcome = self._course_outcomes.get_by_id(outcome_id)
        if (
            outcome is None
            or outcome.course_id != course.id
            or outcome.status != CourseOutcomeStatus.ACTIVE.value
        ):
            raise NotFoundError("Course outcome not found")

        changes = request.model_fields_set
        if not changes:
            return CourseOutcomeResponse.from_model(outcome)

        old_values = {
            "co_code": outcome.co_code,
            "description": outcome.description,
            "status": outcome.status,
        }
        if "co_code" in changes:
            if request.co_code is None:
                raise BadRequestError("Course outcome code cannot be empty")
            duplicate = self._course_outcomes.get_by_code(course.id, request.co_code)
            if duplicate is not None and duplicate.id != outcome.id:
                raise ConflictError(
                    f"Course outcome {request.co_code} already exists for this course",
                    "course_outcome_exists",
                )
            outcome.co_code = request.co_code
        if "description" in changes:
            if request.description is None:
                raise BadRequestError("Course outcome description cannot be empty")
            outcome.description = request.description
        outcome.updated_by = actor_id

        self._audit(
            actor_id,
            "course_outcome",
            outcome.id,
            "UPDATE",
            curriculum_version_id=version.id,
            old_values=old_values,
            new_values={
                "co_code": outcome.co_code,
                "description": outcome.description,
                "status": outcome.status,
            },
        )
        try:
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise ConflictError(
                "Course outcome could not be updated because of conflicting data",
                "course_outcome_conflict",
            ) from exc

        return CourseOutcomeResponse.from_model(outcome)

    def remove_course_outcome(
        self,
        actor_id: uuid.UUID,
        curriculum_id: uuid.UUID,
        version_id: uuid.UUID,
        course_id: uuid.UUID,
        outcome_id: uuid.UUID,
    ) -> None:
        version = self._get_version_or_404(curriculum_id, version_id)
        self._ensure_editable(version)
        course = self._get_active_course_or_404(version, course_id)
        outcome = self._course_outcomes.get_by_id(outcome_id)
        if (
            outcome is None
            or outcome.course_id != course.id
            or outcome.status != CourseOutcomeStatus.ACTIVE.value
        ):
            raise NotFoundError("Course outcome not found")

        old_values = {
            "co_code": outcome.co_code,
            "description": outcome.description,
            "status": outcome.status,
        }
        outcome.status = CourseOutcomeStatus.INACTIVE.value
        outcome.updated_by = actor_id
        self._audit(
            actor_id,
            "course_outcome",
            outcome.id,
            "REMOVE",
            curriculum_version_id=version.id,
            old_values=old_values,
            new_values={"status": outcome.status},
        )
        self._session.commit()

    def remove_course(
        self,
        actor_id: uuid.UUID,
        curriculum_id: uuid.UUID,
        version_id: uuid.UUID,
        course_id: uuid.UUID,
        force: bool = False,
    ) -> None:
        version = self._get_version_or_404(curriculum_id, version_id)
        self._ensure_editable(version)
        course = self._courses.get_by_id(course_id)
        if (
            course is None
            or course.curriculum_version_id != version.id
            or course.status != CourseStatus.ACTIVE.value
        ):
            raise NotFoundError("Course not found in this curriculum version")

        dependencies = self._course_dependencies(course)
        if dependencies and not force:
            raise ConflictError(
                "This course is referenced by other curriculum components: "
                + ", ".join(dependencies),
                "course_has_dependencies",
            )

        old_values = _course_snapshot(course)
        course.status = CourseStatus.REMOVED.value
        course.removed_by = actor_id
        course.removed_at = utc_now()
        course.updated_by = actor_id

        self._audit(
            actor_id=actor_id,
            entity_type="course",
            entity_id=course.id,
            action="REMOVE",
            curriculum_version_id=version.id,
            old_values=old_values,
            new_values={"status": CourseStatus.REMOVED.value},
        )
        self._session.commit()

    def _course_dependencies(self, course: Course) -> list[str]:
        dependencies: list[str] = []
        referenced = self._courses.get_referencing_prerequisites(course.id)
        dependencies.extend(
            f"prerequisite of {referencing.course_code}" for referencing in referenced
        )
        return dependencies

    def _get_active_course_or_404(self, version: CurriculumVersion, course_id: uuid.UUID) -> Course:
        course = self._courses.get_by_id(course_id)
        if (
            course is None
            or course.curriculum_version_id != version.id
            or course.status != CourseStatus.ACTIVE.value
        ):
            raise NotFoundError("Course not found in this curriculum version")
        return course

    def _ensure_editable(self, version: CurriculumVersion) -> None:
        if version.status != VersionStatus.DRAFT.value:
            raise ConflictError(
                "Only DRAFT curriculum versions can be modified",
                "version_not_editable",
            )

    def _next_version_label(self, source: CurriculumVersion) -> str:
        try:
            major, minor = source.version_label.split(".", maxsplit=1)
            return f"{int(major)}.{int(minor) + 1}"
        except (TypeError, ValueError):
            return "1.1"

    def _audit(
        self,
        actor_id: uuid.UUID,
        entity_type: str,
        entity_id: uuid.UUID,
        action: str,
        curriculum_version_id: uuid.UUID | None = None,
        old_values: dict[str, Any] | None = None,
        new_values: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
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
                log_metadata=metadata,
            )
        )

    def _get_curriculum_or_404(self, curriculum_id: uuid.UUID) -> Curriculum:
        curriculum = self._curricula.get_by_id(curriculum_id)
        if curriculum is None:
            raise NotFoundError("Curriculum not found")
        return curriculum

    def _get_version_or_404(
        self, curriculum_id: uuid.UUID, version_id: uuid.UUID
    ) -> CurriculumVersion:
        self._get_curriculum_or_404(curriculum_id)
        version = self._versions.get_by_id(version_id)
        if version is None or version.curriculum_id != curriculum_id:
            raise NotFoundError("Curriculum version not found")
        return version

    def _latest(self, curriculum_id: uuid.UUID) -> CurriculumVersion | None:
        return self._versions.get_latest(curriculum_id)
