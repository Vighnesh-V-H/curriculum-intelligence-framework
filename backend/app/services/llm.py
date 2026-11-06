import json
from typing import Any, Protocol

import httpx
from pydantic import SecretStr

from app.core.errors import ServiceUnavailableError

DOCUMENT_TEXT_MAX_CHARS = 120_000

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

_DRAFT_SYSTEM_PROMPT = (
    "You are a curriculum drafting assistant for an academic institution. "
    "You receive the combined text of one or more uploaded curriculum documents "
    "(syllabi, curriculum outlines, regulations). "
    "Produce a roadmap-style curriculum draft based on them. "
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
    "Rules:\n"
    "- Derive the draft from the provided document text when it is present.\n"
    "- When the documents are sparse, produce a sensible baseline draft for a "
    "typical undergraduate program instead of an empty answer.\n"
    "- Use sequential semester numbers starting at 1 with no gaps.\n"
    "- Course codes are uppercase alphanumeric identifiers, unique across all "
    "semesters.\n"
    "- PEO codes follow the PEO1..PEOn style (2-4 entries); PO codes follow the "
    "PO1..POn style (4-8 entries).\n"
    "- Course outcome codes follow the CO1..COn style; every course has 2-3 "
    "course outcomes.\n"
    "- Every mapping references codes defined above: course_code and "
    "course_outcome_code belong to the same course, program_outcome_code comes "
    "from the pos list, and level is 1, 2 or 3. Provide basic coverage across "
    "the program.\n"
    "- Keep summaries short (at most 2 sentences).\n"
    "- PEOs must never be empty; when the documents define no program outcomes, "
    "leave pos empty.\n"
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
            content = self._request(payload)
        except LLMResponseError:
            raise
        except Exception as exc:
            raise LLMResponseError(f"LLM request failed: {exc}") from exc
        return _parse_json_object(content)

    def draft_curriculum(self, document_text: str) -> dict[str, Any]:
        if self._api_key is None or self._api_key.get_secret_value() == "":
            raise LLMNotConfiguredError()

        truncated = document_text[:DOCUMENT_TEXT_MAX_CHARS]
        payload = {
            "model": self._model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": _DRAFT_SYSTEM_PROMPT},
                {"role": "user", "content": f"Document content:\n{truncated}"},
            ],
        }
        try:
            content = self._request(payload)
        except LLMResponseError:
            raise
        except Exception as exc:
            raise LLMResponseError(f"LLM request failed: {exc}") from exc
        return _parse_json_object(content)

    def _request(self, payload: dict[str, Any]) -> str:
        headers = {"Authorization": f"Bearer {self._api_key.get_secret_value()}"}
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
        if response.status_code >= 400:
            raise LLMResponseError(
                f"LLM provider returned status {response.status_code}"
            )
        body = response.json()
        try:
            return body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMResponseError("LLM response has no message content") from exc


def _parse_json_object(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
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
