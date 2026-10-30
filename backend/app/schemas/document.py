import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.db.models.document import Document


class DocumentResponse(BaseModel):
    id: uuid.UUID
    original_filename: str
    file_extension: str
    content_type: str | None
    size_bytes: int
    checksum_sha256: str
    status: str
    llm_model: str | None
    extracted_text: str | None
    llm_analysis: dict[str, Any] | None
    error_message: str | None
    uploaded_by: uuid.UUID
    uploaded_at: datetime
    processed_at: datetime | None

    @classmethod
    def from_model(cls, document: Document) -> "DocumentResponse":
        return cls(
            id=document.id,
            original_filename=document.original_filename,
            file_extension=document.file_extension,
            content_type=document.content_type,
            size_bytes=document.size_bytes,
            checksum_sha256=document.checksum_sha256,
            status=document.status,
            llm_model=document.llm_model,
            extracted_text=document.extracted_text,
            llm_analysis=document.llm_analysis,
            error_message=document.error_message,
            uploaded_by=document.uploaded_by,
            uploaded_at=document.uploaded_at,
            processed_at=document.processed_at,
        )
