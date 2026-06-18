"""Unit tests for dynamic provider resolution and corrected tool validation messages."""

import pytest

from api.models.anthropic import Message, MessagesRequest, Tool
from api.services import _OPENAI_CHAT_UPSTREAM_IDS
from api.web_tools.request import openai_chat_upstream_server_tool_error


def test_openai_chat_upstream_ids_resolves_dynamically() -> None:
    """Verify that _OPENAI_CHAT_UPSTREAM_IDS matches exactly the set of openai_chat upstreams."""
    # Should include all OpenAI-compatible transports
    assert "nvidia_nim" in _OPENAI_CHAT_UPSTREAM_IDS
    assert "lmstudio" in _OPENAI_CHAT_UPSTREAM_IDS
    assert "llamacpp" in _OPENAI_CHAT_UPSTREAM_IDS
    assert "ollama" in _OPENAI_CHAT_UPSTREAM_IDS
    assert "kimi" in _OPENAI_CHAT_UPSTREAM_IDS
    assert "opencode" in _OPENAI_CHAT_UPSTREAM_IDS
    assert "opencode_go" in _OPENAI_CHAT_UPSTREAM_IDS
    assert "zai" in _OPENAI_CHAT_UPSTREAM_IDS
    assert "fireworks" in _OPENAI_CHAT_UPSTREAM_IDS
    assert "google_ai_studio" in _OPENAI_CHAT_UPSTREAM_IDS

    # Should NOT include native Anthropic Messages transports
    assert "open_router" not in _OPENAI_CHAT_UPSTREAM_IDS
    assert "deepseek" not in _OPENAI_CHAT_UPSTREAM_IDS
    assert "wafer" not in _OPENAI_CHAT_UPSTREAM_IDS


def test_openai_chat_upstream_server_tool_error_messages() -> None:
    """Verify that tool validation error messages are corrected and generalized."""
    # Case 1: Forced server tool but web tools disabled
    req_forced = MessagesRequest(
        model="claude-3-5-sonnet-20241022",
        max_tokens=100,
        messages=[Message(role="user", content="hello")],
        tools=[Tool(name="web_search", description="search the web", input_schema={})],
        tool_choice={"type": "tool", "name": "web_search"},
    )
    err_forced = openai_chat_upstream_server_tool_error(
        req_forced, web_tools_enabled=False
    )
    assert err_forced is not None
    assert "e.g. open_router, deepseek, wafer" in err_forced
    assert "ollama" not in err_forced
    assert "lmstudio" not in err_forced

    # Case 2: Listed server tool (not forced)
    req_listed = MessagesRequest(
        model="claude-3-5-sonnet-20241022",
        max_tokens=100,
        messages=[Message(role="user", content="hello")],
        tools=[Tool(name="web_search", description="search the web", input_schema={})],
    )
    err_listed = openai_chat_upstream_server_tool_error(
        req_listed, web_tools_enabled=True
    )
    assert err_listed is not None
    assert (
        "OpenAI Chat upstreams cannot use listed Anthropic server tools" in err_listed
    )
    assert "NVIDIA NIM" not in err_listed


def test_prompt_caching_capability_present() -> None:
    """Verify that prompt_caching capability is declared on the expected providers."""
    from config.provider_catalog import PROVIDER_CATALOG

    for provider_id in ("google_ai_studio", "deepseek", "open_router", "wafer"):
        desc = PROVIDER_CATALOG.get(provider_id)
        assert desc is not None
        assert "prompt_caching" in desc.capabilities

    # Other providers should not have it
    for provider_id in ("nvidia_nim", "lmstudio", "llamacpp", "ollama"):
        desc = PROVIDER_CATALOG.get(provider_id)
        assert desc is not None
        assert "prompt_caching" not in desc.capabilities


@pytest.mark.asyncio
async def test_context_trimming_bypass_for_prompt_caching_providers() -> None:
    """Verify that providers with prompt_caching bypass context trimming."""
    from unittest.mock import MagicMock

    from api.services import ClaudeProxyService
    from config.settings import Settings

    settings = Settings()
    # Enable context trimming with a small token limit
    settings.max_context_tokens = 50

    mock_provider = MagicMock()

    # Fake async stream generator for stream_response
    async def fake_stream(*args, **kwargs):
        yield "event: ping\ndata: {}\n\n"

    mock_provider.stream_response = fake_stream

    service = ClaudeProxyService(settings, provider_getter=lambda _: mock_provider)

    # Build a long conversation that will exceed 50 tokens and has enough messages to trim
    long_messages = [
        Message(role="user", content="hello " * 20),
        Message(role="assistant", content="hi " * 20),
        Message(role="user", content="tell me a story about a dragon and a wizard"),
        Message(role="assistant", content="once upon a time there was a great dragon"),
        Message(role="user", content="continue the story"),
    ]

    # Test case 1: google_ai_studio (Gemini) which has prompt_caching capability -> Bypass Trimming
    req_gemini = MessagesRequest(
        model="google_ai_studio/gemini-2.5-pro",
        max_tokens=100,
        messages=long_messages,
    )
    await service.create_message(req_gemini)
    mock_provider.preflight_stream.assert_called_once()
    captured_req = mock_provider.preflight_stream.call_args[0][0]
    # Check that messages list is unchanged (length 5)
    assert len(captured_req.messages) == 5

    # Test case 2: nvidia_nim (no prompt caching capability) -> Trimmed
    mock_provider.reset_mock()
    req_nim = MessagesRequest(
        model="nvidia_nim/minimax-m2.7",
        max_tokens=100,
        messages=long_messages,
    )
    await service.create_message(req_nim)
    mock_provider.preflight_stream.assert_called_once()
    captured_req = mock_provider.preflight_stream.call_args[0][0]
    # Check that messages list is trimmed (length < 5)
    assert len(captured_req.messages) < 5
