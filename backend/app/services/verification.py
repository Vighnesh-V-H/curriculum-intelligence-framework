import logging
import time
import uuid
from collections import deque
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.db.models.academic import (
    Course,
    CourseOutcomeStatus,
    CoursePrerequisite,
    CourseStatus,
    CurriculumVersion,
    PrerequisiteStatus,
    Semester,
)
from app.db.models.audit import AuditLog
from app.db.models.mappings import (
    CoPoMapping,
    CurriculumVersionProgramOutcome,
    MappingStatus,
    MappingVersionStatus,
)
from app.db.models.outcomes import OutcomeStatus
from app.db.models.user import utc_now
from app.db.models.verification import (
    FindingCategory,
    FindingSeverity,
    ReferenceEntityType,
    VerificationFinding,
    VerificationFindingReference,
    VerificationRun,
    VerificationRunStatus,
)
from app.repositories.audit import AuditLogRepository
from app.repositories.courses import CourseRepository
from app.repositories.curricula import (
    CurriculumRepository,
    CurriculumVersionRepository,
)
from app.repositories.prerequisites import CoursePrerequisiteRepository
from app.repositories.verification import (
    VerificationFindingRepository,
    VerificationRunRepository,
)
from app.schemas.verification import (
    FindingResponse,
    VerificationRunResponse,
)

ACTIVE_PREREQUISITE_STATUSES = (
    PrerequisiteStatus.PROPOSED.value,
    PrerequisiteStatus.APPROVED.value,
)
ANALYZED_PREREQUISITE_STATUSES = (
    PrerequisiteStatus.PROPOSED.value,
    PrerequisiteStatus.APPROVED.value,
    PrerequisiteStatus.REJECTED.value,
)

logger = logging.getLogger(__name__)

SEVERITY_ORDER = {
    FindingSeverity.INFO.value: 0,
    FindingSeverity.LOW.value: 1,
    FindingSeverity.MEDIUM.value: 2,
    FindingSeverity.HIGH.value: 3,
    FindingSeverity.CRITICAL.value: 4,
}


class _FindingDraft:
    """In-memory finding collected by the analyzer before persistence."""

    def __init__(
        self,
        category: FindingCategory,
        severity: FindingSeverity,
        title: str,
        description: str,
        evidence: str,
        recommendation: str,
        confidence: Decimal,
        course_ids: list[uuid.UUID] | None = None,
        prerequisite_ids: list[uuid.UUID] | None = None,
        semester_ids: list[uuid.UUID] | None = None,
        course_outcome_ids: list[uuid.UUID] | None = None,
        program_outcome_ids: list[uuid.UUID] | None = None,
    ) -> None:
        self.category = category
        self.severity = severity
        self.title = title
        self.description = description
        self.evidence = evidence
        self.recommendation = recommendation
        self.confidence = confidence
        self.course_ids = course_ids or []
        self.prerequisite_ids = prerequisite_ids or []
        self.semester_ids = semester_ids or []
        self.course_outcome_ids = course_outcome_ids or []
        self.program_outcome_ids = program_outcome_ids or []


def _detect_cycles(
    edges: list[tuple[uuid.UUID, uuid.UUID]],
) -> list[list[uuid.UUID]]:
    adjacency: dict[uuid.UUID, list[uuid.UUID]] = {}
    for source, destination in edges:
        adjacency.setdefault(source, []).append(destination)

    cycles: list[list[uuid.UUID]] = []
    seen: set[tuple[uuid.UUID, ...]] = set()
    for source, destination in edges:
        # A cycle through this edge exists when `destination` can reach
        # `source` without re-using the same edge.
        parent: dict[uuid.UUID, uuid.UUID | None] = {destination: None}
        queue: deque[uuid.UUID] = deque([destination])
        path_end: uuid.UUID | None = None
        while queue and path_end is None:
            node = queue.popleft()
            for neighbor in adjacency.get(node, []):
                if (node, neighbor) == (source, destination):
                    continue
                if neighbor in parent:
                    continue
                parent[neighbor] = node
                if neighbor == source:
                    path_end = node
                    break
                queue.append(neighbor)
        if path_end is None:
            continue

        # Reconstruct destination -> ... -> path_end, then close the loop.
        chain: list[uuid.UUID] = []
        cursor = path_end
        while cursor is not None:
            chain.append(cursor)
            cursor = parent[cursor]
        chain.reverse()  # [destination, ..., path_end]
        cycle = [source, *chain, source]
        rotation = _canonical_rotation(cycle)
        if rotation not in seen:
            seen.add(rotation)
            cycles.append(cycle)
    return cycles


def _canonical_rotation(nodes: list[uuid.UUID]) -> tuple[uuid.UUID, ...]:
    sequence = nodes[:-1]
    rotations = [tuple(sequence[i:] + sequence[:i]) for i in range(len(sequence))]
    return min(rotations, key=lambda item: tuple(str(node) for node in item))


class VerificationService:
    def __init__(
        self,
        session: Session,
        curricula: CurriculumRepository,
        versions: CurriculumVersionRepository,
        courses: CourseRepository,
        prerequisites: CoursePrerequisiteRepository,
        runs: VerificationRunRepository,
        findings: VerificationFindingRepository,
        audit_logs: AuditLogRepository,
    ) -> None:
        self._session = session
        self._curricula = curricula
        self._versions = versions
        self._courses = courses
        self._prerequisites = prerequisites
        self._runs = runs
        self._findings = findings
        self._audit_logs = audit_logs

    def run_verification(
        self,
        actor_id: uuid.UUID,
        curriculum_id: uuid.UUID,
        version_id: uuid.UUID,
    ) -> VerificationRunResponse:
        started_at = time.perf_counter()
        self._get_version_or_404(curriculum_id, version_id)
        run = VerificationRun(
            curriculum_version_id=version_id,
            requested_by=actor_id,
            status=VerificationRunStatus.PROCESSING.value,
            started_at=utc_now(),
        )
        self._runs.add(run)
        self._audit(
            actor_id,
            "verification_run",
            run.id,
            "CREATE",
            curriculum_version_id=version_id,
            new_values={"status": run.status},
        )

        logger.info(
            "Verification analysis started",
            extra={"actor_id": str(actor_id), "verification_run_id": str(run.id)},
        )
        try:
            drafts, analysis_summary = self._analyze_version(version_id)
        except Exception as exc:
            logger.error(
                "Verification analysis failed",
                extra={
                    "actor_id": str(actor_id),
                    "verification_run_id": str(run.id),
                    "duration_ms": round((time.perf_counter() - started_at) * 1000, 2),
                    "exception_type": type(exc).__name__,
                },
            )
            run.status = VerificationRunStatus.FAILED.value
            run.completed_at = utc_now()
            run.error_message = "Verification analysis failed; see logs"
            self._session.commit()
            raise
        else:
            run.status = VerificationRunStatus.COMPLETED.value
            run.completed_at = utc_now()
            for draft in drafts:
                self._persist_finding(run, draft)
            run.summary = self._build_summary(drafts, analysis_summary)
            self._session.commit()

        logger.info(
            "Verification run completed",
            extra={
                "actor_id": str(actor_id),
                "verification_run_id": str(run.id),
                "finding_count": len(drafts),
                "duration_ms": round((time.perf_counter() - started_at) * 1000, 2),
            },
        )
        return VerificationRunResponse.from_model(run)

    def list_runs(
        self, curriculum_id: uuid.UUID, version_id: uuid.UUID
    ) -> list[VerificationRunResponse]:
        self._get_version_or_404(curriculum_id, version_id)
        return [
            VerificationRunResponse.from_model(run)
            for run in self._runs.list_by_version(version_id)
        ]

    def get_run(self, run_id: uuid.UUID) -> VerificationRunResponse:
        run = self._runs.get_by_id(run_id)
        if run is None:
            raise NotFoundError("Verification run not found")
        return VerificationRunResponse.from_model(run)

    def list_findings(
        self,
        run_id: uuid.UUID,
        category: str | None = None,
        severity: str | None = None,
    ) -> list[FindingResponse]:
        if self._runs.get_by_id(run_id) is None:
            raise NotFoundError("Verification run not found")
        return [
            FindingResponse.from_model(finding)
            for finding in self._findings.list_by_run(run_id, category, severity)
        ]

    def get_finding(self, finding_id: uuid.UUID) -> FindingResponse:
        finding = self._findings.get_by_id(finding_id)
        if finding is None:
            raise NotFoundError("Verification finding not found")
        return FindingResponse.from_model(finding)

    def review_finding(
        self,
        actor_id: uuid.UUID,
        finding_id: uuid.UUID,
        review_status: str,
        review_comments: str | None,
    ) -> FindingResponse:
        finding = self._findings.get_by_id(finding_id)
        if finding is None:
            raise NotFoundError("Verification finding not found")

        old_values = {
            "review_status": finding.review_status,
            "review_comments": finding.review_comments,
            "reviewed_by": str(finding.reviewed_by) if finding.reviewed_by else None,
        }
        finding.review_status = review_status
        finding.reviewed_by = actor_id
        finding.reviewed_at = utc_now()
        finding.review_comments = review_comments
        self._audit(
            actor_id,
            "verification_finding",
            finding.id,
            "REVIEW",
            curriculum_version_id=finding.verification_run.curriculum_version_id,
            old_values=old_values,
            new_values={
                "review_status": finding.review_status,
                "review_comments": finding.review_comments,
                "reviewed_by": str(actor_id),
            },
        )
        self._session.commit()
        self._session.refresh(finding)
        return FindingResponse.from_model(finding)

    def _analyze_version(self, version_id: uuid.UUID) -> tuple[list[_FindingDraft], dict[str, Any]]:
        courses = {
            course.id: course
            for course in self._courses.list_by_version(version_id, active_only=False)
        }
        relationships = [
            item
            for item in self._prerequisites.list_by_version(version_id)
            if item.status in ANALYZED_PREREQUISITE_STATUSES
        ]

        drafts: list[_FindingDraft] = []
        self._check_self_references(relationships, drafts)
        self._check_invalid_references(courses, relationships, drafts)
        self._check_duplicates(relationships, drafts)
        active_relationships = [
            item for item in relationships if item.status in ACTIVE_PREREQUISITE_STATUSES
        ]
        active_edges = [
            (item.prerequisite_course_id, item.target_course_id) for item in active_relationships
        ]
        self._check_cycles(active_edges, courses, active_relationships, drafts)
        self._check_ordering(courses, active_relationships, drafts)
        self._check_missing_prerequisites(courses, active_edges, drafts)
        analysis_summary = self._check_curriculum_structure(version_id, courses, drafts)
        return drafts, analysis_summary

    def _check_self_references(
        self,
        relationships: list[CoursePrerequisite],
        drafts: list[_FindingDraft],
    ) -> None:
        for relationship in relationships:
            if relationship.prerequisite_course_id == relationship.target_course_id:
                drafts.append(
                    _FindingDraft(
                        category=FindingCategory.DEPENDENCY,
                        severity=FindingSeverity.CRITICAL,
                        title="Self-referencing prerequisite detected",
                        description=(
                            "A course is listed as its own prerequisite, which is never valid."
                        ),
                        evidence=(
                            f"Prerequisite row {relationship.id} references the "
                            "same course on both sides."
                        ),
                        recommendation=("Remove the self-referencing prerequisite."),
                        confidence=Decimal("1.000"),
                        prerequisite_ids=[relationship.id],
                    )
                )

    def _check_invalid_references(
        self,
        courses: dict[uuid.UUID, Course],
        relationships: list[CoursePrerequisite],
        drafts: list[_FindingDraft],
    ) -> None:
        for relationship in relationships:
            for role, course_id in (
                ("prerequisite", relationship.prerequisite_course_id),
                ("target", relationship.target_course_id),
            ):
                course = courses.get(course_id)
                if course is None:
                    drafts.append(
                        _FindingDraft(
                            category=FindingCategory.STRUCTURAL,
                            severity=FindingSeverity.HIGH,
                            title="Prerequisite references a missing course",
                            description=(
                                f"The {role} course of this prerequisite "
                                "relationship does not exist in the analyzed "
                                "curriculum version."
                            ),
                            evidence=(
                                f"Prerequisite row {relationship.id} references "
                                f"course {course_id}, which is absent from the "
                                "version."
                            ),
                            recommendation=(
                                "Re-define the prerequisite against a course in "
                                "the current curriculum version."
                            ),
                            confidence=Decimal("0.950"),
                            prerequisite_ids=[relationship.id],
                        )
                    )
                elif course.status != CourseStatus.ACTIVE.value:
                    drafts.append(
                        _FindingDraft(
                            category=FindingCategory.STRUCTURAL,
                            severity=FindingSeverity.MEDIUM,
                            title="Prerequisite involves a removed course",
                            description=(
                                f"The {role} course of this prerequisite "
                                "relationship is no longer active in the "
                                "curriculum version."
                            ),
                            evidence=(f"Course {course.course_code} has status {course.status}."),
                            recommendation=(
                                "Review whether this prerequisite should be removed or redirected."
                            ),
                            confidence=Decimal("0.900"),
                            course_ids=[course.id],
                            prerequisite_ids=[relationship.id],
                        )
                    )

    def _check_duplicates(
        self,
        relationships: list[CoursePrerequisite],
        drafts: list[_FindingDraft],
    ) -> None:
        pairs: dict[tuple[uuid.UUID, uuid.UUID], list[CoursePrerequisite]] = {}
        for relationship in relationships:
            key = (relationship.prerequisite_course_id, relationship.target_course_id)
            pairs.setdefault(key, []).append(relationship)
        for group in pairs.values():
            if len(group) < 2:
                continue
            statuses = ", ".join(sorted(item.status for item in group))
            drafts.append(
                _FindingDraft(
                    category=FindingCategory.STRUCTURAL,
                    severity=FindingSeverity.LOW,
                    title="Duplicate prerequisite relationships",
                    description=(
                        "The same prerequisite pair appears multiple times within "
                        "the curriculum version."
                    ),
                    evidence=(
                        f"{len(group)} relationships reference this pair; "
                        f"recorded statuses: {statuses}."
                    ),
                    recommendation=(
                        "Keep a single active relationship for the pair and "
                        "clean up rejected duplicates."
                    ),
                    confidence=Decimal("1.000"),
                    course_ids=[group[0].prerequisite_course_id, group[0].target_course_id],
                    prerequisite_ids=[item.id for item in group],
                )
            )

    def _check_cycles(
        self,
        active_edges: list[tuple[uuid.UUID, uuid.UUID]],
        courses: dict[uuid.UUID, Course],
        active_relationships: list[CoursePrerequisite],
        drafts: list[_FindingDraft],
    ) -> None:
        cycles = _detect_cycles(active_edges)
        relationship_by_pair = {
            (item.prerequisite_course_id, item.target_course_id): item
            for item in active_relationships
        }
        for cycle in cycles:
            chain_codes = []
            for node in cycle:
                course = courses.get(node)
                chain_codes.append(course.course_code if course else str(node))
            chain = " -> ".join(chain_codes[:-1]) + f" -> {chain_codes[0]}"
            involved_pairs = {(cycle[i], cycle[i + 1]) for i in range(len(cycle) - 1)}
            involved_relationship_ids = [
                relationship_by_pair[pair].id
                for pair in involved_pairs
                if pair in relationship_by_pair
            ]
            drafts.append(
                _FindingDraft(
                    category=FindingCategory.DEPENDENCY,
                    severity=FindingSeverity.CRITICAL,
                    title="Circular prerequisite dependency",
                    description=(
                        "A cycle exists in the prerequisite graph, so no course "
                        f"inside the loop {chain} can be taken first."
                    ),
                    evidence=f"Cycle: {chain}",
                    recommendation=(
                        "Break the cycle by removing or redirecting one of the "
                        "prerequisites in the loop."
                    ),
                    confidence=Decimal("1.000"),
                    course_ids=list(cycle[:-1]),
                    prerequisite_ids=involved_relationship_ids,
                )
            )

    def _check_ordering(
        self,
        courses: dict[uuid.UUID, Course],
        active_relationships: list[CoursePrerequisite],
        drafts: list[_FindingDraft],
    ) -> None:
        for relationship in active_relationships:
            prerequisite = courses.get(relationship.prerequisite_course_id)
            target = courses.get(relationship.target_course_id)
            if prerequisite is None or target is None:
                continue
            prerequisite_semester = prerequisite.semester.semester_number
            target_semester = target.semester.semester_number
            if target_semester < prerequisite_semester:
                drafts.append(
                    _FindingDraft(
                        category=FindingCategory.DEPENDENCY,
                        severity=FindingSeverity.MEDIUM,
                        title="Course ordering issue",
                        description=(
                            f"{target.course_code} is scheduled in semester "
                            f"{target_semester}, before its prerequisite "
                            f"{prerequisite.course_code} in semester "
                            f"{prerequisite_semester}."
                        ),
                        evidence=(
                            f"{prerequisite.course_code} (S{prerequisite_semester})"
                            f" -> {target.course_code} (S{target_semester})"
                        ),
                        recommendation=(
                            "Move the dependent course after its prerequisite "
                            "or reconsider the prerequisite."
                        ),
                        confidence=Decimal("0.900"),
                        course_ids=[prerequisite.id, target.id],
                        prerequisite_ids=[relationship.id],
                    )
                )
            elif target_semester == prerequisite_semester:
                drafts.append(
                    _FindingDraft(
                        category=FindingCategory.DEPENDENCY,
                        severity=FindingSeverity.LOW,
                        title="Prerequisite available in the same semester",
                        description=(
                            f"{target.course_code} depends on "
                            f"{prerequisite.course_code}, but both are scheduled "
                            f"in semester {target_semester}."
                        ),
                        evidence=(
                            f"{prerequisite.course_code} (S{prerequisite_semester})"
                            f" -> {target.course_code} (S{target_semester})"
                        ),
                        recommendation=(
                            "Confirm whether concurrent enrolment is intended; "
                            "otherwise reorder the courses."
                        ),
                        confidence=Decimal("0.600"),
                        course_ids=[prerequisite.id, target.id],
                        prerequisite_ids=[relationship.id],
                    )
                )

    def _check_missing_prerequisites(
        self,
        courses: dict[uuid.UUID, Course],
        active_edges: list[tuple[uuid.UUID, uuid.UUID]],
        drafts: list[_FindingDraft],
    ) -> None:
        incoming: set[uuid.UUID] = {target for _, target in active_edges}
        outgoing_sources: set[uuid.UUID] = {source for source, _ in active_edges}
        prefixes: dict[str, list[Course]] = {}
        for course in courses.values():
            if course.status != CourseStatus.ACTIVE.value:
                continue
            prefix = "".join(char for char in course.course_code if char.isalpha())
            prefixes.setdefault(prefix or "", []).append(course)

        for prefix, group in prefixes.items():
            group_sorted = sorted(
                group,
                key=lambda item: (item.semester.semester_number, item.course_code),
            )
            for course in group_sorted:
                if course.id in incoming or course.id not in outgoing_sources:
                    continue
                earlier = [
                    other
                    for other in group_sorted
                    if other.id != course.id
                    and other.semester.semester_number < course.semester.semester_number
                ]
                if not earlier:
                    continue
                earlier_codes = ", ".join(item.course_code for item in earlier[:5])
                drafts.append(
                    _FindingDraft(
                        category=FindingCategory.DEPENDENCY,
                        severity=FindingSeverity.INFO,
                        title="Potential missing prerequisite",
                        description=(
                            f"{course.course_code} extends earlier {prefix} "
                            "courses that already participate in prerequisite "
                            "chains, but no prerequisite is defined for it."
                        ),
                        evidence=(
                            f"Earlier discipline courses: {earlier_codes}. "
                            f"{course.course_code} has no incoming prerequisite."
                        ),
                        recommendation=(
                            "Confirm whether knowledge from earlier "
                            f"{prefix} courses is expected; if so, define the "
                            "required prerequisites."
                        ),
                        confidence=Decimal("0.500"),
                        course_ids=[course.id],
                    )
                )

    def _check_curriculum_structure(
        self,
        version_id: uuid.UUID,
        courses: dict[uuid.UUID, Course],
        drafts: list[_FindingDraft],
    ) -> dict[str, Any]:
        semesters = self._session.scalars(
            select(Semester)
            .where(Semester.curriculum_version_id == version_id)
            .order_by(Semester.semester_number)
        ).all()
        active_courses = {
            course_id: course
            for course_id, course in courses.items()
            if course.status == CourseStatus.ACTIVE.value
        }
        courses_by_semester: dict[uuid.UUID, list[Course]] = {}
        credit_totals: dict[str, float] = {}
        for course in active_courses.values():
            courses_by_semester.setdefault(course.semester_id, []).append(course)
            number = str(course.semester.semester_number)
            credit_totals[number] = credit_totals.get(number, 0.0) + float(course.credits)

        for semester in semesters:
            if not courses_by_semester.get(semester.id):
                drafts.append(
                    _FindingDraft(
                        category=FindingCategory.STRUCTURAL,
                        severity=FindingSeverity.INFO,
                        title="Semester has no active courses",
                        description=(
                            f"Semester {semester.semester_number} has no active courses "
                            "in this curriculum version."
                        ),
                        evidence=f"EMPTY_SEMESTER: semester {semester.semester_number} is empty.",
                        recommendation=(
                            "Confirm whether this semester is intentionally left empty "
                            "or whether courses are missing."
                        ),
                        confidence=Decimal("1.000"),
                        semester_ids=[semester.id],
                    )
                )

        active_course_outcomes = {}
        for course in active_courses.values():
            outcomes = [
                outcome
                for outcome in course.outcomes
                if outcome.status == CourseOutcomeStatus.ACTIVE.value
            ]
            if not outcomes:
                drafts.append(
                    _FindingDraft(
                        category=FindingCategory.OUTCOME,
                        severity=FindingSeverity.MEDIUM,
                        title="Course has no active course outcomes",
                        description=f"{course.course_code} has no active course outcomes.",
                        evidence=(
                            f"COURSE_WITHOUT_CO: course {course.course_code} has no active CO."
                        ),
                        recommendation="Define and review course outcomes for this course.",
                        confidence=Decimal("1.000"),
                        course_ids=[course.id],
                    )
                )
            for outcome in outcomes:
                active_course_outcomes[outcome.id] = (course, outcome)

        pins = self._session.scalars(
            select(CurriculumVersionProgramOutcome).where(
                CurriculumVersionProgramOutcome.curriculum_version_id == version_id
            )
        ).all()
        active_program_outcomes = {
            pin.program_outcome_id: pin.program_outcome
            for pin in pins
            if pin.program_outcome.status == OutcomeStatus.ACTIVE.value
        }
        mappings = self._session.scalars(
            select(CoPoMapping).where(
                CoPoMapping.curriculum_version_id == version_id,
                CoPoMapping.status == MappingStatus.ACTIVE.value,
            )
        ).all()
        covered_course_outcomes: set[uuid.UUID] = set()
        covered_program_outcomes: set[uuid.UUID] = set()
        for mapping in mappings:
            if (
                mapping.course_outcome_id not in active_course_outcomes
                or mapping.program_outcome_id not in active_program_outcomes
            ):
                continue
            latest = max(mapping.versions, key=lambda item: item.version_number, default=None)
            if latest is None or latest.status != MappingVersionStatus.APPROVED.value:
                continue
            covered_course_outcomes.add(mapping.course_outcome_id)
            covered_program_outcomes.add(mapping.program_outcome_id)

        for course_outcome_id, (course, outcome) in active_course_outcomes.items():
            if course_outcome_id in covered_course_outcomes:
                continue
            drafts.append(
                _FindingDraft(
                    category=FindingCategory.OUTCOME,
                    severity=FindingSeverity.MEDIUM,
                    title="Course outcome has no approved program-outcome mapping",
                    description=(
                        f"{course.course_code} {outcome.co_code} is not connected by an "
                        "approved active mapping to a program outcome pinned to this version."
                    ),
                    evidence=(
                        f"CO_WITHOUT_APPROVED_PO: {course.course_code} {outcome.co_code} "
                        "has no qualifying approved mapping."
                    ),
                    recommendation=(
                        "Review the relevant program outcomes and create or approve "
                        "an appropriate mapping if one is justified."
                    ),
                    confidence=Decimal("1.000"),
                    course_ids=[course.id],
                    course_outcome_ids=[outcome.id],
                )
            )

        for program_outcome_id, outcome in active_program_outcomes.items():
            if program_outcome_id in covered_program_outcomes:
                continue
            drafts.append(
                _FindingDraft(
                    category=FindingCategory.OUTCOME,
                    severity=FindingSeverity.MEDIUM,
                    title="Program outcome has no approved course-outcome coverage",
                    description=(
                        f"{outcome.po_code} has no approved active mapping from a course "
                        "outcome in this curriculum version."
                    ),
                    evidence=(
                        f"PO_WITHOUT_APPROVED_CO: pinned program outcome {outcome.po_code} "
                        "has no qualifying approved mapping."
                    ),
                    recommendation=(
                        "Review whether this program outcome is intentionally uncovered "
                        "or whether a valid course-outcome mapping is missing."
                    ),
                    confidence=Decimal("1.000"),
                    program_outcome_ids=[program_outcome_id],
                )
            )

        return {
            "analyzers": ["PREREQUISITE", "STRUCTURE", "OUTCOME_COVERAGE"],
            "credit_totals_by_semester": {
                str(semester.semester_number): round(
                    credit_totals.get(str(semester.semester_number), 0.0), 1
                )
                for semester in semesters
            },
        }

    def _persist_finding(self, run: VerificationRun, draft: _FindingDraft) -> VerificationFinding:
        finding = VerificationFinding(
            verification_run_id=run.id,
            category=draft.category.value,
            severity=draft.severity.value,
            confidence=draft.confidence,
            title=draft.title,
            description=draft.description,
            evidence=draft.evidence,
            recommendation=draft.recommendation,
            requires_human_review=True,
        )
        references = [
            VerificationFindingReference(
                finding=finding,
                entity_type=ReferenceEntityType.CURRICULUM_VERSION.value,
                entity_id=run.curriculum_version_id,
            )
        ]
        for course_id in draft.course_ids:
            references.append(
                VerificationFindingReference(
                    finding=finding,
                    entity_type=ReferenceEntityType.COURSE.value,
                    entity_id=course_id,
                )
            )
        for prerequisite_id in draft.prerequisite_ids:
            references.append(
                VerificationFindingReference(
                    finding=finding,
                    entity_type=ReferenceEntityType.PREREQUISITE.value,
                    entity_id=prerequisite_id,
                )
            )
        for semester_id in draft.semester_ids:
            references.append(
                VerificationFindingReference(
                    finding=finding,
                    entity_type=ReferenceEntityType.SEMESTER.value,
                    entity_id=semester_id,
                )
            )
        for outcome_id in draft.course_outcome_ids:
            references.append(
                VerificationFindingReference(
                    finding=finding,
                    entity_type=ReferenceEntityType.COURSE_OUTCOME.value,
                    entity_id=outcome_id,
                )
            )
        for outcome_id in draft.program_outcome_ids:
            references.append(
                VerificationFindingReference(
                    finding=finding,
                    entity_type=ReferenceEntityType.PROGRAM_OUTCOME.value,
                    entity_id=outcome_id,
                )
            )
        finding.references = references
        self._findings.add(finding)
        return finding

    def _build_summary(
        self, drafts: list[_FindingDraft], analysis_summary: dict[str, Any]
    ) -> dict[str, Any]:
        by_severity: dict[str, int] = {}
        by_category: dict[str, int] = {}
        for draft in drafts:
            by_severity[draft.severity.value] = by_severity.get(draft.severity.value, 0) + 1
            by_category[draft.category.value] = by_category.get(draft.category.value, 0) + 1
        return {
            "result": "ISSUES_FOUND" if drafts else "PASSED",
            "total_findings": len(drafts),
            "findings_by_severity": dict(
                sorted(by_severity.items(), key=lambda item: SEVERITY_ORDER[item[0]])
            ),
            "findings_by_category": dict(sorted(by_category.items())),
            **analysis_summary,
        }

    def _get_version_or_404(
        self, curriculum_id: uuid.UUID, version_id: uuid.UUID
    ) -> CurriculumVersion:
        if self._curricula.get_by_id(curriculum_id) is None:
            raise NotFoundError("Curriculum not found")
        version = self._versions.get_by_id(version_id)
        if version is None or version.curriculum_id != curriculum_id:
            raise NotFoundError("Curriculum version not found")
        return version

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
