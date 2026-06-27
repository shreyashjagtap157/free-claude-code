"""Tests for Google AI Studio (Gemini) OpenAI-compatible provider."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from providers.base import ProviderConfig
from providers.google import GoogleProvider


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
        self.thinking = MagicMock()
        self.thinking.enabled = True
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
            "thinking": {"enabled": self.thinking.enabled} if self.thinking else None,
        }


@pytest.fixture
def google_config():
    return ProviderConfig(
        api_key="test-google-key",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        rate_limit=10,
        rate_window=60,
    )


def test_init(google_config):
    """Test provider initialization with default config."""
    with patch("providers.openai_compat.AsyncOpenAI") as mock_openai:
        mock_openai.return_value = MagicMock()
        provider = GoogleProvider(google_config)
        assert provider._provider_name == "GOOGLE"
        assert provider._api_key == "test-google-key"
        assert (
            provider._base_url
            == "https://generativelanguage.googleapis.com/v1beta/openai"
        )


def test_init_default_base_url():
    """Provider uses GOOGLE_DEFAULT_BASE when no base_url is given."""
    config = ProviderConfig(api_key="test-google-key")
    with patch("providers.openai_compat.AsyncOpenAI") as mock_openai:
        mock_openai.return_value = MagicMock()
        provider = GoogleProvider(config)
        assert (
            provider._base_url
            == "https://generativelanguage.googleapis.com/v1beta/openai"
        )


def test_init_base_url_strips_trailing_slash():
    """Config with base_url trailing slash is stored without it."""
    config = ProviderConfig(
        api_key="test-google-key",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        rate_limit=10,
        rate_window=60,
    )
    with patch("providers.openai_compat.AsyncOpenAI") as mock_openai:
        mock_openai.return_value = MagicMock()
        provider = GoogleProvider(config)
        assert (
            provider._base_url
            == "https://generativelanguage.googleapis.com/v1beta/openai"
        )


def test_init_uses_configurable_timeouts():
    """Provider passes configurable read/write/connect timeouts to client."""
    config = ProviderConfig(
        api_key="test-google-key",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        http_read_timeout=600.0,
        http_write_timeout=15.0,
        http_connect_timeout=5.0,
    )
    with patch("providers.openai_compat.AsyncOpenAI") as mock_openai:
        mock_openai.return_value = MagicMock()
        GoogleProvider(config)
        mock_openai.assert_called_once()
        timeout = mock_openai.call_args.kwargs["timeout"]
        assert timeout.read == 600.0
        assert timeout.write == 15.0
        assert timeout.connect == 5.0


def test_init_forwards_proxy_to_http_client():
    """Proxy config is passed through to the underlying httpx client."""
    config = ProviderConfig(
        api_key="test-google-key",
        proxy="socks5://127.0.0.1:9999",
    )
    with (
        patch("providers.openai_compat.AsyncOpenAI") as mock_openai,
        patch("httpx.AsyncClient") as mock_http,
    ):
        mock_openai.return_value = MagicMock()
        GoogleProvider(config)
        assert mock_http.called
        assert mock_http.call_args.kwargs["proxy"] == "socks5://127.0.0.1:9999"


@patch("providers.google.client.build_request_body")
def test_build_request_body_delegates(mock_build, google_config):
    """_build_request_body delegates to the module-level build_request_body."""
    with patch("providers.openai_compat.AsyncOpenAI") as mock_openai:
        mock_openai.return_value = MagicMock()
        provider = GoogleProvider(google_config)
        request = MockRequest()
        provider._build_request_body(request, thinking_enabled=True)
        mock_build.assert_called_once_with(request, thinking_enabled=True)


@patch("providers.google.client.build_request_body")
def test_build_request_body_passes_thinking_disabled(mock_build, google_config):
    """build_request_body receives thinking_enabled=False when globally disabled."""
    config = ProviderConfig(
        api_key="test-google-key",
        enable_thinking=False,
    )
    with patch("providers.openai_compat.AsyncOpenAI") as mock_openai:
        mock_openai.return_value = MagicMock()
        provider = GoogleProvider(config)
        request = MockRequest()
        provider._build_request_body(request, thinking_enabled=None)
        mock_build.assert_called_once_with(request, thinking_enabled=False)


@pytest.mark.asyncio
async def test_cleanup(google_config):
    """cleanup releases the client."""
    with patch("providers.openai_compat.AsyncOpenAI") as mock_openai:
        mock_client = AsyncMock()
        mock_openai.return_value = mock_client
        provider = GoogleProvider(google_config)
        await provider.cleanup()
        mock_client.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_model_ids(google_config):
    """list_model_ids calls the models endpoint."""
    with patch("providers.openai_compat.AsyncOpenAI") as mock_openai:
        mock_client = AsyncMock()
        mock_models_page = MagicMock()
        mock_models_page.data = [
            MagicMock(id="gemini-2.0-flash"),
            MagicMock(id="gemini-2.0-pro"),
        ]
        mock_client.models.list.return_value = mock_models_page
        mock_openai.return_value = mock_client
        provider = GoogleProvider(google_config)
        model_ids = await provider.list_model_ids()

    assert "gemini-2.0-flash" in model_ids
    assert "gemini-2.0-pro" in model_ids
