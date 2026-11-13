import io
import logging
from pathlib import Path

from fastapi import UploadFile

from app.core.config import Settings
from app.core.errors import (
    BadRequestError,
    PayloadTooLargeError,
    ServiceUnavailableError,
)
from app.db.models.user import User
from app.schemas.curriculum_draft import CurriculumDraftResponse
from app.services.doc_extract import (
    DocumentIngestFailure,
    extract_text,
    normalize_extension,
    verify_signature,
)
from app.services.llm import (
    DOCUMENT_TEXT_MAX_CHARS,
    LLMClient,
    LLMNotConfiguredError,
    LLMResponseError,
)

logger = logging.getLogger(__name__)

_CHUNK_SIZE = 1024 * 1024
_MAX_FILES = 5
_MAX_TOPIC_CHARS = 500
_MIN_TOPIC_CHARS = 3
_MAX_DRAFT_ATTEMPTS = 2


class CurriculumDraftService:
    def __init__(self, llm_client: LLMClient, settings: Settings) -> None:
        self._llm_client = llm_client
        self._settings = settings

    def generate(
        self,
        actor: User,
        files: list[UploadFile],
        topic: str | None = None,
    ) -> CurriculumDraftResponse:
        topic_text = (topic or "").strip()
        source_mode = (
            "topic"
            if topic_text and not files
            else "documents_with_topic"
            if topic_text
            else "documents"
        )
        logger.info(
            "Curriculum draft generation started",
            extra={
                "actor_id": str(actor.id),
                "file_count": len(files),
                "has_topic": bool(topic_text),
                "source_mode": source_mode,
            },
        )
        if len(files) > _MAX_FILES:
            raise BadRequestError(
                f"Upload no more than {_MAX_FILES} files per request",
                "too_many_files",
            )
        if not files and not topic_text:
            raise BadRequestError(
                "Provide a curriculum topic or upload at least one document",
                "missing_draft_source",
            )
        if topic_text:
            if len(topic_text) < _MIN_TOPIC_CHARS:
                raise BadRequestError(
                    f"Curriculum topic must contain at least {_MIN_TOPIC_CHARS} characters",
                    "invalid_topic",
                )
            if len(topic_text) > _MAX_TOPIC_CHARS:
                raise BadRequestError(
                    f"Curriculum topic must be at most {_MAX_TOPIC_CHARS} characters",
                    "invalid_topic",
                )

        sources = [self._read_source(uploaded_file) for uploaded_file in files]
        if sources and not any(text.strip() for _, text in sources):
            raise BadRequestError(
                "No extractable text found in the uploaded files "
                "(scanned documents without OCR are not supported)",
                "no_extractable_text",
            )

        if files:
            sections = []
            if topic_text:
                sections.append(f"= Curriculum brief =\n{topic_text}")
            sections.extend(f"= File: {name} =\n{text}" for name, text in sources)
            document_text: str | None = "\n\n".join(sections)[:DOCUMENT_TEXT_MAX_CHARS]
        else:
            document_text = None

        logger.info(
            "Curriculum draft source prepared",
            extra={
                "actor_id": str(actor.id),
                "file_count": len(sources),
                "source_mode": source_mode,
                "text_chars": len(document_text or topic_text),
            },
        )
        draft = self._generate_validated_draft(
            actor,
            document_text=document_text,
            topic=topic_text or None,
        )
        logger.info(
            "Curriculum draft generation completed",
            extra={
                "actor_id": str(actor.id),
                "operation": "draft",
                "source_mode": source_mode,
                "model": self._llm_client.model,
                "semester_count": len(draft.semesters),
                "course_count": sum(len(semester.courses) for semester in draft.semesters),
                "peo_count": len(draft.peos),
                "po_count": len(draft.pos),
                "mapping_count": len(draft.mappings),
            },
        )
        return draft

    def _generate_validated_draft(
        self,
        actor: User,
        *,
        document_text: str | None,
        topic: str | None,
    ) -> CurriculumDraftResponse:
        try:
            payload = (
                self._llm_client.draft_curriculum(document_text)
                if document_text is not None
                else self._llm_client.draft_curriculum_from_topic(topic or "")
            )
        except LLMNotConfiguredError:
            logger.warning(
                "Curriculum draft generation unavailable: LLM is not configured",
                extra={"actor_id": str(actor.id), "operation": "draft"},
            )
            raise
        except LLMResponseError as exc:
            self._log_provider_failure(actor, exc, attempt=1)
            raise ServiceUnavailableError(
                f"LLM drafting failed: {exc}", "llm_draft_failed"
            ) from exc

        try:
            return CurriculumDraftResponse.from_llm_payload(payload)
        except BadRequestError as exc:
            logger.warning(
                "Curriculum draft response failed validation; requesting repair",
                extra={
                    "actor_id": str(actor.id),
                    "operation": "draft",
                    "model": self._llm_client.model,
                    "exception_type": type(exc).__name__,
                    "validation_error": exc.message,
                    "attempt": 1,
                    "max_attempts": _MAX_DRAFT_ATTEMPTS,
                },
            )
            first_error = exc

        try:
            repaired_payload = (
                self._llm_client.repair_curriculum_draft(
                    document_text, payload, first_error.message
                )
                if document_text is not None
                else self._llm_client.repair_curriculum_draft_from_topic(
                    topic or "", payload, first_error.message
                )
            )
        except LLMNotConfiguredError:
            logger.warning(
                "Curriculum draft repair unavailable: LLM is not configured",
                extra={"actor_id": str(actor.id), "operation": "draft"},
            )
            raise
        except LLMResponseError as exc:
            self._log_provider_failure(actor, exc, attempt=2)
            raise ServiceUnavailableError(
                "LLM returned an incomplete or invalid curriculum draft and the repair "
                f"attempt failed: {exc}",
                "llm_draft_failed",
            ) from exc

        try:
            draft = CurriculumDraftResponse.from_llm_payload(repaired_payload)
        except BadRequestError as exc:
            logger.error(
                "Curriculum draft repair failed validation",
                extra={
                    "actor_id": str(actor.id),
                    "operation": "draft",
                    "model": self._llm_client.model,
                    "exception_type": type(exc).__name__,
                    "validation_error": exc.message,
                    "attempt": _MAX_DRAFT_ATTEMPTS,
                    "max_attempts": _MAX_DRAFT_ATTEMPTS,
                },
            )
            raise ServiceUnavailableError(
                "LLM returned an incomplete or invalid curriculum draft after one repair "
                f"attempt: {exc.message}",
                "llm_draft_failed",
            ) from exc

        logger.info(
            "Curriculum draft repaired after validation feedback",
            extra={
                "actor_id": str(actor.id),
                "operation": "draft",
                "model": self._llm_client.model,
                "attempt": _MAX_DRAFT_ATTEMPTS,
            },
        )
        return draft

    def _log_provider_failure(
        self, actor: User, exc: LLMResponseError, attempt: int
    ) -> None:
        logger.error(
            "Curriculum draft provider request failed",
            extra={
                "actor_id": str(actor.id),
                "operation": "draft",
                "model": self._llm_client.model,
                "exception_type": type(exc).__name__,
                "attempt": attempt,
                "max_attempts": _MAX_DRAFT_ATTEMPTS,
            },
        )

    def _read_source(self, uploaded_file: UploadFile) -> tuple[str, str]:
        extension = normalize_extension(uploaded_file.filename)
        allowed = tuple(
            ext.lower() if ext.startswith(".") else f".{ext.lower()}"
            for ext in self._settings.allowed_upload_extensions
        )
        if extension not in allowed:
            raise BadRequestError(
                f"File type '{extension or 'unknown'}' is not allowed",
                "unsupported_file_type",
            )
        data, first_bytes = self._read_bytes(uploaded_file)
        try:
            verify_signature(extension, first_bytes)
        except DocumentIngestFailure as exc:
            raise BadRequestError(str(exc), "invalid_file_content") from exc
        text = extract_text(extension, data)
        return self._safe_basename(uploaded_file.filename), text

    def _read_bytes(self, uploaded_file: UploadFile) -> tuple[bytes, bytes]:
        max_bytes = self._settings.max_upload_size_mb * 1024 * 1024
        total = 0
        first_bytes = b""
        buffer = io.BytesIO()
        while True:
            chunk = uploaded_file.file.read(_CHUNK_SIZE)
            if not chunk:
                break
            if total == 0:
                first_bytes = chunk[:8]
            total += len(chunk)
            if total > max_bytes:
                raise PayloadTooLargeError(
                    "File exceeds the configured maximum upload size of "
                    f"{self._settings.max_upload_size_mb} MB"
                )
            buffer.write(chunk)
        if total == 0:
            raise BadRequestError("Uploaded file is empty", "empty_file")
        return buffer.getvalue(), first_bytes

    def _safe_basename(self, filename: str | None) -> str:
        name = Path(filename or "").name
        if not name or name in {".", ".."}:
            raise BadRequestError("Upload file name is not usable", "invalid_file_content")
        return name
