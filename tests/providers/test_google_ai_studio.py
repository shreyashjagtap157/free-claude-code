from unittest.mock import MagicMock

import openai
import pytest

from providers.google_ai_studio.request import (
    _is_gemma_model,
    build_request_body,
)

# ---------------------------------------------------------------------------
# Gemma detection
# ---------------------------------------------------------------------------


class TestIsGemmaModel:
    @pytest.mark.parametrize(
        "model_id",
        [
            "models/gemma-4-31b-it",
            "models/gemma-4-26b-a4b-it",
            "gemma-3-9b-it",
            "models/GEMMA-4-12B",
        ],
    )
    def test_gemma_detected(self, model_id: str):
        assert _is_gemma_model(model_id) is True

    @pytest.mark.parametrize(
        "model_id",
        [
            "models/gemini-2.5-flash",
            "models/gemini-2.0-pro",
            "gemini-1.5-pro",
        ],
    )
    def test_gemini_not_detected_as_gemma(self, model_id: str):
        assert _is_gemma_model(model_id) is False


# ---------------------------------------------------------------------------
# Request body building
# ---------------------------------------------------------------------------


def _make_request(*, model: str = "models/gemma-4-31b-it"):
    req = MagicMock()
    req.model = model
    req.messages = [MagicMock(role="user", content="hi")]
    req.system = None
    req.tools = None
    req.tool_choice = None
    req.max_tokens = 4096
    req.temperature = None
    req.top_p = None
    req.stop_sequences = None
    req.thinking = None
    req.effort = None
    return req


class TestBuildRequestBody:
    def test_gemma_uses_think_tags_no_reasoning_content(self):
        """Gemma request must NOT have reasoning_content on assistant messages."""
        req = _make_request(model="models/gemma-4-31b-it")
        req.messages = [
            MagicMock(
                role="assistant",
                content=[
                    MagicMock(type="thinking", thinking="inner thought"),
                    MagicMock(type="text", text="visible answer"),
                ],
                reasoning_content=None,
            )
        ]
        body = build_request_body(req, thinking_enabled=True)
        assistant_msg = body["messages"][0]
        assert "reasoning_content" not in assistant_msg
        # Think tags should be used instead.
        assert "<think>" in assistant_msg["content"]
        assert "inner thought" in assistant_msg["content"]

    def test_gemini_uses_reasoning_content(self):
        """Gemini models should use reasoning_content replay."""
        req = _make_request(model="models/gemini-2.5-flash")
        req.messages = [
            MagicMock(
                role="assistant",
                content=[
                    MagicMock(type="thinking", thinking="inner thought"),
                    MagicMock(type="text", text="visible answer"),
                ],
                reasoning_content=None,
            )
        ]
        body = build_request_body(req, thinking_enabled=True)
        assistant_msg = body["messages"][0]
        assert assistant_msg.get("reasoning_content") == "inner thought"
        assert "<think>" not in assistant_msg["content"]

    def test_gemma_strips_reasoning_effort(self):
        """Gemma request should not have reasoning_effort."""
        req = _make_request(model="models/gemma-4-31b-it")
        req.effort = "high"
        body = build_request_body(req, thinking_enabled=True)
        assert "reasoning_effort" not in body

    def test_gemini_keeps_reasoning_effort(self):
        """Gemini models should keep reasoning_effort."""
        req = _make_request(model="models/gemini-2.5-flash")
        req.effort = "high"
        body = build_request_body(req, thinking_enabled=True)
        assert body.get("reasoning_effort") == "high"


# ---------------------------------------------------------------------------
# Retry logic
# ---------------------------------------------------------------------------


class TestGetRetryRequestBody:
    def _make_provider(self):
        from providers.base import ProviderConfig
        from providers.google_ai_studio.client import GoogleAIStudioProvider

        config = ProviderConfig(api_key="test-key")
        return GoogleAIStudioProvider(config)

    def test_retries_on_reasoning_content_in_error(self):
        provider = self._make_provider()
        body = {
            "model": "models/gemma-4-31b-it",
            "messages": [
                {"role": "user", "content": "hi"},
                {
                    "role": "assistant",
                    "content": "answer",
                    "reasoning_content": "thought",
                },
            ],
        }
        error = openai.BadRequestError(
            message="reasoning_content is not supported",
            response=MagicMock(status_code=400, headers={}),
            body={"error": {"message": "reasoning_content not supported"}},
        )
        retry = provider._get_retry_request_body(error, body)
        assert retry is not None
        assert "reasoning_content" not in retry["messages"][1]

    def test_retries_on_reasoning_effort_in_error(self):
        provider = self._make_provider()
        body = {
            "model": "models/gemma-4-31b-it",
            "messages": [{"role": "user", "content": "hi"}],
            "reasoning_effort": "high",
        }
        error = openai.BadRequestError(
            message="reasoning_effort is not supported",
            response=MagicMock(status_code=400, headers={}),
            body={"error": {"message": "reasoning_effort not supported"}},
        )
        retry = provider._get_retry_request_body(error, body)
        assert retry is not None
        assert "reasoning_effort" not in retry

    def test_opaque_400_strips_reasoning_content_as_fallback(self):
        """When the 400 error body doesn't mention the specific field, still try stripping."""
        provider = self._make_provider()
        body = {
            "model": "models/gemma-4-31b-it",
            "messages": [
                {"role": "user", "content": "hi"},
                {
                    "role": "assistant",
                    "content": "answer",
                    "reasoning_content": "thought",
                },
            ],
        }
        error = openai.BadRequestError(
            message="Bad request",
            response=MagicMock(status_code=400, headers={}),
            body={"error": {"message": "Request is invalid"}},
        )
        retry = provider._get_retry_request_body(error, body)
        assert retry is not None
        assert "reasoning_content" not in retry["messages"][1]

    def test_returns_none_for_non_400(self):
        class _StatusException(Exception):
            status_code: int

        provider = self._make_provider()
        body = {"model": "test", "messages": []}
        error = _StatusException("server error")
        error.status_code = 500
        assert provider._get_retry_request_body(error, body) is None

    def test_returns_none_when_nothing_to_strip(self):
        provider = self._make_provider()
        body = {
            "model": "test",
            "messages": [{"role": "user", "content": "hi"}],
        }
        error = openai.BadRequestError(
            message="Bad request",
            response=MagicMock(status_code=400, headers={}),
            body={"error": {"message": "something else"}},
        )
        assert provider._get_retry_request_body(error, body) is None
