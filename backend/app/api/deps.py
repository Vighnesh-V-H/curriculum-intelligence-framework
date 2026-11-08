import uuid

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ForbiddenError, ServiceUnavailableError, UnauthorizedError
from app.core.logging_config import set_actor_id
from app.core.security import (
    JwtService,
    PasswordService,
    TokenError,
    get_jwt_service,
    get_password_service,
)
from app.db.models.outcomes import (
    PeoVersion,
    ProgramEducationalObjective,
    ProgramOutcome,
    ProgramOutcomeVersion,
)
from app.db.models.user import RoleCode, User, UserStatus
from app.db.session import get_db
from app.repositories.academic import (
    CourseTypeRepository,
    DepartmentRepository,
    ProgramRepository,
)
from app.repositories.audit import AuditLogRepository
from app.repositories.courses import CourseOutcomeRepository, CourseRepository
from app.repositories.curricula import (
    CurriculumRepository,
    CurriculumVersionRepository,
    SemesterRepository,
)
from app.repositories.documents import DocumentRepository
from app.repositories.mappings import (
    CoPoMappingRepository,
    CoPoMappingVersionRepository,
    CurriculumVersionPeoRepository,
    CurriculumVersionProgramOutcomeRepository,
    MappingLevelRepository,
)
from app.repositories.outcomes import OutcomeRepository, OutcomeVersionRepository
from app.repositories.prerequisites import CoursePrerequisiteRepository
from app.repositories.roles import RoleRepository
from app.repositories.users import UserRepository
from app.repositories.verification import (
    VerificationFindingRepository,
    VerificationRunRepository,
)
from app.services.academic import AcademicService
from app.services.auth import AuthService
from app.services.curriculum import CurriculumService
from app.services.curriculum_draft import CurriculumDraftService
from app.services.curriculum_draft_persistence import CurriculumDraftPersistenceService
from app.services.documents import DocumentProcessingService
from app.services.knowledge_graph import KnowledgeGraphRepository
from app.services.knowledge_graph_projection import KnowledgeGraphProjectionService
from app.services.llm import LLMClient
from app.services.llm import get_llm_client as build_llm_client
from app.services.mappings import MappingService
from app.services.outcomes import OutcomeService
from app.services.prerequisites import PrerequisiteService
from app.services.uploadthing import UploadThingClient, build_uploadthing_client
from app.services.users import UserService
from app.services.verification import VerificationService

bearer_scheme = HTTPBearer(auto_error=False)


def get_user_repository(session: Session = Depends(get_db)) -> UserRepository:
    return UserRepository(session)


def get_role_repository(session: Session = Depends(get_db)) -> RoleRepository:
    return RoleRepository(session)


def get_auth_service(
    session: Session = Depends(get_db),
    users: UserRepository = Depends(get_user_repository),
    passwords: PasswordService = Depends(get_password_service),
    tokens: JwtService = Depends(get_jwt_service),
) -> AuthService:
    return AuthService(session, users, passwords, tokens)


def get_user_service(
    session: Session = Depends(get_db),
    users: UserRepository = Depends(get_user_repository),
    roles: RoleRepository = Depends(get_role_repository),
    passwords: PasswordService = Depends(get_password_service),
) -> UserService:
    return UserService(session, users, roles, passwords)


def get_department_repository(
    session: Session = Depends(get_db),
) -> DepartmentRepository:
    return DepartmentRepository(session)


def get_program_repository(session: Session = Depends(get_db)) -> ProgramRepository:
    return ProgramRepository(session)


def get_course_type_repository(
    session: Session = Depends(get_db),
) -> CourseTypeRepository:
    return CourseTypeRepository(session)


def get_curriculum_repository(
    session: Session = Depends(get_db),
) -> CurriculumRepository:
    return CurriculumRepository(session)


def get_curriculum_version_repository(
    session: Session = Depends(get_db),
) -> CurriculumVersionRepository:
    return CurriculumVersionRepository(session)


def get_semester_repository(session: Session = Depends(get_db)) -> SemesterRepository:
    return SemesterRepository(session)


def get_course_repository(session: Session = Depends(get_db)) -> CourseRepository:
    return CourseRepository(session)


def get_course_outcome_repository(
    session: Session = Depends(get_db),
) -> CourseOutcomeRepository:
    return CourseOutcomeRepository(session)


def get_audit_log_repository(session: Session = Depends(get_db)) -> AuditLogRepository:
    return AuditLogRepository(session)


def get_prerequisite_repository(
    session: Session = Depends(get_db),
) -> CoursePrerequisiteRepository:
    return CoursePrerequisiteRepository(session)


def get_mapping_level_repository(
    session: Session = Depends(get_db),
) -> MappingLevelRepository:
    return MappingLevelRepository(session)


def get_curriculum_version_outcome_repository(
    session: Session = Depends(get_db),
) -> CurriculumVersionProgramOutcomeRepository:
    return CurriculumVersionProgramOutcomeRepository(session)


def get_mapping_repository(
    session: Session = Depends(get_db),
) -> CoPoMappingRepository:
    return CoPoMappingRepository(session)


def get_mapping_version_repository(
    session: Session = Depends(get_db),
) -> CoPoMappingVersionRepository:
    return CoPoMappingVersionRepository(session)


def get_program_outcome_repository(
    session: Session = Depends(get_db),
) -> OutcomeRepository:
    return OutcomeRepository(session, ProgramOutcome, "po_code")


def get_program_outcome_version_repository(
    session: Session = Depends(get_db),
) -> OutcomeVersionRepository:
    return OutcomeVersionRepository(session, ProgramOutcomeVersion, "program_outcome_id")


def get_peo_repository(session: Session = Depends(get_db)) -> OutcomeRepository:
    return OutcomeRepository(session, ProgramEducationalObjective, "peo_code")


def get_peo_version_repository(
    session: Session = Depends(get_db),
) -> OutcomeVersionRepository:
    return OutcomeVersionRepository(session, PeoVersion, "peo_id")


def get_academic_service(
    session: Session = Depends(get_db),
    departments: DepartmentRepository = Depends(get_department_repository),
    programs: ProgramRepository = Depends(get_program_repository),
    course_types: CourseTypeRepository = Depends(get_course_type_repository),
) -> AcademicService:
    return AcademicService(session, departments, programs, course_types)


def get_curriculum_service(
    session: Session = Depends(get_db),
    programs: ProgramRepository = Depends(get_program_repository),
    course_types: CourseTypeRepository = Depends(get_course_type_repository),
    curricula: CurriculumRepository = Depends(get_curriculum_repository),
    versions: CurriculumVersionRepository = Depends(get_curriculum_version_repository),
    semesters: SemesterRepository = Depends(get_semester_repository),
    courses: CourseRepository = Depends(get_course_repository),
    course_outcomes: CourseOutcomeRepository = Depends(get_course_outcome_repository),
    audit_logs: AuditLogRepository = Depends(get_audit_log_repository),
) -> CurriculumService:
    return CurriculumService(
        session,
        programs,
        course_types,
        curricula,
        versions,
        semesters,
        courses,
        course_outcomes,
        audit_logs,
    )


def get_outcome_service(
    session: Session = Depends(get_db),
    programs: ProgramRepository = Depends(get_program_repository),
    program_outcomes: OutcomeRepository = Depends(get_program_outcome_repository),
    program_outcome_versions: OutcomeVersionRepository = Depends(
        get_program_outcome_version_repository
    ),
    peos: OutcomeRepository = Depends(get_peo_repository),
    peo_versions: OutcomeVersionRepository = Depends(get_peo_version_repository),
    audit_logs: AuditLogRepository = Depends(get_audit_log_repository),
) -> OutcomeService:
    return OutcomeService(
        session,
        programs,
        program_outcomes,
        program_outcome_versions,
        peos,
        peo_versions,
        audit_logs,
    )


def get_mapping_service(
    session: Session = Depends(get_db),
    curricula: CurriculumRepository = Depends(get_curriculum_repository),
    versions: CurriculumVersionRepository = Depends(get_curriculum_version_repository),
    course_outcomes: CourseOutcomeRepository = Depends(get_course_outcome_repository),
    program_outcomes: OutcomeRepository = Depends(get_program_outcome_repository),
    program_outcome_versions: OutcomeVersionRepository = Depends(
        get_program_outcome_version_repository
    ),
    levels: MappingLevelRepository = Depends(get_mapping_level_repository),
    pins: CurriculumVersionProgramOutcomeRepository = Depends(
        get_curriculum_version_outcome_repository
    ),
    mappings: CoPoMappingRepository = Depends(get_mapping_repository),
    mapping_versions: CoPoMappingVersionRepository = Depends(get_mapping_version_repository),
    audit_logs: AuditLogRepository = Depends(get_audit_log_repository),
) -> MappingService:
    return MappingService(
        session,
        curricula,
        versions,
        course_outcomes,
        program_outcomes,
        program_outcome_versions,
        levels,
        pins,
        mappings,
        mapping_versions,
        audit_logs,
    )


def get_prerequisite_service(
    session: Session = Depends(get_db),
    curricula: CurriculumRepository = Depends(get_curriculum_repository),
    versions: CurriculumVersionRepository = Depends(get_curriculum_version_repository),
    courses: CourseRepository = Depends(get_course_repository),
    prerequisites: CoursePrerequisiteRepository = Depends(get_prerequisite_repository),
    audit_logs: AuditLogRepository = Depends(get_audit_log_repository),
) -> PrerequisiteService:
    return PrerequisiteService(
        session,
        curricula,
        versions,
        courses,
        prerequisites,
        audit_logs,
    )


def get_verification_run_repository(
    session: Session = Depends(get_db),
) -> VerificationRunRepository:
    return VerificationRunRepository(session)


def get_verification_finding_repository(
    session: Session = Depends(get_db),
) -> VerificationFindingRepository:
    return VerificationFindingRepository(session)


def get_document_repository(session: Session = Depends(get_db)) -> DocumentRepository:
    return DocumentRepository(session)


def get_llm_client() -> LLMClient:
    return build_llm_client()


def get_uploadthing_client() -> UploadThingClient | None:
    return build_uploadthing_client()


def get_knowledge_graph_repository(request: Request) -> KnowledgeGraphRepository:
    driver = getattr(request.app.state, "neo4j_driver", None)
    if driver is None:
        raise ServiceUnavailableError("Curriculum graph is not configured", "graph_unavailable")
    settings = get_settings()
    return KnowledgeGraphRepository(driver, settings.neo4j_database)


def get_knowledge_graph_service(
    session: Session = Depends(get_db),
    graph: KnowledgeGraphRepository = Depends(get_knowledge_graph_repository),
) -> KnowledgeGraphProjectionService:
    return KnowledgeGraphProjectionService(session, graph)


def get_document_service(
    session: Session = Depends(get_db),
    documents: DocumentRepository = Depends(get_document_repository),
    audit_logs: AuditLogRepository = Depends(get_audit_log_repository),
    llm_client: LLMClient = Depends(get_llm_client),
    storage: UploadThingClient | None = Depends(get_uploadthing_client),
) -> DocumentProcessingService:
    return DocumentProcessingService(
        session,
        get_settings(),
        documents,
        audit_logs,
        llm_client,
        storage,
    )


def get_curriculum_draft_service(
    llm_client: LLMClient = Depends(get_llm_client),
) -> CurriculumDraftService:
    return CurriculumDraftService(llm_client, get_settings())


def get_curriculum_version_peo_repository(
    session: Session = Depends(get_db),
) -> CurriculumVersionPeoRepository:
    return CurriculumVersionPeoRepository(session)


def get_curriculum_draft_persistence_service(
    session: Session = Depends(get_db),
    programs: ProgramRepository = Depends(get_program_repository),
    course_types: CourseTypeRepository = Depends(get_course_type_repository),
    curricula: CurriculumRepository = Depends(get_curriculum_repository),
    versions: CurriculumVersionRepository = Depends(get_curriculum_version_repository),
    semesters: SemesterRepository = Depends(get_semester_repository),
    courses: CourseRepository = Depends(get_course_repository),
    course_outcomes: CourseOutcomeRepository = Depends(get_course_outcome_repository),
    program_outcomes: OutcomeRepository = Depends(get_program_outcome_repository),
    program_outcome_versions: OutcomeVersionRepository = Depends(
        get_program_outcome_version_repository
    ),
    peos: OutcomeRepository = Depends(get_peo_repository),
    peo_versions: OutcomeVersionRepository = Depends(get_peo_version_repository),
    mapping_levels: MappingLevelRepository = Depends(get_mapping_level_repository),
    version_outcomes: CurriculumVersionProgramOutcomeRepository = Depends(
        get_curriculum_version_outcome_repository
    ),
    version_peos: CurriculumVersionPeoRepository = Depends(get_curriculum_version_peo_repository),
    mappings: CoPoMappingRepository = Depends(get_mapping_repository),
    mapping_versions: CoPoMappingVersionRepository = Depends(get_mapping_version_repository),
    audit_logs: AuditLogRepository = Depends(get_audit_log_repository),
) -> CurriculumDraftPersistenceService:
    return CurriculumDraftPersistenceService(
        session,
        programs,
        course_types,
        curricula,
        versions,
        semesters,
        courses,
        course_outcomes,
        program_outcomes,
        program_outcome_versions,
        peos,
        peo_versions,
        mapping_levels,
        version_outcomes,
        version_peos,
        mappings,
        mapping_versions,
        audit_logs,
    )


def get_verification_service(
    session: Session = Depends(get_db),
    curricula: CurriculumRepository = Depends(get_curriculum_repository),
    versions: CurriculumVersionRepository = Depends(get_curriculum_version_repository),
    courses: CourseRepository = Depends(get_course_repository),
    prerequisites: CoursePrerequisiteRepository = Depends(get_prerequisite_repository),
    runs: VerificationRunRepository = Depends(get_verification_run_repository),
    findings: VerificationFindingRepository = Depends(get_verification_finding_repository),
    audit_logs: AuditLogRepository = Depends(get_audit_log_repository),
) -> VerificationService:
    return VerificationService(
        session,
        curricula,
        versions,
        courses,
        prerequisites,
        runs,
        findings,
        audit_logs,
    )


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    users: UserRepository = Depends(get_user_repository),
    tokens: JwtService = Depends(get_jwt_service),
) -> User:
    if credentials is None:
        raise UnauthorizedError("Bearer token required")

    try:
        payload = tokens.decode_token(credentials.credentials)
    except TokenError as exc:
        raise UnauthorizedError("Invalid or expired token", "invalid_token") from exc

    try:
        user_id = uuid.UUID(payload.get("sub", ""))
    except (TypeError, ValueError) as exc:
        raise UnauthorizedError("Invalid token subject", "invalid_token") from exc

    user = users.get_by_id(user_id)
    if user is None or user.status != UserStatus.ACTIVE.value:
        raise UnauthorizedError("User is not active", "invalid_token")
    actor_id = str(user.id)
    request.state.actor_id = actor_id
    set_actor_id(actor_id)
    return user


def require_roles(*codes: RoleCode):
    allowed = {code.value for code in codes}

    def dependency(current_user: User = Depends(get_current_user)) -> User:
        granted = {assignment.role.code for assignment in current_user.role_assignments}
        if not allowed.intersection(granted):
            raise ForbiddenError("You do not have permission to perform this action")
        return current_user

    return dependency
