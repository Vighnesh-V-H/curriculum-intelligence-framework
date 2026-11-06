import io
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

_CHUNK_SIZE = 1024 * 1024
_MAX_FILES = 5


class CurriculumDraftService:
    def __init__(self, llm_client: LLMClient, settings: Settings) -> None:
        self._llm_client = llm_client
        self._settings = settings

    def generate(self, actor: User, files: list[UploadFile]) -> CurriculumDraftResponse:
        if not 1 <= len(files) <= _MAX_FILES:
            raise BadRequestError(
                f"Upload between 1 and {_MAX_FILES} files per request",
                "too_many_files",
            )

        sources = [self._read_source(uploaded_file) for uploaded_file in files]
        if not any(text.strip() for _, text in sources):
            raise BadRequestError(
                "No extractable text found in the uploaded files "
                "(scanned documents without OCR are not supported)",
                "no_extractable_text",
            )

        combined = "\n\n".join(
            f"= File: {name} =\n{text}" for name, text in sources
        )[:DOCUMENT_TEXT_MAX_CHARS]
        try:
            payload = self._llm_client.draft_curriculum(combined)
        except LLMNotConfiguredError:
            raise
        except LLMResponseError as exc:
            raise ServiceUnavailableError(
                f"LLM drafting failed: {exc}", "llm_draft_failed"
            ) from exc
        return CurriculumDraftResponse.from_llm_payload(payload)

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
