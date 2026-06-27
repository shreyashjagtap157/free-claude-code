"""Google AI Studio (Gemini) provider implementation."""

from __future__ import annotations

from typing import Any

from providers.base import ProviderConfig
from providers.defaults import GOOGLE_DEFAULT_BASE
from providers.openai_compat import OpenAIChatTransport

from .request import build_request_body


class GoogleProvider(OpenAIChatTransport):
    """Google Gemini provider using the OpenAI-compatible chat completions API.

    Google's Gemini API uses ``x-goog-api-key`` header authentication, not the
    standard ``Authorization: Bearer`` token. This subclass overrides the client
    kwargs to send the API key via the correct header"""

    def __init__(self, config: ProviderConfig):
        super().__init__(
            config,
            provider_name="GOOGLE",
            base_url=config.base_url or GOOGLE_DEFAULT_BASE,
            api_key=config.api_key,
        )

    def _build_client_kwargs(self) -> dict[str, Any]:
        kwargs = super()._build_client_kwargs()
        # Google Gemini API uses x-goog-api-key header, not Bearer token.
        kwargs["default_headers"] = {"x-goog-api-key": self._api_key}
        kwargs["api_key"] = ""  # Prevent sending Authorization: Bearer
        return kwargs

    def _build_request_body(
        self, request: Any, thinking_enabled: bool | None = None
    ) -> dict:
        return build_request_body(
            request,
            thinking_enabled=self._is_thinking_enabled(request, thinking_enabled),
        )
