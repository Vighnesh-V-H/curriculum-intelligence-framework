import json
import logging
import random
import time
from typing import Any, Protocol

import httpx
from pydantic import SecretStr

from app.core.errors import ServiceUnavailableError
from app.core.logging_config import safe_exception_details

DOCUMENT_TEXT_MAX_CHARS = 120_000
_DEFAULT_DRAFT_MAX_OUTPUT_TOKENS = 16_384
_GEMINI_MAX_OUTPUT_TOKENS = 32_768
_RETRYABLE_PROVIDER_STATUSES = {408, 429, 500, 502, 503, 504, 529}
_MAX_PROVIDER_ATTEMPTS = 5
_MAX_RETRY_DELAY_SECONDS = 10.0
logger = logging.getLogger(__name__)


def _draft_max_output_tokens(model: str) -> int:
    if model.lower().startswith("gemini-"):
        return _GEMINI_MAX_OUTPUT_TOKENS
    return _DEFAULT_DRAFT_MAX_OUTPUT_TOKENS


def _retry_delay_seconds(response: httpx.Response, attempt: int) -> float:
    retry_after = response.headers.get("retry-after")
    if retry_after is not None:
        try:
            return max(0.0, min(float(retry_after), _MAX_RETRY_DELAY_SECONDS))
        except ValueError:
            pass
    base_delay = min(float(2**attempt), _MAX_RETRY_DELAY_SECONDS)
    return base_delay + random.uniform(0.0, 0.5)


_SYSTEM_PROMPT = (
    "You are a curriculum analysis assistant for an academic institution. "
    "You receive the text content of an uploaded curriculum document. "
    "Extract a structured summary of the curriculum described in it. "
    "Respond with a single JSON object and nothing else. Use these keys:\n"
    "{\n"
    '  "program": {"name": string|null, "degree": string|null, '
    '"regulation": string|null, "duration_years": int|null},\n'
    '  "semesters": [{"semester_number": int, "name": string|null}],\n'
    '  "courses": [{"course_code": string, "course_name": string|null, '
    '"course_type": string|null, "credits": int|null, "semester_number": int|null, '
    '"contact_hours": int|null}],\n'
    '  "course_outcomes": [{"course_code": string, "outcome_code": string, '
    '"description": string|null}],\n'
    '  "prerequisites": [{"course_code": string, "prerequisite_course_code": string}],\n'
    '  "summary": string\n'
    "}\n"
    "Rules: use null for values the document does not state; omit nothing, "
    "produce empty lists where the category is absent; do not invent data."
)

_DRAFT_OUTPUT_SCHEMA = (
    "Respond with a single JSON object and nothing else. Use EXACTLY these keys:\n"
    "{\n"
    '  "program": {"name": string|null, "degree": string|null, '
    '"duration_years": int|null, "summary": string},\n'
    '  "semesters": [{"semester_number": int, "semester_name": string, '
    '"focus": string, "courses": [{"code": string, "title": string, '
    '"credits": int|null, "category": string, "summary": string, '
    '"outcomes": [{"code": string, "statement": string}]}]}],\n'
    '  "peos": [{"code": string, "statement": string}],\n'
    '  "pos": [{"code": string, "statement": string}],\n'
    '  "mappings": [{"course_code": string, "course_outcome_code": string, '
    '"program_outcome_code": string, "level": int}]\n'
    "}\n"
)

_DRAFT_RULES = (
    "Rules:\n"
    "- Use sequential semester numbers starting at 1 with no gaps.\n"
    "- Course codes are uppercase alphanumeric identifiers, unique across all "
    "semesters.\n"
    "- PEO codes follow the PEO1..PEOn style (2-4 entries); PO codes follow the "
    "PO1..POn style (4-8 entries).\n"
    "- Course outcome codes follow the CO1..COn style; every course has 2-3 "
    "course outcomes.\n"
    "- Every mapping references codes defined above: course_code and "
    "course_outcome_code belong to the same course, program_outcome_code comes "
    "from the pos list, and level is 1, 2 or 3. Map every course outcome to "
    "at least one relevant PO, with 1-2 mappings per course outcome.\n"
    "- Propose suitable draft POs and PEOs when they are not defined; do not "
    "leave either list empty. These are AI suggestions, not claims that a "
    "source document stated them.\n"
    "- Keep summaries short (at most 2 sentences).\n"
    "- Before responding, verify that every course outcome for every course "
    "appears in at least one mapping entry.\n"
)

_DRAFT_SYSTEM_PROMPT = (
    "You are a curriculum drafting assistant for an academic institution. "
    "You receive the combined text of one or more uploaded curriculum documents "
    "(syllabi, curriculum outlines, regulations). "
    "Produce a roadmap-style curriculum draft based on them. "
    + _DRAFT_OUTPUT_SCHEMA
    + "Rules:\n"
    "- Derive the draft from the provided document text when it is present.\n"
    "- A section named '= Curriculum brief =' is the user's requested topic and "
    "focus; it takes priority over document details when they conflict.\n"
    "- When the documents are sparse, produce a sensible baseline draft for a "
    "typical undergraduate program instead of an empty answer.\n"
    + _DRAFT_RULES.removeprefix("Rules:\n")
)

_TOPIC_DRAFT_SYSTEM_PROMPT = (
    "You are a curriculum design assistant for an academic institution. "
    "You receive a short topic or program brief from an academic user instead "
    "of source documents. Design a complete, realistic roadmap-style curriculum "
    "draft for that brief. "
    + _DRAFT_OUTPUT_SCHEMA
    + "Rules:\n"
    "- Treat the brief as the authority for the program focus, degree level, "
    "duration, and any stated constraints. Infer missing details sensibly.\n"
    "- Build the number of semesters implied by the duration (two semesters per "
    "academic year) unless the brief states otherwise, with 2-12 semesters.\n"
    "- Sequence courses from foundations to advanced material. Include core "
    "courses, labs or applied projects, and relevant electives or capstone work "
    "where they make the program coherent.\n"
    "- Use the topic to choose course titles and content; keep the program "
    "realistic for an accredited higher-education curriculum.\n"
    "- Put every generative design choice into the draft rather than asking the "
    "user follow-up questions.\n"
    + _DRAFT_RULES
)


class LLMNotConfiguredError(ServiceUnavailableError):
    def __init__(self) -> None:
        super().__init__(
            "LLM provider is not configured; set LLM_API_KEY to enable ingestion",
            "llm_not_configured",
        )


class LLMResponseError(Exception):
    """Raised when the LLM transport fails or answers without usable JSON."""


class LLMClient(Protocol):
    @property
    def model(self) -> str: ...

    def analyze_document(
        self, document_text: str, original_filename: str
    ) -> dict[str, Any]: ...

    def draft_curriculum(self, document_text: str) -> dict[str, Any]: ...

    def draft_curriculum_from_topic(self, topic: str) -> dict[str, Any]: ...

    def repair_curriculum_draft(
        self,
        document_text: str,
        previous_payload: dict[str, Any],
        validation_feedback: str,
    ) -> dict[str, Any]: ...

    def repair_curriculum_draft_from_topic(
        self,
        topic: str,
        previous_payload: dict[str, Any],
        validation_feedback: str,
    ) -> dict[str, Any]: ...


class OpenAICompatibleLLMClient:
    def __init__(
        self,
        base_url: str,
        api_key: SecretStr | None,
        model: str,
        timeout_seconds: int,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._http_client = http_client

    @property
    def model(self) -> str:
        return self._model

    def analyze_document(
        self, document_text: str, original_filename: str
    ) -> dict[str, Any]:
        if self._api_key is None or self._api_key.get_secret_value() == "":
            raise LLMNotConfiguredError()

        truncated = document_text[:DOCUMENT_TEXT_MAX_CHARS]
        payload = {
            "model": self._model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Document name: {original_filename}\n\n"
                        f"Document content:\n{truncated}"
                    ),
                },
            ],
        }
        try:
            content = self._request(payload, operation="analysis")
        except LLMResponseError:
            raise
        except Exception as exc:
            raise LLMResponseError(f"LLM request failed: {exc}") from exc
        return _parse_json_object(content)

    def draft_curriculum(self, document_text: str) -> dict[str, Any]:
        return self._request_draft(document_text)

    def draft_curriculum_from_topic(self, topic: str) -> dict[str, Any]:
        return self._request_draft(
            topic,
            system_prompt=_TOPIC_DRAFT_SYSTEM_PROMPT,
            source_label="Curriculum topic and requirements",
        )

    def repair_curriculum_draft(
        self,
        document_text: str,
        previous_payload: dict[str, Any],
        validation_feedback: str,
    ) -> dict[str, Any]:
        return self._request_draft(
            document_text,
            previous_payload=previous_payload,
            validation_feedback=validation_feedback,
        )

    def repair_curriculum_draft_from_topic(
        self,
        topic: str,
        previous_payload: dict[str, Any],
        validation_feedback: str,
    ) -> dict[str, Any]:
        return self._request_draft(
            topic,
            previous_payload=previous_payload,
            validation_feedback=validation_feedback,
            system_prompt=_TOPIC_DRAFT_SYSTEM_PROMPT,
            source_label="Curriculum topic and requirements",
        )

    def _request_draft(
        self,
        source_text: str,
        previous_payload: dict[str, Any] | None = None,
        validation_feedback: str | None = None,
        *,
        system_prompt: str = _DRAFT_SYSTEM_PROMPT,
        source_label: str = "Document content",
    ) -> dict[str, Any]:
        if self._api_key is None or self._api_key.get_secret_value() == "":
            raise LLMNotConfiguredError()

        truncated = source_text[:DOCUMENT_TEXT_MAX_CHARS]
        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"{source_label}:\n{truncated}"},
        ]
        if previous_payload is not None and validation_feedback is not None:
            messages.extend(
                [
                    {
                        "role": "assistant",
                        "content": json.dumps(previous_payload, ensure_ascii=False),
                    },
                    {
                        "role": "user",
                        "content": (
                            "The draft validator rejected that response with this error:\n"
                            f"{validation_feedback}\n\n"
                            "Return the complete corrected JSON object, preserving the valid "
                            "content. Check that every course outcome appears in at least one "
                            "mapping before answering."
                        ),
                    },
                ]
            )
        payload = {
            "model": self._model,
            "temperature": 0,
            "max_tokens": _draft_max_output_tokens(self._model),
            "messages": messages,
        }
        try:
            content = self._request(payload, operation="draft")
        except LLMResponseError:
            raise
        except Exception as exc:
            raise LLMResponseError(f"LLM request failed: {exc}") from exc
        return _parse_json_object(content)

    def _request(self, payload: dict[str, Any], operation: str) -> str:
        headers = {"Authorization": f"Bearer {self._api_key.get_secret_value()}"}
        started_at = time.perf_counter()
        logger.info(
            "LLM provider request started",
            extra={"operation": operation, "model": self._model},
        )
        for attempt in range(_MAX_PROVIDER_ATTEMPTS):
            try:
                if self._http_client is not None:
                    response = self._http_client.post(
                        f"{self._base_url}/chat/completions",
                        json=payload,
                        headers=headers,
                    )
                else:
                    with httpx.Client(timeout=self._timeout_seconds) as client:
                        response = client.post(
                            f"{self._base_url}/chat/completions",
                            json=payload,
                            headers=headers,
                        )
            except httpx.HTTPError as exc:
                logger.error(
                    "LLM provider transport failed",
                    extra={
                        "operation": operation,
                        "model": self._model,
                        "attempt": attempt + 1,
                        "max_attempts": _MAX_PROVIDER_ATTEMPTS,
                        **safe_exception_details(exc),
                    },
                )
                raise
            if (
                response.status_code in _RETRYABLE_PROVIDER_STATUSES
                and attempt < _MAX_PROVIDER_ATTEMPTS - 1
            ):
                delay = _retry_delay_seconds(response, attempt)
                logger.warning(
                    "Retrying transient LLM provider response",
                    extra={
                        "operation": operation,
                        "model": self._model,
                        "provider_status": response.status_code,
                        "attempt": attempt + 1,
                        "max_attempts": _MAX_PROVIDER_ATTEMPTS,
                        "retry_delay_seconds": round(delay, 2),
                    },
                )
                time.sleep(delay)
                continue
            if response.status_code >= 400:
                logger.error(
                    "LLM provider returned an error response",
                    extra={
                        "operation": operation,
                        "model": self._model,
                        "provider_status": response.status_code,
                        "attempt": attempt + 1,
                    },
                )
                detail = _provider_error_detail(response) or _provider_status_fallback(
                    response.status_code
                )
                suffix = f": {detail}" if detail else ""
                raise LLMResponseError(
                    f"LLM provider returned status {response.status_code}{suffix}"
                )
            break
        try:
            body = response.json()
            choice = body["choices"][0]
            content = choice["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            logger.error(
                "LLM provider response could not be parsed",
                extra={"operation": operation, "model": self._model},
            )
            raise LLMResponseError("LLM response has no usable message content") from exc
        if choice.get("finish_reason") == "length":
            logger.error(
                "LLM provider response was truncated",
                extra={"operation": operation, "model": self._model},
            )
            raise LLMResponseError(
                "LLM response was truncated at the output token limit; "
                "increase the model output-token limit"
            )
        if not isinstance(content, str) or not content.strip():
            logger.error(
                "LLM provider response contained no usable content",
                extra={"operation": operation, "model": self._model},
            )
            raise LLMResponseError("LLM response has no usable message content")
        logger.info(
            "LLM provider request completed",
            extra={
                "operation": operation,
                "model": self._model,
                "duration_ms": round((time.perf_counter() - started_at) * 1000, 2),
            },
        )
        return content


def _provider_error_detail(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return ""
    if not isinstance(body, dict):
        return ""
    error = body.get("error")
    if isinstance(error, str):
        return error.strip()[:300]
    message = error.get("message") if isinstance(error, dict) else None
    if not isinstance(message, str):
        message = body.get("message")
    return message.strip()[:300] if isinstance(message, str) else ""


def _provider_status_fallback(status_code: int) -> str:
    if status_code == 429:
        return "provider rate limit reached; try again later"
    if status_code == 503:
        return "provider is temporarily unavailable or overloaded; try again in a moment"
    if status_code == 529:
        return "provider is temporarily overloaded; try again in a moment"
    return ""


def _parse_json_object(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        fenced_text = text[3:]
        first_line, separator, body = fenced_text.partition("\n")
        if first_line.strip().lower() in {"", "json"}:
            text = body if separator else first_line
        else:
            text = fenced_text
        text = text.rsplit("```", 1)[0].strip()
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError) as exc:
        raise LLMResponseError("LLM response is not valid JSON") from exc
    if not isinstance(parsed, dict):
        raise LLMResponseError("LLM response is not a JSON object")
    return parsed


def get_llm_client() -> LLMClient:
    from app.core.config import get_settings

    settings = get_settings()
    return OpenAICompatibleLLMClient(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        timeout_seconds=settings.llm_timeout_seconds,
    )
