import uuid

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.errors import ForbiddenError, UnauthorizedError
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
from app.repositories.courses import CourseRepository
from app.repositories.curricula import (
    CurriculumRepository,
    CurriculumVersionRepository,
    SemesterRepository,
)
from app.repositories.outcomes import OutcomeRepository, OutcomeVersionRepository
from app.repositories.roles import RoleRepository
from app.repositories.users import UserRepository
from app.services.academic import AcademicService
from app.services.auth import AuthService
from app.services.curriculum import CurriculumService
from app.services.outcomes import OutcomeService
from app.services.users import UserService

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


def get_audit_log_repository(session: Session = Depends(get_db)) -> AuditLogRepository:
    return AuditLogRepository(session)


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


def get_current_user(
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
    return user


def require_roles(*codes: RoleCode):
    allowed = {code.value for code in codes}

    def dependency(current_user: User = Depends(get_current_user)) -> User:
        granted = {assignment.role.code for assignment in current_user.role_assignments}
        if not allowed.intersection(granted):
            raise ForbiddenError("You do not have permission to perform this action")
        return current_user

    return dependency
