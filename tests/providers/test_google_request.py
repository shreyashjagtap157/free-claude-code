"""Tests for Google AI Studio request builder."""

from unittest.mock import patch

import pytest

from providers.exceptions import InvalidRequestError
from providers.google.request import build_request_body


class MockMessage:
    def __init__(self, role, content):
        self.role = role
        self.content = content


class MockRequest:
    def __init__(self, **kwargs):
        self.model = "google/gemini-2.0-flash"
        self.messages = [MockMessage("user", "Hello")]
        self.max_tokens = 100
        self.temperature = 0.5
        self.top_p = 0.9
        self.system = "System prompt"
        self.stop_sequences = None
        self.stream = True
        self.tools = []
        self.tool_choice = None
        self.extra_body = {}
        self.thinking = None
        for key, value in kwargs.items():
            setattr(self, key, value)

    def model_dump(self, exclude_none=True):
        return {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in self.messages],
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "system": self.system,
            "stream": self.stream,
            "tools": self.tools,
            "tool_choice": self.tool_choice,
            "extra_body": self.extra_body,
        }


@patch("providers.google.request.build_base_request_body")
def test_build_request_body_basic(mock_build):
    """build_request_body calls build_base_request_body with REASONING_CONTENT mode."""
    mock_build.return_value = {
        "model": "gemini-2.0-flash",
        "messages": [{"role": "user", "content": "Hello"}],
    }
    request = MockRequest()
    result = build_request_body(request, thinking_enabled=True)

    mock_build.assert_called_once()
    assert result["model"] == "gemini-2.0-flash"


@patch("providers.google.request.build_base_request_body")
def test_build_request_body_with_thinking_disabled(mock_build):
    """build_request_body works with thinking disabled."""
    mock_build.return_value = {
        "model": "gemini-2.0-flash",
        "messages": [{"role": "user", "content": "Hello"}],
    }
    request = MockRequest()
    result = build_request_body(request, thinking_enabled=False)

    mock_build.assert_called_once()
    assert result["model"] == "gemini-2.0-flash"


@patch("providers.google.request.build_base_request_body")
def test_build_request_body_with_tools(mock_build):
    """build_request_body works with tools."""
    mock_build.return_value = {
        "model": "gemini-2.0-flash",
        "messages": [{"role": "user", "content": "Hello"}],
        "tools": [{"type": "function", "function": {"name": "test_tool"}}],
    }
    request = MockRequest(
        tools=[{"type": "function", "function": {"name": "test_tool"}}]
    )
    result = build_request_body(request, thinking_enabled=True)

    mock_build.assert_called_once()
    assert "tools" in result


@patch("providers.google.request.build_base_request_body")
def test_build_request_body_conversion_error(mock_build):
    """build_request_body wraps OpenAIConversionError in InvalidRequestError."""
    from core.anthropic.conversion import OpenAIConversionError

    mock_build.side_effect = OpenAIConversionError("Conversion failed")

    request = MockRequest()
    with pytest.raises(InvalidRequestError, match="Conversion failed"):
        build_request_body(request, thinking_enabled=True)
