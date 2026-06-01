"""Request builder for Google AI Studio (Gemini) provider."""

from typing import Any

from loguru import logger

from core.anthropic import ReasoningReplayMode, build_base_request_body
from core.anthropic.conversion import OpenAIConversionError
from providers.exceptions import InvalidRequestError

# Gemma models served through Google AI Studio's OpenAI-compatible endpoint
# do NOT support the ``reasoning_content`` field on assistant messages.
# They also reject ``reasoning_effort``.  We detect them by model ID and
# fall back to ``THINK_TAGS`` mode (``<think>`` tags inside plain text).
_GEMMA_MODEL_SUBSTRING = "gemma"


def _is_gemma_model(model_name: str) -> bool:
    """Return whether a model ID identifies a Gemma (non-thinking) model."""
    return _GEMMA_MODEL_SUBSTRING in model_name.lower()


def build_request_body(request_data: Any, *, thinking_enabled: bool) -> dict:
    """Build OpenAI-format request body from Anthropic request."""
    model = getattr(request_data, "model", "?")
    logger.debug(
        "GEMINI_REQUEST: conversion start model={} msgs={}",
        model,
        len(getattr(request_data, "messages", [])),
    )

    gemma = _is_gemma_model(str(model))
    if gemma:
        # Gemma models reject ``reasoning_content`` — use <think> tags instead.
        reasoning_replay = ReasoningReplayMode.THINK_TAGS
    else:
        reasoning_replay = ReasoningReplayMode.REASONING_CONTENT

    try:
        body = build_base_request_body(
            request_data,
            reasoning_replay=reasoning_replay,
        )
    except OpenAIConversionError as exc:
        raise InvalidRequestError(str(exc)) from exc

    # Strip reasoning_effort for Gemma — not supported.
    if gemma:
        body.pop("reasoning_effort", None)

    logger.debug(
        "GEMINI_REQUEST: conversion done model={} msgs={} tools={} gemma={}",
        body.get("model"),
        len(body.get("messages", [])),
        len(body.get("tools", [])),
        gemma,
    )
    return body
