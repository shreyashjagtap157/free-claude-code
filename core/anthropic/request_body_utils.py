"""Shared request body manipulation utilities for OpenAI-compatible providers.

These helpers strip unsupported fields from request bodies and are used by
the retry logic in multiple providers (NVIDIA NIM, Google AI Studio, etc.).
"""

from copy import deepcopy
from typing import Any


def strip_message_reasoning_content(body: dict[str, Any]) -> bool:
    """Remove ``reasoning_content`` from all messages **in place**.

    Returns ``True`` when at least one field was removed.
    """
    removed = False
    messages = body.get("messages")
    if not isinstance(messages, list):
        return False
    for message in messages:
        if (
            isinstance(message, dict)
            and message.pop("reasoning_content", None) is not None
        ):
            removed = True
    return removed


def clone_body_without_reasoning_content(
    body: dict[str, Any],
) -> dict[str, Any] | None:
    """Clone a request body and strip assistant message ``reasoning_content`` fields.

    Returns ``None`` when no ``reasoning_content`` fields were present.
    """
    cloned_body = deepcopy(body)
    if not strip_message_reasoning_content(cloned_body):
        return None
    return cloned_body


def clone_body_without_reasoning_effort(
    body: dict[str, Any],
) -> dict[str, Any] | None:
    """Clone a request body and strip the ``reasoning_effort`` field.

    Returns ``None`` when the field was not present.
    """
    if "reasoning_effort" not in body:
        return None
    cloned_body = deepcopy(body)
    cloned_body.pop("reasoning_effort", None)
    return cloned_body
