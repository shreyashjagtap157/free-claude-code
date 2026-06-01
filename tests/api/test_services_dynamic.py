"""Unit tests for dynamic provider resolution and corrected tool validation messages."""

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
