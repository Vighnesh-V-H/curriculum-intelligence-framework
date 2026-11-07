import json

import httpx
import pytest
from pydantic import SecretStr

from app.services.llm import (
    LLMResponseError,
    OpenAICompatibleLLMClient,
    _parse_json_object,
)


def _client(
    response_body: dict,
    finish_reason: str = "stop",
    model: str = "test-model",
):
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": finish_reason,
                        "message": {
                            "role": "assistant",
                            "content": json.dumps(response_body),
                        },
                    }
                ]
            },
        )

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    llm = OpenAICompatibleLLMClient(
        base_url="https://llm.example/v1",
        api_key=SecretStr("test-key"),
        model=model,
        timeout_seconds=5,
        http_client=http_client,
    )
    return llm, http_client, requests


def test_draft_request_sets_a_large_output_budget_and_returns_json():
    expected = {"program": {"name": "Example"}}
    llm, http_client, requests = _client(expected)
    try:
        result = llm.draft_curriculum("course outline")
    finally:
        http_client.close()

    assert result == expected
    assert len(requests) == 1
    request_body = json.loads(requests[0].content)
    assert request_body["max_tokens"] == 16_384
    assert request_body["messages"][0]["role"] == "system"
    assert "do not leave either list empty" in request_body["messages"][0]["content"]
    assert "Map every course outcome" in request_body["messages"][0]["content"]


def test_gemini_25_uses_its_larger_output_budget():
    llm, http_client, requests = _client({}, model="gemini-2.5-flash")
    try:
        llm.draft_curriculum("course outline")
    finally:
        http_client.close()

    request_body = json.loads(requests[0].content)
    assert request_body["max_tokens"] == 32_768


def test_transient_provider_error_is_retried():
    requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        if requests == 1:
            return httpx.Response(
                503,
                headers={"Retry-After": "0"},
                json={"error": {"message": "temporarily overloaded"}},
            )
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": '{"ok":true}'},
                    }
                ]
            },
        )

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    llm = OpenAICompatibleLLMClient(
        base_url="https://llm.example/v1",
        api_key=SecretStr("test-key"),
        model="test-model",
        timeout_seconds=5,
        http_client=http_client,
    )
    try:
        assert llm.draft_curriculum("course outline") == {"ok": True}
    finally:
        http_client.close()
    assert requests == 2


def test_truncated_llm_response_is_reported_clearly():
    llm, http_client, _ = _client({"partial": True}, finish_reason="length")
    try:
        with pytest.raises(LLMResponseError, match="truncated"):
            llm.draft_curriculum("course outline")
    finally:
        http_client.close()


def test_json_parser_accepts_uppercase_markdown_fences():
    assert _parse_json_object("```JSON\n{\"ok\": true}\n```") == {"ok": True}
