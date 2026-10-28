from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.db.models.academic import Department, Program
from app.repositories.academic import (
    CourseTypeRepository,
    DepartmentRepository,
    ProgramRepository,
)
from app.schemas.academic import (
    CourseTypeResponse,
    DepartmentCreate,
    DepartmentResponse,
    ProgramCreate,
    ProgramResponse,
)


class AcademicService:
    def __init__(
        self,
        session: Session,
        departments: DepartmentRepository,
        programs: ProgramRepository,
        course_types: CourseTypeRepository,
    ) -> None:
        self._session = session
        self._departments = departments
        self._programs = programs
        self._course_types = course_types

    def create_department(self, request: DepartmentCreate) -> DepartmentResponse:
        if self._departments.get_by_code(request.code) is not None:
            raise ConflictError("Department code already exists", "department_exists")

        department = Department(code=request.code, name=request.name)
        try:
            self._departments.add(department)
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise ConflictError("Department code already exists", "department_exists") from exc
        return DepartmentResponse.from_model(department)

    def list_departments(self) -> list[DepartmentResponse]:
        return [
            DepartmentResponse.from_model(department) for department in self._departments.list()
        ]

    def create_program(self, request: ProgramCreate) -> ProgramResponse:
        department = self._departments.get_by_id(request.department_id)
        if department is None:
            raise NotFoundError("Department not found")
        if self._programs.get_by_code(request.code) is not None:
            raise ConflictError("Program code already exists", "program_exists")

        program = Program(
            department_id=request.department_id,
            code=request.code,
            name=request.name,
            degree_type=request.degree_type,
            duration_years=request.duration_years,
        )
        try:
            self._programs.add(program)
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise ConflictError("Program code already exists", "program_exists") from exc
        return ProgramResponse.from_model(program)

    def list_programs(self) -> list[ProgramResponse]:
        return [ProgramResponse.from_model(program) for program in self._programs.list()]

    def list_course_types(self) -> list[CourseTypeResponse]:
        return [
            CourseTypeResponse.from_model(course_type)
            for course_type in self._course_types.list_active()
        ]
