import io
from collections.abc import Callable
from pathlib import Path

_PDF_MAGIC = b"%PDF-"
_DOCX_MAGIC = b"PK\x03\x04"


class DocumentIngestFailure(Exception):
    """Document-specific, user-recoverable ingestion failure."""


def normalize_extension(raw: str | None) -> str:
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


def extract_text(extension: str, data: bytes) -> str:
    reader = _READERS.get(extension)
    if reader is None:
        raise DocumentIngestFailure(
            f"No text extraction available for '{extension}' files"
        )
    return reader(data)


def verify_signature(extension: str, first_bytes: bytes) -> None:
    expected = {".pdf": _PDF_MAGIC, ".docx": _DOCX_MAGIC}.get(extension)
    if expected is not None and not first_bytes.startswith(expected):
        raise DocumentIngestFailure("File content does not match the declared format")
