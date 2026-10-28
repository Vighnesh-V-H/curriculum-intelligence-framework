from sqlalchemy.orm import Session

from app.db.models.audit import AuditLog


class AuditLogRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, entry: AuditLog) -> AuditLog:
        self._session.add(entry)
        return entry
