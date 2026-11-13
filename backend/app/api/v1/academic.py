from fastapi import APIRouter, Depends, status

from app.api.deps import get_academic_service, get_current_user
from app.db.models.user import RoleCode, User
from app.schemas.academic import (
    CourseTypeResponse,
    DepartmentCreate,
    DepartmentResponse,
    ProgramCreate,
    ProgramResponse,
)
from app.services.academic import AcademicService

router = APIRouter(tags=["academic"])

CURRICULUM_WRITE_ROLES = (
    RoleCode.ADMIN,
    RoleCode.COMMITTEE_MEMBER,
    RoleCode.FACULTY,
)


@router.post(
    "/departments",
    response_model=DepartmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_department(
    payload: DepartmentCreate,
    current_user: User = Depends(get_current_user),
    service: AcademicService = Depends(get_academic_service),
) -> DepartmentResponse:
    return service.create_department(payload)


@router.get("/departments", response_model=list[DepartmentResponse])
def list_departments(
    current_user: User = Depends(get_current_user),
    service: AcademicService = Depends(get_academic_service),
) -> list[DepartmentResponse]:
    return service.list_departments()


@router.post(
    "/programs",
    response_model=ProgramResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_program(
    payload: ProgramCreate,
    current_user: User = Depends(get_current_user),
    service: AcademicService = Depends(get_academic_service),
) -> ProgramResponse:
    return service.create_program(payload)


@router.get("/programs", response_model=list[ProgramResponse])
def list_programs(
    current_user: User = Depends(get_current_user),
    service: AcademicService = Depends(get_academic_service),
) -> list[ProgramResponse]:
    return service.list_programs()


@router.get("/course-types", response_model=list[CourseTypeResponse])
def list_course_types(
    current_user: User = Depends(get_current_user),
    service: AcademicService = Depends(get_academic_service),
) -> list[CourseTypeResponse]:
    return service.list_course_types()
