from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.academic import CourseType, Department, Program


class DepartmentRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, department_id) -> Department | None:
        return self._session.get(Department, department_id)

    def get_by_code(self, code: str) -> Department | None:
        statement = select(Department).where(func.upper(Department.code) == code.strip().upper())
        return self._session.scalars(statement).first()

    def list(self) -> list[Department]:
        return list(self._session.scalars(select(Department).order_by(Department.code)))

    def add(self, department: Department) -> Department:
        self._session.add(department)
        self._session.flush()
        return department


class ProgramRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, program_id) -> Program | None:
        return self._session.get(Program, program_id)

    def get_by_code(self, code: str) -> Program | None:
        statement = select(Program).where(func.upper(Program.code) == code.strip().upper())
        return self._session.scalars(statement).first()

    def list(self) -> list[Program]:
        return list(self._session.scalars(select(Program).order_by(Program.code)))

    def add(self, program: Program) -> Program:
        self._session.add(program)
        self._session.flush()
        return program


class CourseTypeRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_code(self, code: str) -> CourseType | None:
        statement = select(CourseType).where(func.upper(CourseType.code) == code.strip().upper())
        return self._session.scalars(statement).first()

    def list_active(self) -> list[CourseType]:
        statement = (
            select(CourseType).where(CourseType.is_active.is_(True)).order_by(CourseType.code)
        )
        return list(self._session.scalars(statement))
