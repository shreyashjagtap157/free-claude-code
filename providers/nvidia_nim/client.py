"""NVIDIA NIM provider implementation."""

import json
from typing import Any

import httpx
import openai
from loguru import logger

from config.nim import NimSettings
from providers.base import ProviderConfig
from providers.defaults import NVIDIA_NIM_DEFAULT_BASE
from providers.openai_compat import OpenAIChatTransport

from .request import (
    body_without_nim_tool_argument_aliases,
    build_request_body,
    clone_body_without_chat_template,
    clone_body_without_reasoning_budget,
    clone_body_without_reasoning_content,
    clone_body_without_reasoning_effort,
    clone_body_without_system_role,
    nim_tool_argument_aliases_from_body,
)


class NvidiaNimProvider(OpenAIChatTransport):
    """NVIDIA NIM provider using official OpenAI client."""

    def __init__(self, config: ProviderConfig, *, nim_settings: NimSettings):
        # Assign _nim_settings before super().__init__() because the parent
        # constructor calls _build_client_kwargs(), which reads _nim_settings.
        self._nim_settings = nim_settings
        super().__init__(
            config,
            provider_name="NIM",
            base_url=config.base_url or NVIDIA_NIM_DEFAULT_BASE,
            api_key=config.api_key,
        )

    def _build_client_kwargs(self) -> dict[str, Any]:
        kwargs = super()._build_client_kwargs()
        kwargs["max_retries"] = 0
        nim = self._nim_settings
        nim_timeout = httpx.Timeout(
            nim.http_read_timeout,
            connect=nim.http_connect_timeout,
            read=nim.http_read_timeout,
            write=nim.http_write_timeout,
        )
        kwargs["timeout"] = nim_timeout
        limits = httpx.Limits(
            max_connections=self._config.max_connections,
            max_keepalive_connections=self._config.max_keepalive_connections,
        )
        if self._config.proxy:
            kwargs["http_client"] = httpx.AsyncClient(
                proxy=self._config.proxy,
                timeout=nim_timeout,
                limits=limits,
            )
        else:
            kwargs["http_client"] = httpx.AsyncClient(
                timeout=nim_timeout,
                limits=limits,
            )
        return kwargs

    def _build_request_body(
        self, request: Any, thinking_enabled: bool | None = None
    ) -> dict:
        """Internal helper for tests and shared building."""
        return build_request_body(
            request,
            self._nim_settings,
            thinking_enabled=self._is_thinking_enabled(request, thinking_enabled),
        )

    def _prepare_create_body(self, body: dict[str, Any]) -> dict[str, Any]:
        """Strip private request metadata before calling NVIDIA NIM."""
        return body_without_nim_tool_argument_aliases(body)

    def _tool_argument_aliases(self, body: dict[str, Any]) -> dict[str, dict[str, str]]:
        """Return NIM tool argument aliases captured while building this request."""
        return nim_tool_argument_aliases_from_body(body)

    def _get_retry_request_body(self, error: Exception, body: dict) -> dict | None:
        """Retry once with a downgraded body when NIM rejects a known field or times out."""
        logger.debug(
            "NIM_STREAM: _get_retry_request_body called with error type={} error={}",
            type(error).__name__,
            str(error)[:200],
        )
        status_code = getattr(error, "status_code", None)
        is_timeout = isinstance(
            error, (openai.APITimeoutError, httpx.TimeoutException, httpx.ReadTimeout)
        )
        logger.debug(
            "NIM_STREAM: is_timeout={} status_code={}", is_timeout, status_code
        )

        if (
            not isinstance(error, openai.BadRequestError)
            and status_code != 400
            and not is_timeout
        ):
            logger.debug(
                "NIM_STREAM: no retry - not BadRequestError, not 400, not timeout"
            )
            return None

        error_text = str(error)
        error_body = getattr(error, "body", None)
        if error_body is not None:
            raw_body = json.dumps(error_body, default=str)
            error_text = f"{error_text} {raw_body}"
        error_text_lower = error_text.lower()
        logger.debug("NIM_STREAM: error_text={}", error_text_lower[:500])

        if is_timeout or "timeout" in error_text_lower:
            retry_body = clone_body_without_system_role(body)
            if retry_body is not None:
                logger.warning(
                    "NIM_STREAM: retrying without system role messages after timeout"
                )
                return retry_body
            return None

        if "reasoning_budget" in error_text_lower:
            retry_body = clone_body_without_reasoning_budget(body)
            if retry_body is not None:
                logger.warning(
                    "NIM_STREAM: retrying without reasoning_budget after 400 error"
                )
                return retry_body
            return None

        if "chat_template" in error_text_lower:
            retry_body = clone_body_without_chat_template(body)
            if retry_body is not None:
                logger.warning(
                    "NIM_STREAM: retrying without chat_template after 400 error"
                )
                return retry_body
            return None

        if "reasoning_content" in error_text_lower:
            retry_body = clone_body_without_reasoning_content(body)
            if retry_body is not None:
                logger.warning(
                    "NIM_STREAM: retrying without reasoning_content after 400 error"
                )
                return retry_body
            return None

        if "reasoning_effort" in error_text_lower:
            retry_body = clone_body_without_reasoning_effort(body)
            if retry_body is not None:
                logger.warning(
                    "NIM_STREAM: retrying without reasoning_effort after 400 error"
                )
                return retry_body
            return None

        if "role" in error_text_lower and "system" in error_text_lower:
            retry_body = clone_body_without_system_role(body)
            if retry_body is not None:
                logger.warning(
                    "NIM_STREAM: retrying without system role messages after 400 error"
                )
                return retry_body
            return None

        # No specific error text pattern matched — do not blindly retry with
        # a shotgun body transformation (merging system messages, stripping
        # unknown fields). The change would almost certainly be unrelated to
        # the actual error, wasting retry capacity and adding latency.
        logger.warning(
            "NIM_STREAM: no matching retry pattern for 400 error, not retrying."
            " raw_body={}",
            json.dumps(error_body, default=str) if error_body is not None else "N/A",
        )
        return None
