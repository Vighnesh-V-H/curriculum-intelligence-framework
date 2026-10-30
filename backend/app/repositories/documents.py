import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.document import Document


class DocumentRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, document_id: uuid.UUID) -> Document | None:
        return self._session.get(Document, document_id)

    def list_all(self) -> list[Document]:
        statement = select(Document).order_by(Document.uploaded_at.desc(), Document.id)
        return list(self._session.scalars(statement))

    def add(self, document: Document) -> Document:
        self._session.add(document)
        self._session.flush()
        return document
