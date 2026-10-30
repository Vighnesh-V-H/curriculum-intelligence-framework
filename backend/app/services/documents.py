import hashlib
import io
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import (
    BadRequestError,
    ConflictError,
    NotFoundError,
    PayloadTooLargeError,
)
from app.db.models.audit import AuditLog
from app.db.models.document import Document, DocumentStatus
from app.db.models.user import User, utc_now
from app.repositories.audit import AuditLogRepository
from app.repositories.documents import DocumentRepository
from app.schemas.document import DocumentResponse
from app.services.llm import LLMClient, LLMNotConfiguredError, LLMResponseError

_PDF_MAGIC = b"%PDF-"
_DOCX_MAGIC = b"PK\x03\x04"
_ERROR_MESSAGE_MAX_CHARS = 480


def _normalize_extension(raw: str | None) -> str:
    extension = Path(raw or "").suffix.lower()
    return extension or ""


def _read_pdf(data: bytes) -> str:
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(data))
        return "\n".join(
            page.extract_text() or "" for page in reader.pages
        ).strip()
    except Exception as exc:
        raise DocumentIngestFailure(f"PDF could not be read: {exc}") from exc


def _read_docx(data: bytes) -> str:
    from docx import Document as DocxDocument

    try:
        parsed = DocxDocument(io.BytesIO(data))
        parts = [paragraph.text for paragraph in parsed.paragraphs]
        for table in parsed.tables:
            for row in table.rows:
                for cell in row.cells:
                    parts.append(cell.text)
        return "\n".join(parts).strip()
    except Exception as exc:
        raise DocumentIngestFailure(f"DOCX could not be read: {exc}") from exc


def _read_plaintext(data: bytes) -> str:
    return data.decode("utf-8", errors="replace").strip()


_READERS: dict[str, Callable[[bytes], str]] = {
    ".pdf": _read_pdf,
    ".docx": _read_docx,
    ".txt": _read_plaintext,
    ".md": _read_plaintext,
    ".csv": _read_plaintext,
}


class DocumentIngestFailure(Exception):
    """Document-specific, user-recoverable ingestion failure."""


class DocumentProcessingService:
    def __init__(
        self,
        session: Session,
        settings: Settings,
        documents: DocumentRepository,
        audit_logs: AuditLogRepository,
        llm_client: LLMClient,
    ) -> None:
        self._session = session
        self._settings = settings
        self._documents = documents
        self._audit_logs = audit_logs
        self._llm_client = llm_client

    def upload(self, actor: User, uploaded_file: UploadFile) -> DocumentResponse:
        extension = _normalize_extension(uploaded_file.filename)
        allowed = tuple(
            ext.lower() if ext.startswith(".") else f".{ext.lower()}"
            for ext in self._settings.allowed_upload_extensions
        )
        if extension not in allowed:
            raise BadRequestError(
                f"File type '{extension or 'unknown'}' is not allowed",
                "unsupported_file_type",
            )

        document_id = uuid.uuid4()
        stored_name = f"{document_id}{extension}"
        period = utc_now().strftime("%Y/%m")
        target_dir = self._settings.upload_dir / period
        target_dir.mkdir(parents=True, exist_ok=True)
        temp_path = target_dir / f"{stored_name}.part"
        final_path = target_dir / stored_name
        storage_key = f"{period}/{stored_name}"

        max_bytes = self._settings.max_upload_size_mb * 1024 * 1024
        digest = hashlib.sha256()
        total = 0
        first_bytes = b""
        try:
            with temp_path.open("wb") as handle:
                while True:
                    chunk = uploaded_file.file.read(1024 * 1024)
                    if not chunk:
                        break
                    if total == 0:
                        first_bytes = chunk[:8]
                    total += len(chunk)
                    if total > max_bytes:
                        raise PayloadTooLargeError(
                            "File exceeds the configured maximum upload size of "
                            f"{self._settings.max_upload_size_mb} MB",
                        )
                    digest.update(chunk)
                    handle.write(chunk)
            if total == 0:
                raise BadRequestError("Uploaded file is empty", "empty_file")
            self._verify_signature(extension, first_bytes)
            temp_path.replace(final_path)
        except (PayloadTooLargeError, BadRequestError):
            temp_path.unlink(missing_ok=True)
            raise
        except OSError as exc:
            temp_path.unlink(missing_ok=True)
            raise BadRequestError(
                f"File content could not be validated: {exc}", "invalid_file_content"
            ) from exc

        document = Document(
            id=document_id,
            original_filename=self._safe_basename(uploaded_file.filename),
            file_extension=extension,
            content_type=uploaded_file.content_type,
            size_bytes=total,
            checksum_sha256=digest.hexdigest(),
            storage_path=storage_key,
            status=DocumentStatus.UPLOADED.value,
            uploaded_by=actor.id,
        )
        self._documents.add(document)
        self._audit(actor.id, "CREATE", document.id, {"status": document.status})
        self._session.commit()
        return DocumentResponse.from_model(document)

    def ingest(self, actor: User, document_id: uuid.UUID) -> DocumentResponse:
        document = self._documents.get_by_id(document_id)
        if document is None:
            raise NotFoundError("Document not found")

        if document.status == DocumentStatus.PROCESSING.value:
            raise ConflictError(
                "Document ingestion is already running", "document_processing"
            )

        document.status = DocumentStatus.PROCESSING.value
        document.processed_at = None
        document.error_message = None
        self._audit(actor.id, "UPDATE", document.id, {"status": document.status})
        self._session.commit()

        try:
            data = self._read_stored_file(document)
            text = _READERS[document.file_extension](data)
            if not text.strip():
                raise DocumentIngestFailure(
                    "No extractable text found in the document "
                    "(scanned documents without OCR are not supported)"
                )
        except DocumentIngestFailure as exc:
            self._fail(actor, document, str(exc))
            return DocumentResponse.from_model(document)

        try:
            analysis = self._llm_client.analyze_document(text, document.original_filename)
        except LLMNotConfiguredError:
            document.status = DocumentStatus.UPLOADED.value
            self._audit(actor.id, "UPDATE", document.id, {"status": document.status})
            self._session.commit()
            raise
        except LLMResponseError as exc:
            self._fail(actor, document, f"LLM analysis failed: {exc}")
            return DocumentResponse.from_model(document)

        document.extracted_text = text
        document.llm_analysis = analysis
        document.llm_model = self._llm_client.model
        document.status = DocumentStatus.COMPLETED.value
        document.processed_at = utc_now()
        self._audit(actor.id, "UPDATE", document.id, {"status": document.status})
        self._session.commit()
        return DocumentResponse.from_model(document)

    def get(self, document_id: uuid.UUID) -> DocumentResponse:
        document = self._documents.get_by_id(document_id)
        if document is None:
            raise NotFoundError("Document not found")
        return DocumentResponse.from_model(document)

    def list_documents(self) -> list[DocumentResponse]:
        return [
            DocumentResponse.from_model(document) for document in self._documents.list_all()
        ]

    def _verify_signature(self, extension: str, first_bytes: bytes) -> None:
        expected = {".pdf": _PDF_MAGIC, ".docx": _DOCX_MAGIC}.get(extension)
        if expected is not None and not first_bytes.startswith(expected):
            raise BadRequestError(
                "File content does not match the declared format",
                "invalid_file_content",
            )

    def _read_stored_file(self, document: Document) -> bytes:
        root = self._settings.upload_dir
        path = root / document.storage_path
        try:
            return path.read_bytes()
        except OSError as exc:
            raise DocumentIngestFailure(f"Stored file could not be read: {exc}") from exc

    def _fail(
        self,
        actor: User,
        document: Document,
        message: str,
    ) -> None:
        document.status = DocumentStatus.FAILED.value
        document.error_message = message[:_ERROR_MESSAGE_MAX_CHARS]
        document.processed_at = utc_now()
        self._audit(actor.id, "UPDATE", document.id, {"status": document.status})
        self._session.commit()

    def _audit(
        self,
        actor_id: uuid.UUID,
        action: str,
        document_id: uuid.UUID,
        new_values: dict[str, Any],
    ) -> None:
        self._audit_logs.add(
            AuditLog(
                entity_type="document",
                entity_id=document_id,
                action=action,
                actor_user_id=actor_id,
                new_values=new_values,
            )
        )

    def _safe_basename(self, filename: str | None) -> str:
        name = Path(filename or "").name
        if not name or name in {".", ".."}:
            raise BadRequestError("Upload file name is not usable", "invalid_file_content")
        return name
