import hashlib
import json
import logging
import time
import uuid
from collections import Counter, deque
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.db.models.academic import (
    Course,
    CourseOutcome,
    CourseOutcomeStatus,
    CoursePrerequisite,
    CourseStatus,
    Curriculum,
    CurriculumVersion,
    PrerequisiteStatus,
    Semester,
)
from app.db.models.audit import AuditLog
from app.db.models.mappings import (
    CoPoMapping,
    CurriculumVersionPeo,
    CurriculumVersionProgramOutcome,
    MappingStatus,
    MappingVersionStatus,
)
from app.db.models.outcomes import (
    OutcomeStatus,
    ProgramEducationalObjective,
    ProgramOutcome,
)
from app.db.models.user import utc_now
from app.db.models.verification import (
    FindingCategory,
    FindingSeverity,
    ReferenceEntityType,
    VerificationFinding,
    VerificationFindingReference,
    VerificationReference,
    VerificationReferenceType,
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
from app.repositories.verification_references import VerificationReferenceRepository
from app.schemas.verification import (
    FindingResponse,
    VerificationReportGroup,
    VerificationReportResponse,
    VerificationRunResponse,
)
from app.schemas.verification_reference import (
    AccreditationRules,
    IndustryRules,
    InstitutionalRules,
    ObeRules,
)
from app.services.verification_analysis import (
    build_upstream_reachability,
    course_number,
    course_topic_tokens,
    has_progression_marker,
    keyword_present,
    longest_prerequisite_chain,
    title_similarity,
    topic_similarity,
    transitive_redundant_edges,
)
from app.services.verification_references import resolve_applicable_references

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

TOPIC_MIN_SHARED_TERMS = 3
TOPIC_MIN_PROFILE_TERMS = 5
TOPIC_CANDIDATE_SCORE = 0.35
TOPIC_REDUNDANCY_SCORE = 0.55


@dataclass
class _VersionSnapshot:
    version: CurriculumVersion
    curriculum: Curriculum
    semesters: list[Semester]
    courses: dict[uuid.UUID, Course]
    relationships: list[CoursePrerequisite]
    active_relationships: list[CoursePrerequisite]
    active_edges: list[tuple[uuid.UUID, uuid.UUID]]
    active_course_outcomes: dict[uuid.UUID, tuple[Course, CourseOutcome]]
    pinned_program_outcomes: dict[uuid.UUID, ProgramOutcome]
    pinned_peos: dict[uuid.UUID, ProgramEducationalObjective]
    mappings: list[CoPoMapping]
    covered_course_outcomes: set[uuid.UUID]
    covered_program_outcomes: set[uuid.UUID]
    references: list[VerificationReference]
    fingerprint: str


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
        reference_ids: list[uuid.UUID] | None = None,
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
        self.reference_ids = reference_ids or []


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
        references: VerificationReferenceRepository,
        audit_logs: AuditLogRepository,
    ) -> None:
        self._session = session
        self._curricula = curricula
        self._versions = versions
        self._courses = courses
        self._prerequisites = prerequisites
        self._runs = runs
        self._findings = findings
        self._references = references
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
            snapshot = self._load_snapshot(version_id)
            drafts, analysis_summary = self._analyze_snapshot(snapshot)
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
        return VerificationRunResponse.from_model(run, is_stale=False)

    def list_runs(
        self, curriculum_id: uuid.UUID, version_id: uuid.UUID
    ) -> list[VerificationRunResponse]:
        self._get_version_or_404(curriculum_id, version_id)
        current_fingerprint = self._current_fingerprint(version_id)
        return [
            self._run_response(run, current_fingerprint)
            for run in self._runs.list_by_version(version_id)
        ]

    def get_run(self, run_id: uuid.UUID) -> VerificationRunResponse:
        run = self._runs.get_by_id(run_id)
        if run is None:
            raise NotFoundError("Verification run not found")
        return self._run_response(run, self._current_fingerprint(run.curriculum_version_id))

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

    def get_report(
        self,
        run_id: uuid.UUID,
        group_by: Literal["category", "severity", "review_status"] = "category",
        category: str | None = None,
        severity: str | None = None,
        review_status: str | None = None,
    ) -> VerificationReportResponse:
        run = self._runs.get_by_id(run_id)
        if run is None:
            raise NotFoundError("Verification run not found")
        findings = self._findings.list_by_run(run_id, category, severity)
        if review_status is not None:
            findings = [item for item in findings if item.review_status == review_status]

        counts_by_category = Counter(item.category for item in findings)
        counts_by_severity = Counter(item.severity for item in findings)
        counts_by_review_status = Counter(item.review_status for item in findings)
        grouped: dict[str, list[FindingResponse]] = {}
        for finding in findings:
            grouped.setdefault(getattr(finding, group_by), []).append(
                FindingResponse.from_model(finding)
            )
        return VerificationReportResponse(
            run=self._run_response(
                run,
                self._current_fingerprint(run.curriculum_version_id),
            ),
            total_findings=len(findings),
            groups=[
                VerificationReportGroup(key=key, count=len(group), findings=group)
                for key, group in sorted(grouped.items())
            ],
            counts_by_category=dict(sorted(counts_by_category.items())),
            counts_by_severity=dict(sorted(counts_by_severity.items())),
            counts_by_review_status=dict(sorted(counts_by_review_status.items())),
        )

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

    def _run_response(
        self,
        run: VerificationRun,
        current_fingerprint: str | None,
    ) -> VerificationRunResponse:
        stored_fingerprint = (run.summary or {}).get("input_fingerprint")
        is_stale = bool(
            stored_fingerprint
            and current_fingerprint
            and stored_fingerprint != current_fingerprint
        )
        return VerificationRunResponse.from_model(run, is_stale=is_stale)

    def _current_fingerprint(self, version_id: uuid.UUID) -> str | None:
        try:
            return self._load_snapshot(version_id).fingerprint
        except NotFoundError:
            return None

    def _load_snapshot(self, version_id: uuid.UUID) -> _VersionSnapshot:
        version = self._versions.get_by_id(version_id)
        if version is None:
            raise NotFoundError("Curriculum version not found")
        curriculum = self._curricula.get_by_id(version.curriculum_id)
        if curriculum is None:
            raise NotFoundError("Curriculum not found")

        semesters = list(
            self._session.scalars(
                select(Semester)
                .where(Semester.curriculum_version_id == version_id)
                .order_by(Semester.semester_number)
            ).all()
        )
        courses = {
            course.id: course
            for course in self._courses.list_by_version(version_id, active_only=False)
        }
        relationships = [
            item
            for item in self._prerequisites.list_by_version(version_id)
            if item.status in ANALYZED_PREREQUISITE_STATUSES
        ]
        active_relationships = [
            item for item in relationships if item.status in ACTIVE_PREREQUISITE_STATUSES
        ]
        active_edges = [
            (item.prerequisite_course_id, item.target_course_id)
            for item in active_relationships
        ]

        active_course_outcomes: dict[uuid.UUID, tuple[Course, CourseOutcome]] = {}
        for course in courses.values():
            if course.status != CourseStatus.ACTIVE.value:
                continue
            for outcome in course.outcomes:
                if outcome.status == CourseOutcomeStatus.ACTIVE.value:
                    active_course_outcomes[outcome.id] = (course, outcome)

        pins = list(
            self._session.scalars(
                select(CurriculumVersionProgramOutcome).where(
                    CurriculumVersionProgramOutcome.curriculum_version_id == version_id
                )
            ).all()
        )
        pinned_program_outcomes = {
            pin.program_outcome_id: pin.program_outcome
            for pin in pins
            if pin.program_outcome.status == OutcomeStatus.ACTIVE.value
        }
        peo_pins = list(
            self._session.scalars(
                select(CurriculumVersionPeo).where(
                    CurriculumVersionPeo.curriculum_version_id == version_id
                )
            ).all()
        )
        pinned_peos = {
            pin.peo_id: pin.peo
            for pin in peo_pins
            if pin.peo.status == OutcomeStatus.ACTIVE.value
        }

        mappings = list(
            self._session.scalars(
                select(CoPoMapping).where(
                    CoPoMapping.curriculum_version_id == version_id,
                    CoPoMapping.status == MappingStatus.ACTIVE.value,
                )
            ).all()
        )
        covered_course_outcomes: set[uuid.UUID] = set()
        covered_program_outcomes: set[uuid.UUID] = set()
        for mapping in mappings:
            if (
                mapping.course_outcome_id not in active_course_outcomes
                or mapping.program_outcome_id not in pinned_program_outcomes
            ):
                continue
            latest = max(mapping.versions, key=lambda item: item.version_number, default=None)
            if latest is None or latest.status != MappingVersionStatus.APPROVED.value:
                continue
            covered_course_outcomes.add(mapping.course_outcome_id)
            covered_program_outcomes.add(mapping.program_outcome_id)

        references = resolve_applicable_references(
            self._references.list_active_for_program(curriculum.program_id)
        )
        snapshot = _VersionSnapshot(
            version=version,
            curriculum=curriculum,
            semesters=semesters,
            courses=courses,
            relationships=relationships,
            active_relationships=active_relationships,
            active_edges=active_edges,
            active_course_outcomes=active_course_outcomes,
            pinned_program_outcomes=pinned_program_outcomes,
            pinned_peos=pinned_peos,
            mappings=mappings,
            covered_course_outcomes=covered_course_outcomes,
            covered_program_outcomes=covered_program_outcomes,
            references=references,
            fingerprint="",
        )
        snapshot.fingerprint = self._fingerprint(snapshot)
        return snapshot

    def _fingerprint(self, snapshot: _VersionSnapshot) -> str:
        payload = {
            "version": {
                "id": str(snapshot.version.id),
                "label": snapshot.version.version_label,
                "status": snapshot.version.status,
                "previous_version_id": (
                    str(snapshot.version.previous_version_id)
                    if snapshot.version.previous_version_id
                    else None
                ),
            },
            "curriculum": {
                "id": str(snapshot.curriculum.id),
                "program_id": str(snapshot.curriculum.program_id),
                "regulation": snapshot.curriculum.regulation,
                "duration_years": str(snapshot.curriculum.duration_years),
            },
            "semesters": [
                {
                    "id": str(semester.id),
                    "number": semester.semester_number,
                    "name": semester.name,
                    "focus": semester.focus,
                }
                for semester in snapshot.semesters
            ],
            "courses": sorted(
                (
                    {
                        "id": str(course.id),
                        "code": course.course_code,
                        "name": course.course_name,
                        "type": course.course_type.code,
                        "credits": str(course.credits),
                        "semester": course.semester.semester_number,
                        "contact_hours": course.contact_hours,
                        "description": course.description,
                        "syllabus": course.syllabus,
                        "status": course.status,
                        "updated_at": course.updated_at,
                    }
                    for course in snapshot.courses.values()
                ),
                key=lambda item: item["id"],
            ),
            "course_outcomes": sorted(
                (
                    {
                        "id": str(outcome.id),
                        "course_id": str(course.id),
                        "code": outcome.co_code,
                        "description": outcome.description,
                        "status": outcome.status,
                        "updated_at": outcome.updated_at,
                    }
                    for course in snapshot.courses.values()
                    for outcome in course.outcomes
                ),
                key=lambda item: item["id"],
            ),
            "prerequisites": sorted(
                (
                    {
                        "id": str(item.id),
                        "prerequisite_course_id": str(item.prerequisite_course_id),
                        "target_course_id": str(item.target_course_id),
                        "status": item.status,
                        "review_comments": item.review_comments,
                        "updated_at": item.updated_at,
                    }
                    for item in snapshot.relationships
                ),
                key=lambda item: item["id"],
            ),
            "program_outcome_pins": sorted(
                (
                    {
                        "program_outcome_id": str(pin.program_outcome_id),
                        "program_outcome_version_id": str(pin.program_outcome_version_id),
                    }
                    for pin in self._session.scalars(
                        select(CurriculumVersionProgramOutcome).where(
                            CurriculumVersionProgramOutcome.curriculum_version_id
                            == snapshot.version.id
                        )
                    ).all()
                ),
                key=lambda item: item["program_outcome_id"],
            ),
            "peo_pins": sorted(
                (
                    {
                        "peo_id": str(pin.peo_id),
                        "peo_version_id": str(pin.peo_version_id),
                    }
                    for pin in self._session.scalars(
                        select(CurriculumVersionPeo).where(
                            CurriculumVersionPeo.curriculum_version_id
                            == snapshot.version.id
                        )
                    ).all()
                ),
                key=lambda item: item["peo_id"],
            ),
            "mappings": sorted(
                (
                    {
                        "id": str(mapping.id),
                        "course_outcome_id": str(mapping.course_outcome_id),
                        "program_outcome_id": str(mapping.program_outcome_id),
                        "status": mapping.status,
                        "versions": sorted(
                            (
                                {
                                    "id": str(version.id),
                                    "number": version.version_number,
                                    "level_id": str(version.mapping_level_id),
                                    "status": version.status,
                                }
                                for version in mapping.versions
                            ),
                            key=lambda item: item["number"],
                        ),
                    }
                    for mapping in snapshot.mappings
                ),
                key=lambda item: item["id"],
            ),
            "references": sorted(
                (
                    {
                        "id": str(reference.id),
                        "type": reference.reference_type,
                        "code": reference.code,
                        "version": reference.version_label,
                        "status": reference.status,
                        "severity": reference.severity,
                        "rules": reference.rules,
                        "effective_date": (
                            reference.effective_date.isoformat()
                            if reference.effective_date
                            else None
                        ),
                    }
                    for reference in snapshot.references
                ),
                key=lambda item: item["id"],
            ),
        }
        serialized = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
        return f"sha256:{hashlib.sha256(serialized.encode('utf-8')).hexdigest()}"

    def _analyze_snapshot(
        self,
        snapshot: _VersionSnapshot,
    ) -> tuple[list[_FindingDraft], dict[str, Any]]:
        drafts: list[_FindingDraft] = []
        self._check_self_references(snapshot.relationships, drafts)
        self._check_invalid_references(snapshot.courses, snapshot.relationships, drafts)
        self._check_duplicates(snapshot.relationships, drafts)
        self._check_cycles(
            snapshot.active_edges,
            snapshot.courses,
            snapshot.active_relationships,
            drafts,
        )
        self._check_ordering(snapshot.courses, snapshot.active_relationships, drafts)
        self._check_missing_prerequisites(snapshot.courses, snapshot.active_edges, drafts)
        prerequisite_summary = self._analyze_prerequisite_chains(snapshot, drafts)
        structure_summary = self._check_semester_structure(snapshot, drafts)
        topic_summary = self._check_topic_overlap(snapshot, drafts)
        self._check_outcome_coverage(snapshot, drafts)
        reference_summary = self._check_reference_alignment(snapshot, drafts)
        analysis_summary = self._build_analysis_summary(
            snapshot,
            prerequisite_summary,
            structure_summary,
            topic_summary,
            reference_summary,
        )
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
                            f"SELF_PREREQUISITE: prerequisite row {relationship.id} "
                            "references the same course on both sides."
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
                                f"MISSING_PREREQUISITE_COURSE: prerequisite row "
                                f"{relationship.id} references course {course_id}, "
                                "which is absent from the version."
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
                            evidence=(
                                f"REMOVED_PREREQUISITE_COURSE: course "
                                f"{course.course_code} has status {course.status}."
                            ),
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
                        f"DUPLICATE_PREREQUISITE: {len(group)} relationships "
                        f"reference this pair; recorded statuses: {statuses}."
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
                    evidence=f"CIRCULAR_PREREQUISITE: cycle {chain}",
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
                            "PREREQUISITE_OUT_OF_ORDER: "
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
                            "PREREQUISITE_SAME_SEMESTER: "
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
                            f"MISSING_PREREQUISITE_CANDIDATE: earlier discipline "
                            f"courses: {earlier_codes}. {course.course_code} has no "
                            "incoming prerequisite."
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

    def _analyze_prerequisite_chains(
        self,
        snapshot: _VersionSnapshot,
        drafts: list[_FindingDraft],
    ) -> dict[str, Any]:
        active_courses = {
            course_id: course
            for course_id, course in snapshot.courses.items()
            if course.status == CourseStatus.ACTIVE.value
        }
        edges = snapshot.active_edges
        incoming = {target for _, target in edges}
        outgoing = {source for source, _ in edges}
        roots = sorted(
            (course for course_id, course in active_courses.items() if course_id not in incoming),
            key=lambda course: (course.semester.semester_number, course.course_code),
        )
        leaves = sorted(
            (course for course_id, course in active_courses.items() if course_id not in outgoing),
            key=lambda course: (course.semester.semester_number, course.course_code),
        )
        isolated = sorted(
            (
                course
                for course_id, course in active_courses.items()
                if course_id not in incoming and course_id not in outgoing
            ),
            key=lambda course: (course.semester.semester_number, course.course_code),
        )

        longest = longest_prerequisite_chain(edges)
        longest_codes = [
            active_courses[node].course_code if node in active_courses else str(node)
            for node in longest
        ]
        longest_semesters = [
            active_courses[node].semester.semester_number
            for node in longest
            if node in active_courses
        ]

        relationship_by_pair = {
            (item.prerequisite_course_id, item.target_course_id): item
            for item in snapshot.active_relationships
        }
        redundant_edges = transitive_redundant_edges(edges)
        for prerequisite_id, target_id, path in redundant_edges:
            path_codes = [
                active_courses[node].course_code if node in active_courses else str(node)
                for node in path
            ]
            relationship_ids = [
                relationship_by_pair[(path[index], path[index + 1])].id
                for index in range(len(path) - 1)
                if (path[index], path[index + 1]) in relationship_by_pair
            ]
            direct_relationship = relationship_by_pair.get((prerequisite_id, target_id))
            if direct_relationship is not None:
                relationship_ids.insert(0, direct_relationship.id)
            drafts.append(
                _FindingDraft(
                    category=FindingCategory.DEPENDENCY,
                    severity=FindingSeverity.INFO,
                    title="Redundant transitive prerequisite",
                    description=(
                        f"{path_codes[0]} is a direct prerequisite of "
                        f"{path_codes[-1]}, but the same dependency is already implied "
                        f"by the chain {' -> '.join(path_codes)}."
                    ),
                    evidence=(
                        f"TRANSITIVE_PREREQUISITE: direct edge {path_codes[0]} -> "
                        f"{path_codes[-1]}; alternative path "
                        f"{' -> '.join(path_codes)}."
                    ),
                    recommendation=(
                        "Keep the direct prerequisite only if an explicit placement or "
                        "validation rule requires it; otherwise remove the redundant edge "
                        "to keep the dependency chain easier to maintain."
                    ),
                    confidence=Decimal("1.000"),
                    course_ids=path,
                    prerequisite_ids=relationship_ids,
                )
            )

        return {
            "edge_count": len(edges),
            "root_courses": [course.course_code for course in roots],
            "leaf_courses": [course.course_code for course in leaves],
            "isolated_courses": [course.course_code for course in isolated],
            "longest_chain": longest_codes,
            "longest_chain_length": len(longest_codes),
            "longest_chain_semesters": longest_semesters,
            "transitive_redundant_edges": len(redundant_edges),
        }

    def _check_semester_structure(
        self,
        snapshot: _VersionSnapshot,
        drafts: list[_FindingDraft],
    ) -> dict[str, Any]:
        active_courses = {
            course_id: course
            for course_id, course in snapshot.courses.items()
            if course.status == CourseStatus.ACTIVE.value
        }
        courses_by_semester: dict[uuid.UUID, list[Course]] = {}
        credit_totals: dict[str, float] = {}
        credit_totals_by_type: dict[str, float] = {}
        course_counts_by_semester: dict[str, int] = {}
        course_counts_by_type: dict[str, int] = {}
        for course in active_courses.values():
            courses_by_semester.setdefault(course.semester_id, []).append(course)
            semester_key = str(course.semester.semester_number)
            type_code = course.course_type.code
            credit_totals[semester_key] = credit_totals.get(semester_key, 0.0) + float(
                course.credits
            )
            credit_totals_by_type[type_code] = credit_totals_by_type.get(type_code, 0.0) + float(
                course.credits
            )
            course_counts_by_semester[semester_key] = (
                course_counts_by_semester.get(semester_key, 0) + 1
            )
            course_counts_by_type[type_code] = course_counts_by_type.get(type_code, 0) + 1

            if float(course.credits) <= 0 or float(course.credits) > 30:
                drafts.append(
                    _FindingDraft(
                        category=FindingCategory.STRUCTURAL,
                        severity=FindingSeverity.HIGH,
                        title="Course has an invalid credit value",
                        description=(
                            f"{course.course_code} records {course.credits} credits. "
                            "Course credits must be greater than zero and no more than 30."
                        ),
                        evidence=(
                            f"INVALID_COURSE_CREDITS: course {course.course_code} has "
                            f"{course.credits} credits."
                        ),
                        recommendation=(
                            "Correct the course credit value and rerun verification."
                        ),
                        confidence=Decimal("1.000"),
                        course_ids=[course.id],
                    )
                )

        if not active_courses:
            drafts.append(
                _FindingDraft(
                    category=FindingCategory.STRUCTURAL,
                    severity=FindingSeverity.HIGH,
                    title="Curriculum version has no active courses",
                    description=(
                        "The selected curriculum version contains no active courses, so "
                        "credit, distribution, dependency, and topic checks have no evidence."
                    ),
                    evidence=(
                        "CURRICULUM_WITHOUT_ACTIVE_COURSES: all courses are removed or absent."
                    ),
                    recommendation=(
                        "Add the intended active courses to this version before treating "
                        "the verification result as meaningful."
                    ),
                    confidence=Decimal("1.000"),
                )
            )

        for semester in snapshot.semesters:
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
                        evidence=(
                            f"EMPTY_SEMESTER: semester {semester.semester_number} is empty."
                        ),
                        recommendation=(
                            "Confirm whether this semester is intentionally left empty "
                            "or whether courses are missing."
                        ),
                        confidence=Decimal("1.000"),
                        semester_ids=[semester.id],
                    )
                )

        semester_numbers = [semester.semester_number for semester in snapshot.semesters]
        missing_numbers = [
            number
            for number in range(1, max(semester_numbers, default=0) + 1)
            if number not in set(semester_numbers)
        ]
        if missing_numbers:
            drafts.append(
                _FindingDraft(
                    category=FindingCategory.STRUCTURAL,
                    severity=FindingSeverity.LOW,
                    title="Semester sequence contains gaps",
                    description=(
                        "Semester numbers are not contiguous from 1. Missing numbers: "
                        + ", ".join(str(number) for number in missing_numbers)
                        + "."
                    ),
                    evidence=(
                        "SEMESTER_SEQUENCE_GAP: present "
                        f"{sorted(semester_numbers)}; missing {missing_numbers}."
                    ),
                    recommendation=(
                        "Add the missing semesters or renumber the sequence so course "
                        "ordering can be interpreted consistently."
                    ),
                    confidence=Decimal("1.000"),
                )
            )

        total_credits = round(sum(credit_totals.values()), 1)
        semester_credit_values = [
            round(credit_totals.get(str(semester.semester_number), 0.0), 1)
            for semester in snapshot.semesters
        ]
        return {
            "active_course_count": len(active_courses),
            "semester_count": len(snapshot.semesters),
            "expected_semester_count": (
                int(float(snapshot.curriculum.duration_years) * 2)
                if snapshot.curriculum.duration_years is not None
                else None
            ),
            "total_credits": total_credits,
            "credit_totals_by_semester": {
                str(semester.semester_number): round(
                    credit_totals.get(str(semester.semester_number), 0.0), 1
                )
                for semester in snapshot.semesters
            },
            "credits_by_course_type": dict(sorted(credit_totals_by_type.items())),
            "course_counts_by_semester": {
                str(semester.semester_number): course_counts_by_semester.get(
                    str(semester.semester_number), 0
                )
                for semester in snapshot.semesters
            },
            "course_counts_by_course_type": dict(sorted(course_counts_by_type.items())),
            "average_semester_credits": (
                round(total_credits / len(snapshot.semesters), 1)
                if snapshot.semesters
                else 0.0
            ),
            "semester_credit_range": {
                "min": min(semester_credit_values, default=0.0),
                "max": max(semester_credit_values, default=0.0),
            },
        }

    def _check_topic_overlap(
        self,
        snapshot: _VersionSnapshot,
        drafts: list[_FindingDraft],
    ) -> dict[str, Any]:
        active_courses = sorted(
            (
                course
                for course in snapshot.courses.values()
                if course.status == CourseStatus.ACTIVE.value
            ),
            key=lambda course: (course.semester.semester_number, course.course_code),
        )
        profiles = {}
        for course in active_courses:
            profiles[course.id] = course_topic_tokens(
                course.course_name,
                course.description,
                course.syllabus,
                [
                    outcome.description
                    for outcome in course.outcomes
                    if outcome.status == CourseOutcomeStatus.ACTIVE.value
                ],
            )
        upstream = build_upstream_reachability(snapshot.active_edges)

        overlaps: list[dict[str, Any]] = []
        redundancy_count = 0
        progression_count = 0
        unverified_progression_count = 0
        cross_discipline_count = 0
        pairs_evaluated = 0

        for index, left in enumerate(active_courses):
            for right in active_courses[index + 1 :]:
                left_profile = profiles[left.id]
                right_profile = profiles[right.id]
                if (
                    len(left_profile) < TOPIC_MIN_PROFILE_TERMS
                    or len(right_profile) < TOPIC_MIN_PROFILE_TERMS
                ):
                    continue
                pairs_evaluated += 1
                score, shared_terms = topic_similarity(left_profile, right_profile)
                if len(shared_terms) < TOPIC_MIN_SHARED_TERMS or score < TOPIC_CANDIDATE_SCORE:
                    continue
                title_score = title_similarity(left.course_name, right.course_name)
                if left.semester.semester_number <= right.semester.semester_number:
                    earlier, later = left, right
                else:
                    earlier, later = right, left
                same_semester = left.semester.semester_number == right.semester.semester_number
                same_prefix = self._course_prefix(earlier.course_code) == self._course_prefix(
                    later.course_code
                )
                related = earlier.id in upstream.get(later.id, set())
                later_number = course_number(later.course_code)
                earlier_number = course_number(earlier.course_code)
                higher_level_code = bool(
                    later_number is not None
                    and earlier_number is not None
                    and later_number > earlier_number
                )
                progression_marker = has_progression_marker(
                    later.course_name, later.course_code
                )

                if same_semester:
                    if score >= TOPIC_REDUNDANCY_SCORE or title_score >= 0.75:
                        classification = "REDUNDANCY"
                    else:
                        classification = "CROSS_DISCIPLINE"
                elif related:
                    classification = "PROGRESSION"
                elif same_prefix and (
                    progression_marker or higher_level_code or score >= 0.5
                ):
                    classification = "PROGRESSION_UNVERIFIED"
                elif score >= 0.6 and title_score >= 0.55:
                    classification = "REDUNDANCY"
                else:
                    classification = "CROSS_DISCIPLINE"

                overlap = {
                    "course_a": earlier.course_code,
                    "course_b": later.course_code,
                    "semester_a": earlier.semester.semester_number,
                    "semester_b": later.semester.semester_number,
                    "score": score,
                    "title_similarity": title_score,
                    "shared_terms": shared_terms[:10],
                    "classification": classification,
                }
                overlaps.append(overlap)

                if classification == "REDUNDANCY":
                    redundancy_count += 1
                    severity = (
                        FindingSeverity.MEDIUM
                        if score >= TOPIC_REDUNDANCY_SCORE or title_score >= 0.7
                        else FindingSeverity.LOW
                    )
                    drafts.append(
                        _FindingDraft(
                            category=FindingCategory.CONTENT,
                            severity=severity,
                            title="Potential topic redundancy between courses",
                            description=(
                                f"{earlier.course_code} and {later.course_code} share "
                                f"substantial topic evidence ({round(score * 100)}% "
                                "weighted overlap) without a prerequisite progression "
                                "between them."
                            ),
                            evidence=(
                                "TOPIC_REDUNDANCY: "
                                f"{earlier.course_code} (S{earlier.semester.semester_number}) "
                                f"and {later.course_code} "
                                f"(S{later.semester.semester_number}) share "
                                f"{len(shared_terms)} topic terms: "
                                f"{', '.join(shared_terms[:8])}; score={score}; "
                                f"title_similarity={title_score}."
                            ),
                            recommendation=(
                                "Confirm whether the shared content is intentional. If not, "
                                "remove duplicate topics, merge the courses, or make the "
                                "progression explicit with distinct depth and a prerequisite."
                            ),
                            confidence=Decimal(str(min(max(score, 0.0), 1.0))),
                            course_ids=[earlier.id, later.id],
                            semester_ids=[earlier.semester_id, later.semester_id],
                        )
                    )
                elif classification == "PROGRESSION":
                    progression_count += 1
                elif classification == "PROGRESSION_UNVERIFIED":
                    unverified_progression_count += 1
                    drafts.append(
                        _FindingDraft(
                            category=FindingCategory.CONTENT,
                            severity=FindingSeverity.INFO,
                            title="Topic progression without a prerequisite path",
                            description=(
                                f"{later.course_code} builds on topic evidence from "
                                f"{earlier.course_code} in a later semester, but no "
                                "prerequisite path connects the courses."
                            ),
                            evidence=(
                                "TOPIC_PROGRESSION: "
                                f"{earlier.course_code} (S{earlier.semester.semester_number}) "
                                f"and {later.course_code} "
                                f"(S{later.semester.semester_number}) share "
                                f"{len(shared_terms)} topic terms: "
                                f"{', '.join(shared_terms[:8])}; score={score}; "
                                f"title_similarity={title_score}."
                            ),
                            recommendation=(
                                "Confirm that the later course adds depth rather than "
                                "repeating content, and define the prerequisite if the "
                                "earlier course is genuinely required."
                            ),
                            confidence=Decimal(str(min(max(score, 0.0), 1.0))),
                            course_ids=[earlier.id, later.id],
                            semester_ids=[earlier.semester_id, later.semester_id],
                        )
                    )
                else:
                    cross_discipline_count += 1
                    if score >= 0.6 and title_score >= 0.55:
                        drafts.append(
                            _FindingDraft(
                                category=FindingCategory.CONTENT,
                                severity=FindingSeverity.INFO,
                                title="Cross-discipline topic overlap",
                                description=(
                                    f"{earlier.course_code} and {later.course_code} share "
                                    "topic evidence across course-code disciplines. This "
                                    "may be intentional integration or unintended duplication."
                                ),
                                evidence=(
                                    "TOPIC_OVERLAP: "
                                    f"{earlier.course_code} and {later.course_code} share "
                                    f"{len(shared_terms)} topic terms: "
                                    f"{', '.join(shared_terms[:8])}; score={score}; "
                                    f"title_similarity={title_score}."
                                ),
                                recommendation=(
                                    "Confirm that the shared content is intentional and that "
                                    "each course assesses it at the appropriate depth."
                                ),
                                confidence=Decimal(str(min(max(score, 0.0), 1.0))),
                                course_ids=[earlier.id, later.id],
                                semester_ids=[earlier.semester_id, later.semester_id],
                            )
                        )

        top_overlaps = sorted(
            overlaps,
            key=lambda item: (-item["score"], item["course_a"], item["course_b"]),
        )[:10]
        return {
            "pairs_evaluated": pairs_evaluated,
            "candidates": len(overlaps),
            "redundancy_candidates": redundancy_count,
            "progression_candidates": progression_count,
            "unverified_progression_candidates": unverified_progression_count,
            "cross_discipline_candidates": cross_discipline_count,
            "top_overlaps": top_overlaps,
        }

    def _check_outcome_coverage(
        self,
        snapshot: _VersionSnapshot,
        drafts: list[_FindingDraft],
    ) -> None:
        active_courses = {
            course_id: course
            for course_id, course in snapshot.courses.items()
            if course.status == CourseStatus.ACTIVE.value
        }
        active_course_outcomes = snapshot.active_course_outcomes

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

        for course_outcome_id, (course, outcome) in active_course_outcomes.items():
            if course_outcome_id in snapshot.covered_course_outcomes:
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

        for program_outcome_id, outcome in snapshot.pinned_program_outcomes.items():
            if program_outcome_id in snapshot.covered_program_outcomes:
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

    def _check_reference_alignment(
        self,
        snapshot: _VersionSnapshot,
        drafts: list[_FindingDraft],
    ) -> dict[str, Any]:
        active_courses = [
            course
            for course in snapshot.courses.values()
            if course.status == CourseStatus.ACTIVE.value
        ]
        total_credits = round(sum(float(course.credits) for course in active_courses), 1)
        credits_by_type: dict[str, float] = {}
        for course in active_courses:
            type_code = course.course_type.code
            credits_by_type[type_code] = credits_by_type.get(type_code, 0.0) + float(
                course.credits
            )

        references_summary: list[dict[str, Any]] = []
        metrics_by_reference: dict[str, Any] = {}
        findings_by_reference: dict[str, int] = {}
        invalid_references: list[dict[str, str]] = []

        for reference in snapshot.references:
            before = len(drafts)
            category = FindingCategory.ACCREDITATION_OBE
            if reference.reference_type == VerificationReferenceType.INSTITUTIONAL.value:
                category = FindingCategory.STRUCTURAL
            elif reference.reference_type == VerificationReferenceType.INDUSTRY.value:
                category = FindingCategory.INDUSTRY_ALIGNMENT

            try:
                if reference.reference_type == VerificationReferenceType.INSTITUTIONAL.value:
                    rules = InstitutionalRules.model_validate(reference.rules)
                    metrics = self._compare_institutional_reference(
                        snapshot, rules, reference, drafts
                    )
                elif reference.reference_type == VerificationReferenceType.OBE.value:
                    rules = ObeRules.model_validate(reference.rules)
                    metrics = self._compare_obe_reference(
                        snapshot, rules, reference, drafts
                    )
                elif reference.reference_type == VerificationReferenceType.ACCREDITATION.value:
                    rules = AccreditationRules.model_validate(reference.rules)
                    metrics = self._compare_accreditation_reference(
                        snapshot, rules, reference, drafts
                    )
                elif reference.reference_type == VerificationReferenceType.INDUSTRY.value:
                    rules = IndustryRules.model_validate(reference.rules)
                    metrics = self._compare_industry_reference(
                        active_courses, rules, reference, drafts
                    )
                else:
                    invalid_references.append(
                        {
                            "id": str(reference.id),
                            "code": reference.code,
                            "reason": f"unsupported reference type {reference.reference_type}",
                        }
                    )
                    continue
            except ValidationError as exc:
                invalid_references.append(
                    {
                        "id": str(reference.id),
                        "code": reference.code,
                        "reason": str(exc.errors()[0].get("msg", "invalid rules")),
                    }
                )
                logger.warning(
                    "Skipped invalid verification reference",
                    extra={
                        "verification_reference_id": str(reference.id),
                        "verification_reference_code": reference.code,
                    },
                )
                continue

            findings_by_reference[str(reference.id)] = len(drafts) - before
            metrics_by_reference[str(reference.id)] = metrics
            references_summary.append(
                {
                    "id": str(reference.id),
                    "type": reference.reference_type,
                    "code": reference.code,
                    "title": reference.title,
                    "source": reference.source,
                    "version_label": reference.version_label,
                    "severity": reference.severity,
                    "category": category.value,
                }
            )

        return {
            "status": "EVALUATED" if references_summary else "NOT_CONFIGURED",
            "checked": bool(references_summary),
            "count": len(references_summary),
            "references": references_summary,
            "findings_by_reference": findings_by_reference,
            "metrics": metrics_by_reference,
            "invalid_references": invalid_references,
            "evidence_basis": {
                "active_course_count": len(active_courses),
                "total_credits": total_credits,
                "credits_by_course_type": dict(sorted(credits_by_type.items())),
            },
        }

    def _compare_institutional_reference(
        self,
        snapshot: _VersionSnapshot,
        rules: InstitutionalRules,
        reference: VerificationReference,
        drafts: list[_FindingDraft],
    ) -> dict[str, Any]:
        active_courses = [
            course
            for course in snapshot.courses.values()
            if course.status == CourseStatus.ACTIVE.value
        ]
        total_credits = round(sum(float(course.credits) for course in active_courses), 1)
        credits_by_type: dict[str, float] = {}
        credits_by_semester: dict[str, float] = {
            str(semester.semester_number): 0.0 for semester in snapshot.semesters
        }
        for course in active_courses:
            type_code = course.course_type.code
            semester_key = str(course.semester.semester_number)
            credits_by_type[type_code] = credits_by_type.get(type_code, 0.0) + float(
                course.credits
            )
            credits_by_semester[semester_key] = credits_by_semester.get(
                semester_key, 0.0
            ) + float(course.credits)
        credits_by_type = {key: round(value, 1) for key, value in credits_by_type.items()}
        credits_by_semester = {
            key: round(value, 1) for key, value in credits_by_semester.items()
        }
        shares = {
            key: round(value / total_credits, 4) if total_credits else 0.0
            for key, value in credits_by_type.items()
        }

        if rules.total_credits is not None:
            violation = self._range_violation(total_credits, rules.total_credits)
            if violation:
                self._add_reference_finding(
                    drafts,
                    reference,
                    FindingCategory.STRUCTURAL,
                    "Total credits outside the institutional target",
                    f"{reference.code}: total active credits are {total_credits}.",
                    f"INSTITUTIONAL_TOTAL_CREDITS: reference={reference.code}; "
                    f"actual={total_credits}; "
                    f"expected={self._describe_range(rules.total_credits)}.",
                    "Adjust the curriculum credit total or update the governed "
                    "institutional target.",
                )

        if rules.semester_credits is not None:
            for semester in snapshot.semesters:
                value = credits_by_semester.get(str(semester.semester_number), 0.0)
                violation = self._range_violation(value, rules.semester_credits)
                if violation:
                    self._add_reference_finding(
                        drafts,
                        reference,
                        FindingCategory.STRUCTURAL,
                        "Semester credits outside the institutional target",
                        f"Semester {semester.semester_number} has {value} credits; "
                        f"{violation}.",
                        f"INSTITUTIONAL_SEMESTER_CREDITS: reference={reference.code}; "
                        f"semester={semester.semester_number}; actual={value}; "
                        f"expected={self._describe_range(rules.semester_credits)}.",
                        "Rebalance courses across semesters or update the governed "
                        "semester credit target.",
                        semester_ids=[semester.id],
                    )

        if rules.semester_count is not None:
            actual_count = len(snapshot.semesters)
            violation = self._range_violation(actual_count, rules.semester_count)
            if violation:
                self._add_reference_finding(
                    drafts,
                    reference,
                    FindingCategory.STRUCTURAL,
                    "Semester count outside the institutional target",
                    f"The version has {actual_count} semesters; {violation}.",
                    f"INSTITUTIONAL_SEMESTER_COUNT: reference={reference.code}; "
                    f"actual={actual_count}; "
                    f"expected={self._describe_range(rules.semester_count)}.",
                    "Confirm the program duration and semester structure against "
                    "the institutional rule.",
                )

        for type_code, range_rule in rules.course_type_credits.items():
            value = credits_by_type.get(type_code, 0.0)
            violation = self._range_violation(value, range_rule)
            if violation:
                self._add_reference_finding(
                    drafts,
                    reference,
                    FindingCategory.STRUCTURAL,
                    f"{type_code} credits outside the institutional target",
                    f"{type_code} courses contribute {value} credits; {violation}.",
                    f"INSTITUTIONAL_COURSE_TYPE_CREDITS: reference={reference.code}; "
                    f"course_type={type_code}; actual={value}; "
                    f"expected={self._describe_range(range_rule)}.",
                    "Adjust the course-type mix or update the governed distribution target.",
                )

        for type_code, range_rule in rules.course_type_share.items():
            value = shares.get(type_code, 0.0)
            violation = self._range_violation(value, range_rule)
            if violation:
                self._add_reference_finding(
                    drafts,
                    reference,
                    FindingCategory.STRUCTURAL,
                    f"{type_code} credit share outside the institutional target",
                    f"{type_code} courses represent {round(value * 100, 1)}% of credits; "
                    f"{violation}.",
                    f"INSTITUTIONAL_COURSE_TYPE_SHARE: reference={reference.code}; "
                    f"course_type={type_code}; actual={value}; "
                    f"expected={self._describe_range(range_rule)}.",
                    "Adjust the course-type mix or update the governed distribution target.",
                )

        return {
            "total_credits": total_credits,
            "credits_by_semester": credits_by_semester,
            "credits_by_course_type": credits_by_type,
            "course_type_share": shares,
            "semester_count": len(snapshot.semesters),
        }

    def _compare_obe_reference(
        self,
        snapshot: _VersionSnapshot,
        rules: ObeRules,
        reference: VerificationReference,
        drafts: list[_FindingDraft],
    ) -> dict[str, Any]:
        pinned_po_codes = {
            outcome.po_code.upper(): outcome_id
            for outcome_id, outcome in snapshot.pinned_program_outcomes.items()
        }
        pinned_peo_codes = {
            outcome.peo_code.upper(): outcome_id
            for outcome_id, outcome in snapshot.pinned_peos.items()
        }
        missing_po_codes = sorted(
            code for code in rules.required_po_codes if code not in pinned_po_codes
        )
        if missing_po_codes:
            self._add_reference_finding(
                drafts,
                reference,
                FindingCategory.ACCREDITATION_OBE,
                "Required program outcome is not pinned to the curriculum version",
                f"{reference.code} requires {', '.join(missing_po_codes)} to be active "
                "and pinned to this curriculum version.",
                f"OBE_PO_REQUIRED: reference={reference.code}; missing="
                f"{', '.join(missing_po_codes)}; "
                f"pinned={', '.join(sorted(pinned_po_codes)) or 'none'}.",
                "Pin the required program outcomes to this version or align the "
                "OBE reference with the intended outcome set.",
            )

        missing_peo_codes = sorted(
            code for code in rules.required_peo_codes if code not in pinned_peo_codes
        )
        if missing_peo_codes:
            self._add_reference_finding(
                drafts,
                reference,
                FindingCategory.ACCREDITATION_OBE,
                "Required PEO is not pinned to the curriculum version",
                f"{reference.code} requires {', '.join(missing_peo_codes)} to be active "
                "and pinned to this curriculum version.",
                f"OBE_PEO_REQUIRED: reference={reference.code}; missing="
                f"{', '.join(missing_peo_codes)}; "
                f"pinned={', '.join(sorted(pinned_peo_codes)) or 'none'}.",
                "Pin the required PEOs to this version or align the OBE reference "
                "with the intended PEO set.",
            )

        po_coverage_ratio = (
            len(snapshot.covered_program_outcomes) / len(snapshot.pinned_program_outcomes)
            if snapshot.pinned_program_outcomes
            else 0.0
        )
        if (
            rules.min_po_coverage_ratio is not None
            and po_coverage_ratio < rules.min_po_coverage_ratio
        ):
            self._add_reference_finding(
                drafts,
                reference,
                FindingCategory.ACCREDITATION_OBE,
                "Program outcome coverage below the OBE target",
                f"{round(po_coverage_ratio * 100, 1)}% of pinned program outcomes have "
                f"approved CO-PO coverage; the target is "
                f"{round(rules.min_po_coverage_ratio * 100, 1)}%.",
                f"OBE_PO_COVERAGE: reference={reference.code}; "
                f"actual={round(po_coverage_ratio, 4)}; "
                f"target={rules.min_po_coverage_ratio}.",
                "Approve valid CO-PO mappings for uncovered program outcomes or "
                "revise the OBE target.",
            )

        mapping_coverage_ratio = (
            len(snapshot.covered_course_outcomes) / len(snapshot.active_course_outcomes)
            if snapshot.active_course_outcomes
            else 0.0
        )
        if (
            rules.min_approved_mapping_ratio is not None
            and mapping_coverage_ratio < rules.min_approved_mapping_ratio
        ):
            self._add_reference_finding(
                drafts,
                reference,
                FindingCategory.ACCREDITATION_OBE,
                "Approved CO-PO mapping coverage below the OBE target",
                f"{round(mapping_coverage_ratio * 100, 1)}% of active course outcomes "
                f"have approved CO-PO coverage; the target is "
                f"{round(rules.min_approved_mapping_ratio * 100, 1)}%.",
                f"OBE_MAPPING_COVERAGE: reference={reference.code}; "
                f"actual={round(mapping_coverage_ratio, 4)}; "
                f"target={rules.min_approved_mapping_ratio}.",
                "Review and approve justified CO-PO mappings for uncovered course outcomes.",
            )

        return {
            "pinned_po_codes": sorted(pinned_po_codes),
            "pinned_peo_codes": sorted(pinned_peo_codes),
            "missing_po_codes": missing_po_codes,
            "missing_peo_codes": missing_peo_codes,
            "po_coverage_ratio": round(po_coverage_ratio, 4),
            "approved_mapping_ratio": round(mapping_coverage_ratio, 4),
        }

    def _compare_accreditation_reference(
        self,
        snapshot: _VersionSnapshot,
        rules: AccreditationRules,
        reference: VerificationReference,
        drafts: list[_FindingDraft],
    ) -> dict[str, Any]:
        pinned_po_codes = {
            outcome.po_code.upper(): outcome_id
            for outcome_id, outcome in snapshot.pinned_program_outcomes.items()
        }
        missing_po_codes = sorted(
            code for code in rules.required_po_codes if code not in pinned_po_codes
        )
        if missing_po_codes:
            self._add_reference_finding(
                drafts,
                reference,
                FindingCategory.ACCREDITATION_OBE,
                "Accreditation criterion requires missing program outcomes",
                f"{reference.code} ({rules.criterion}) requires "
                f"{', '.join(missing_po_codes)} to be active and pinned.",
                f"ACCREDITATION_PO_REQUIRED: reference={reference.code}; "
                f"criterion={rules.criterion}; missing={', '.join(missing_po_codes)}.",
                "Pin the required program outcomes or align the criterion mapping "
                "with the curriculum.",
            )

        active_type_codes = {
            course.course_type.code
            for course in snapshot.courses.values()
            if course.status == CourseStatus.ACTIVE.value
        }
        missing_course_types = sorted(
            type_code
            for type_code in rules.required_course_types
            if type_code not in active_type_codes
        )
        if missing_course_types:
            self._add_reference_finding(
                drafts,
                reference,
                FindingCategory.ACCREDITATION_OBE,
                "Accreditation criterion requires missing course types",
                f"{reference.code} ({rules.criterion}) requires the course types "
                f"{', '.join(missing_course_types)}.",
                f"ACCREDITATION_COURSE_TYPE_REQUIRED: reference={reference.code}; "
                f"criterion={rules.criterion}; missing={', '.join(missing_course_types)}; "
                f"present={', '.join(sorted(active_type_codes)) or 'none'}.",
                "Add the required course types or align the accreditation criterion "
                "with the curriculum design.",
            )

        po_coverage_ratio = (
            len(snapshot.covered_program_outcomes) / len(snapshot.pinned_program_outcomes)
            if snapshot.pinned_program_outcomes
            else 0.0
        )
        if (
            rules.min_po_coverage_ratio is not None
            and po_coverage_ratio < rules.min_po_coverage_ratio
        ):
            self._add_reference_finding(
                drafts,
                reference,
                FindingCategory.ACCREDITATION_OBE,
                "Accreditation program outcome coverage below target",
                f"{reference.code} ({rules.criterion}) requires at least "
                f"{round(rules.min_po_coverage_ratio * 100, 1)}% PO coverage; "
                f"the current value is {round(po_coverage_ratio * 100, 1)}%.",
                f"ACCREDITATION_PO_COVERAGE: reference={reference.code}; "
                f"criterion={rules.criterion}; actual={round(po_coverage_ratio, 4)}; "
                f"target={rules.min_po_coverage_ratio}.",
                "Approve valid CO-PO mappings for uncovered program outcomes.",
            )

        mapping_coverage_ratio = (
            len(snapshot.covered_course_outcomes) / len(snapshot.active_course_outcomes)
            if snapshot.active_course_outcomes
            else 0.0
        )
        if (
            rules.min_approved_mapping_ratio is not None
            and mapping_coverage_ratio < rules.min_approved_mapping_ratio
        ):
            self._add_reference_finding(
                drafts,
                reference,
                FindingCategory.ACCREDITATION_OBE,
                "Accreditation approved mapping coverage below target",
                f"{reference.code} ({rules.criterion}) requires at least "
                f"{round(rules.min_approved_mapping_ratio * 100, 1)}% approved CO-PO "
                f"coverage; the current value is "
                f"{round(mapping_coverage_ratio * 100, 1)}%.",
                f"ACCREDITATION_MAPPING_COVERAGE: reference={reference.code}; "
                f"criterion={rules.criterion}; "
                f"actual={round(mapping_coverage_ratio, 4)}; "
                f"target={rules.min_approved_mapping_ratio}.",
                "Review and approve justified CO-PO mappings for uncovered course outcomes.",
            )

        return {
            "criterion": rules.criterion,
            "missing_po_codes": missing_po_codes,
            "missing_course_types": missing_course_types,
            "po_coverage_ratio": round(po_coverage_ratio, 4),
            "approved_mapping_ratio": round(mapping_coverage_ratio, 4),
        }

    def _compare_industry_reference(
        self,
        active_courses: list[Course],
        rules: IndustryRules,
        reference: VerificationReference,
        drafts: list[_FindingDraft],
    ) -> dict[str, Any]:
        corpus_by_course = {
            course.id: " ".join(
                part
                for part in (
                    course.course_name,
                    course.description or "",
                    course.syllabus or "",
                    " ".join(
                        outcome.description
                        for outcome in course.outcomes
                        if outcome.status == CourseOutcomeStatus.ACTIVE.value
                    ),
                )
                if part
            )
            for course in active_courses
        }
        skills: list[dict[str, Any]] = []
        covered_required = 0
        required_count = 0
        for skill in rules.skills:
            matched_courses = [
                course
                for course in active_courses
                if any(
                    keyword_present(corpus_by_course[course.id], keyword)
                    for keyword in skill.keywords
                )
            ]
            evidenced = len(matched_courses) >= skill.min_courses
            if skill.required:
                required_count += 1
                if evidenced:
                    covered_required += 1
                else:
                    self._add_reference_finding(
                        drafts,
                        reference,
                        FindingCategory.INDUSTRY_ALIGNMENT,
                        f"Required industry skill is not evidenced: {skill.label}",
                        f"{reference.code} requires evidence of {skill.label} in at least "
                        f"{skill.min_courses} course(s); {len(matched_courses)} course(s) "
                        "match the configured keywords.",
                        f"INDUSTRY_SKILL_COVERAGE: reference={reference.code}; "
                        f"skill={skill.code}; required={skill.required}; "
                        f"matched={len(matched_courses)}; min_courses={skill.min_courses}; "
                        f"keywords={', '.join(skill.keywords)}.",
                        "Add or update course content and outcomes that evidence this skill, "
                        "or revise the governed industry reference.",
                        confidence=Decimal("0.800"),
                        course_ids=[course.id for course in matched_courses],
                    )
            skills.append(
                {
                    "code": skill.code,
                    "label": skill.label,
                    "required": skill.required,
                    "min_courses": skill.min_courses,
                    "matched_courses": [course.course_code for course in matched_courses],
                    "evidenced": evidenced,
                }
            )

        coverage_ratio = covered_required / required_count if required_count else 1.0
        if (
            rules.min_required_skill_coverage_ratio is not None
            and coverage_ratio < rules.min_required_skill_coverage_ratio
        ):
            self._add_reference_finding(
                drafts,
                reference,
                FindingCategory.INDUSTRY_ALIGNMENT,
                "Required industry skill coverage below target",
                f"{round(coverage_ratio * 100, 1)}% of required industry skills are "
                f"evidenced; the target is "
                f"{round(rules.min_required_skill_coverage_ratio * 100, 1)}%.",
                f"INDUSTRY_SKILL_TOTAL: reference={reference.code}; "
                f"actual={round(coverage_ratio, 4)}; "
                f"target={rules.min_required_skill_coverage_ratio}.",
                "Strengthen course evidence for the missing industry skills or "
                "revise the governed reference.",
                confidence=Decimal("0.850"),
            )

        return {
            "skills": skills,
            "required_skill_count": required_count,
            "covered_required_skill_count": covered_required,
            "required_skill_coverage_ratio": round(coverage_ratio, 4),
        }

    def _add_reference_finding(
        self,
        drafts: list[_FindingDraft],
        reference: VerificationReference,
        category: FindingCategory,
        title: str,
        description: str,
        evidence: str,
        recommendation: str,
        confidence: Decimal = Decimal("1.000"),
        course_ids: list[uuid.UUID] | None = None,
        semester_ids: list[uuid.UUID] | None = None,
    ) -> None:
        drafts.append(
            _FindingDraft(
                category=category,
                severity=FindingSeverity(reference.severity),
                title=title,
                description=description,
                evidence=evidence,
                recommendation=recommendation,
                confidence=confidence,
                course_ids=course_ids,
                semester_ids=semester_ids,
                reference_ids=[reference.id],
            )
        )

    @staticmethod
    def _range_violation(value: float, rule: Any) -> str | None:
        if rule.min is not None and value < rule.min:
            return f"it is below the minimum {rule.min}"
        if rule.max is not None and value > rule.max:
            return f"it is above the maximum {rule.max}"
        return None

    @staticmethod
    def _describe_range(rule: Any) -> str:
        if rule.min is not None and rule.max is not None:
            return f"{rule.min}-{rule.max}"
        if rule.min is not None:
            return f">={rule.min}"
        if rule.max is not None:
            return f"<={rule.max}"
        return "unspecified"

    @staticmethod
    def _course_prefix(course_code: str) -> str:
        return "".join(character for character in course_code if character.isalpha())

    def _build_analysis_summary(
        self,
        snapshot: _VersionSnapshot,
        prerequisite_summary: dict[str, Any],
        structure_summary: dict[str, Any],
        topic_summary: dict[str, Any],
        reference_summary: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "analyzers": [
                "PREREQUISITE",
                "CONTENT",
                "STRUCTURE",
                "OUTCOME_COVERAGE",
                "REFERENCE_COMPARISON",
            ],
            "prerequisite_graph": prerequisite_summary,
            "structure": structure_summary,
            "credit_totals_by_semester": structure_summary.get(
                "credit_totals_by_semester", {}
            ),
            "total_credits": structure_summary.get("total_credits", 0.0),
            "credits_by_course_type": structure_summary.get(
                "credits_by_course_type", {}
            ),
            "topic_overlap": topic_summary,
            "reference_comparison": reference_summary,
            "input_fingerprint": snapshot.fingerprint,
            "input_fingerprint_version": 1,
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
        for reference_id in draft.reference_ids:
            references.append(
                VerificationFindingReference(
                    finding=finding,
                    entity_type=ReferenceEntityType.VERIFICATION_REFERENCE.value,
                    entity_id=reference_id,
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
