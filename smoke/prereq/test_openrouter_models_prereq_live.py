"""Live integration: hit the real OpenRouter /models endpoint and validate metadata extraction."""

from __future__ import annotations

import httpx
import pytest

from providers.model_listing import (
    ProviderModelInfo,
    extract_openrouter_tool_model_infos,
)

pytestmark = [pytest.mark.live, pytest.mark.smoke_target("providers")]
_OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
_OPENROUTER_MODELS_TIMEOUT_S = 15.0
_PRIORITY_MODEL_IDS = (
    "anthropic/claude-sonnet-4",
    "openai/gpt-4o",
    "mistralai/mistral-large",
    "deepseek/deepseek-chat",
    "google/gemini-pro",
)


def _openrouter_api_key() -> str | None:
    """Return the OpenRouter API key from the environment, or None."""
    from config.settings import get_settings

    return get_settings().open_router_api_key.get_secret_value() or None


def test_openrouter_models_extracts_metadata_for_known_models() -> None:
    """Fetch real OpenRouter model list, parse with extract_openrouter_tool_model_infos,
    and verify that capability metadata fields are populated for well-known models."""
    api_key = _openrouter_api_key()
    if not api_key:
        pytest.skip("missing_env: OPENROUTER_API_KEY is not configured")

    response = httpx.get(
        _OPENROUTER_MODELS_URL,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=_OPENROUTER_MODELS_TIMEOUT_S,
    )
    response.raise_for_status()
    payload = response.json()

    model_infos = extract_openrouter_tool_model_infos(
        payload, provider_name="open_router"
    )
    assert model_infos, "no tool-capable models parsed from OpenRouter response"

    # Build a lookup for assertions
    info_by_id: dict[str, ProviderModelInfo] = {
        info.model_id: info for info in model_infos
    }

    # Check that priority models are present and have populated metadata.
    # OpenRouter does not guarantee max_output_tokens for all models
    # (it depends on top_provider.max_completion_tokens), so we track
    # how many have it vs. how many do not.
    found_priority: int = 0
    priority_with_max_output: int = 0
    priority_with_context_window: int = 0
    priority_with_thinking: int = 0
    for model_id in _PRIORITY_MODEL_IDS:
        info = info_by_id.get(model_id)
        if info is None:
            continue
        found_priority += 1

        # Track: did the API provide max_output_tokens for this model?
        if info.max_output_tokens is not None:
            assert isinstance(info.max_output_tokens, int)
            assert info.max_output_tokens > 0
            priority_with_max_output += 1

        # context_window should be populated from context_length for priority models
        if info.context_window is not None:
            assert isinstance(info.context_window, int)
            assert info.context_window > 0
            priority_with_context_window += 1

        # supports_thinking should be populated for modern priority models
        if info.supports_thinking is not None:
            assert isinstance(info.supports_thinking, bool)
            priority_with_thinking += 1

        # supports_vision type must be valid (value may be None if no architecture metadata)
        assert isinstance(info.supports_vision, bool | None), (
            f"{model_id}: supports_vision must be bool or None"
        )

    assert found_priority > 0, (
        f"none of the priority models {_PRIORITY_MODEL_IDS} "
        f"were found in the OpenRouter response "
        f"(total tool-capable models parsed: {len(model_infos)})"
    )

    # Most priority models should have context_window populated
    min_with_context = found_priority * 4 // 5  # floor of 80%
    assert priority_with_context_window >= min_with_context, (
        f"expected at least {min_with_context}/{found_priority} priority models "
        f"to have context_window, got {priority_with_context_window}"
    )

    # At least one priority model should have max_output_tokens populated
    assert priority_with_max_output > 0, (
        f"no priority model has max_output_tokens populated "
        f"({priority_with_max_output}/{found_priority})"
    )

    # At least one priority model should have supports_thinking populated
    assert priority_with_thinking > 0, (
        f"no priority model has supports_thinking populated "
        f"({priority_with_thinking}/{found_priority})"
    )

    # Verify that at least one model has supports_vision=True and at least one has False
    vision_capable_count = sum(
        1 for info in model_infos if info.supports_vision is True
    )
    non_vision_count = sum(1 for info in model_infos if info.supports_vision is False)
    assert vision_capable_count > 0, (
        "expected at least one tool-capable model with vision support"
    )
    assert non_vision_count > 0, (
        "expected at least one tool-capable model without vision support"
    )

    # Sanity: no unexpected None fields on any model
    for info in model_infos:
        assert info.model_id, "model_id must be a non-empty string"
        assert isinstance(info.max_output_tokens, int | None), (
            f"{info.model_id}: invalid max_output_tokens type"
        )
        assert isinstance(info.context_window, int | None), (
            f"{info.model_id}: invalid context_window type"
        )
        assert isinstance(info.supports_thinking, bool | None), (
            f"{info.model_id}: invalid supports_thinking type"
        )
        assert isinstance(info.supports_vision, bool | None), (
            f"{info.model_id}: invalid supports_vision type"
        )
        assert isinstance(info.supports_tools, bool | None), (
            f"{info.model_id}: invalid supports_tools type"
        )
        assert isinstance(info.supports_streaming, bool | None), (
            f"{info.model_id}: invalid supports_streaming type"
        )
