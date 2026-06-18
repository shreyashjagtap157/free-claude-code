"""Cache-control marker injection for Anthropic-native request bodies.

Enterprise-grade prompt caching should inject ``cache_control`` markers on
predictable prompt segments (system prompt, tools, first user message) so
the upstream Anthropic API can serve cached responses for shared prefixes.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

EPHEMERAL: dict[str, str] = {"type": "ephemeral"}


def ensure_system_cache_control(body: dict[str, Any]) -> None:
    """Inject ``cache_control`` on the system prompt when absent.

    Only injects when the system prompt is already a list — never converts
    a plain string to a list, which would change the API contract.
    """
    system = body.get("system")
    if system is None:
        return

    if isinstance(system, list):
        if (
            system
            and isinstance(system[-1], dict)
            and "cache_control" not in system[-1]
        ):
            last = dict(system[-1])
            last["cache_control"] = EPHEMERAL
            system[-1] = last
            logger.debug("CACHE_CTRL: injected cache_control on last system block")
    else:
        logger.debug(
            "CACHE_CTRL: unexpected system type={}, skipping", type(system).__name__
        )


def ensure_tools_cache_control(body: dict[str, Any]) -> None:
    """Inject ``cache_control`` on the last tool definition when absent."""
    tools = body.get("tools")
    if not isinstance(tools, list) or not tools:
        return

    last_tool = tools[-1]
    if isinstance(last_tool, dict) and "cache_control" not in last_tool:
        tools[-1] = {**last_tool, "cache_control": EPHEMERAL}
        logger.debug(
            "CACHE_CTRL: injected cache_control on tool '{}'",
            last_tool.get("name", "unknown"),
        )


def ensure_messages_cache_control(body: dict[str, Any]) -> None:
    """Inject ``cache_control`` on the first user content block when absent.

    Only injects when the content is already a list of blocks — never converts
    a plain string to a list, which would change the API contract.
    """
    messages = body.get("messages")
    if not isinstance(messages, list) or not messages:
        return

    for msg in messages:
        if not isinstance(msg, dict):
            continue
        if msg.get("role") != "user":
            continue
        content = msg.get("content")
        if isinstance(content, list) and content:
            last_block = content[-1]
            if isinstance(last_block, dict) and "cache_control" not in last_block:
                last_block["cache_control"] = EPHEMERAL
                logger.debug(
                    "CACHE_CTRL: injected cache_control on first user message block"
                )
            break


def inject_cache_control(body: dict[str, Any]) -> dict[str, Any]:
    """Apply all cache-control injections to *body* (mutates and returns it).

    Skips injection when the request already has cache_control markers
    (i.e. the client is managing caching itself).
    """
    has_existing = _body_has_cache_control(body)
    if has_existing:
        logger.debug(
            "CACHE_CTRL: body already has cache_control markers, skipping injection"
        )
        return body
    ensure_system_cache_control(body)
    ensure_tools_cache_control(body)
    ensure_messages_cache_control(body)
    return body


def _body_has_cache_control(body: dict[str, Any]) -> bool:
    """Return True when any part of the body already carries ``cache_control``."""
    system = body.get("system")
    if isinstance(system, list):
        for block in system:
            if isinstance(block, dict) and "cache_control" in block:
                return True

    tools = body.get("tools")
    if isinstance(tools, list):
        for tool in tools:
            if isinstance(tool, dict) and "cache_control" in tool:
                return True

    messages = body.get("messages")
    if isinstance(messages, list):
        for msg in messages:
            if isinstance(msg, dict):
                content = msg.get("content")
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and "cache_control" in block:
                            return True
    return False
