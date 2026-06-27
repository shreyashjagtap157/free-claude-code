from typing import Any

import httpx

from core.anthropic import build_base_request_body
from providers.base import ProviderConfig
from providers.defaults import OLLAMA_DEFAULT_BASE
from providers.model_listing import extract_ollama_model_ids
from providers.openai_compat import OpenAIChatTransport


class OllamaProvider(OpenAIChatTransport):
    """Ollama provider using OpenAI-compatible chat completions API."""

    def __init__(self, config: ProviderConfig):
        super().__init__(
            config,
            provider_name="OLLAMA",
            base_url=config.base_url or OLLAMA_DEFAULT_BASE,
            api_key=config.api_key or "ollama",
        )
        self._model_list_client: httpx.AsyncClient | None = None

    def _prepare_create_body(self, body: dict[str, Any]) -> dict[str, Any]:
        """Strip fields that Ollama might reject with 400 Bad Request."""
        clean = dict(body)
        clean.pop("reasoning_effort", None)
        return clean

    def _build_request_body(
        self, request: Any, thinking_enabled: bool | None = None
    ) -> dict:
        return build_base_request_body(request)

    async def list_model_ids(self) -> frozenset[str]:
        """Query Ollama's native local model-list endpoint."""
        resp = await self._send_model_list_request()
        resp.raise_for_status()
        return self._extract_model_ids_from_model_list_payload(resp.json())

    async def _send_model_list_request(self) -> httpx.Response:
        """Query Ollama's native local model-list endpoint using a reusable client."""
        if self._model_list_client is None:
            self._model_list_client = httpx.AsyncClient(
                timeout=10.0,
                limits=httpx.Limits(
                    max_connections=self._config.max_connections,
                    max_keepalive_connections=self._config.max_keepalive_connections,
                ),
            )
        url = f"{self._base_url}/api/tags"
        return await self._model_list_client.get(url)

    def _extract_model_ids_from_model_list_payload(
        self, payload: object
    ) -> frozenset[str]:
        return extract_ollama_model_ids(payload, provider_name=self._provider_name)
