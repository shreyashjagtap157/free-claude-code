"""Server-side context trimming for providers without prompt caching.

The real Anthropic Claude API has prompt caching (unchanged prefixes are
processed once) and server-side context management.  Non-Anthropic providers
(NVIDIA NIM, etc.) re-process the full context on every request.  This module
reduces token counts by:

1. Stripping ``thinking`` / ``redacted_thinking`` blocks from assistant
   messages (non-Anthropic providers cannot use them).
2. Truncating oversized ``tool_result`` content blocks.
3. Dropping the oldest conversation turns when the total exceeds a
   configurable token budget.
"""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from loguru import logger

from .content import get_block_attr, get_block_type
from .tokens import get_token_count

# Block types that are pure waste for non-Anthropic providers.
_THINKING_BLOCK_TYPES = frozenset({"thinking", "redacted_thinking"})

_TRIMMED_MARKER = "[Earlier conversation history was trimmed to fit context budget]"


# ---------------------------------------------------------------------------
# 1.  Strip thinking blocks
# ---------------------------------------------------------------------------


def _strip_thinking_blocks(messages: list[Any]) -> list[Any]:
    """Remove ``thinking`` and ``redacted_thinking`` blocks from assistant messages.

    Returns a new list; original messages are not mutated.
    """
    result: list[Any] = []
    stripped_count = 0
    for msg in messages:
        role = get_block_attr(msg, "role")
        content = get_block_attr(msg, "content")
        if role != "assistant" or not isinstance(content, list):
            result.append(msg)
            continue

        filtered = [
            block
            for block in content
            if get_block_type(block) not in _THINKING_BLOCK_TYPES
        ]
        count_removed = len(content) - len(filtered)
        if count_removed == 0:
            result.append(msg)
            continue

        stripped_count += count_removed
        # Shallow copy preserving Pydantic model or dict shape.
        if hasattr(msg, "model_copy"):
            new_msg = msg.model_copy(update={"content": filtered or ""})
        elif isinstance(msg, dict):
            new_msg = {**msg, "content": filtered or ""}
        else:
            result.append(msg)
            continue
        result.append(new_msg)

    if stripped_count:
        logger.debug(
            "CONTEXT_TRIM: stripped {} thinking/redacted_thinking blocks",
            stripped_count,
        )
    return result


# ---------------------------------------------------------------------------
# 2.  Truncate oversized tool results
# ---------------------------------------------------------------------------


def _estimate_block_tokens(block: Any) -> int:
    """Rough token estimate for a single content block."""
    btype = get_block_type(block)
    if btype == "text":
        text = get_block_attr(block, "text", "")
        return len(str(text)) // 4  # rough char/4 estimate
    if btype == "tool_result":
        content = get_block_attr(block, "content", "")
        if isinstance(content, str):
            return len(content) // 4
        if isinstance(content, list):
            total = 0
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    total += len(str(item.get("text", ""))) // 4
                else:
                    total += len(json.dumps(item, default=str)) // 4
            return total
        return len(json.dumps(content, default=str)) // 4
    return 0


def _truncate_text_to_tokens(text: str, max_tokens: int) -> str:
    """Truncate text to approximately ``max_tokens`` tokens (char/4 heuristic)."""
    max_chars = max_tokens * 4
    if len(text) <= max_chars:
        return text
    original_approx = len(text) // 4
    return (
        text[:max_chars] + f"\n... [truncated, original was ~{original_approx} tokens]"
    )


def _truncate_tool_result_content(content: Any, max_tokens: int) -> tuple[Any, bool]:
    """Truncate a tool_result's content if it exceeds ``max_tokens``.

    Returns ``(new_content, was_truncated)``.
    """
    if isinstance(content, str):
        if len(content) // 4 <= max_tokens:
            return content, False
        return _truncate_text_to_tokens(content, max_tokens), True

    if isinstance(content, list):
        total_tokens = 0
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                total_tokens += len(str(item.get("text", ""))) // 4
            else:
                total_tokens += len(json.dumps(item, default=str)) // 4
        if total_tokens <= max_tokens:
            return content, False

        # Truncate text blocks proportionally.
        remaining = max_tokens
        new_items: list[Any] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text = str(item.get("text", ""))
                item_tokens = len(text) // 4
                if item_tokens > remaining:
                    new_items.append(
                        {
                            **item,
                            "text": _truncate_text_to_tokens(text, max(remaining, 100)),
                        }
                    )
                    remaining = 0
                else:
                    new_items.append(item)
                    remaining -= item_tokens
            else:
                new_items.append(item)
        return new_items, True

    return content, False


def _truncate_tool_results(
    messages: list[Any], max_tool_result_tokens: int
) -> list[Any]:
    """Truncate oversized ``tool_result`` blocks across all messages."""
    if max_tool_result_tokens <= 0:
        return messages

    result: list[Any] = []
    truncated_count = 0

    for msg in messages:
        content = get_block_attr(msg, "content")
        if not isinstance(content, list):
            result.append(msg)
            continue

        new_content: list[Any] = []
        msg_changed = False
        for block in content:
            if get_block_type(block) == "tool_result":
                raw_content = get_block_attr(block, "content", "")
                new_raw, was_truncated = _truncate_tool_result_content(
                    raw_content, max_tool_result_tokens
                )
                if was_truncated:
                    truncated_count += 1
                    msg_changed = True
                    if hasattr(block, "model_copy"):
                        new_content.append(
                            block.model_copy(update={"content": new_raw})
                        )
                    elif isinstance(block, dict):
                        new_content.append({**block, "content": new_raw})
                    else:
                        new_content.append(block)
                else:
                    new_content.append(block)
            else:
                new_content.append(block)

        if msg_changed:
            if hasattr(msg, "model_copy"):
                result.append(msg.model_copy(update={"content": new_content}))
            elif isinstance(msg, dict):
                result.append({**msg, "content": new_content})
            else:
                result.append(msg)
        else:
            result.append(msg)

    if truncated_count:
        logger.debug(
            "CONTEXT_TRIM: truncated {} oversized tool_result blocks (cap={})",
            truncated_count,
            max_tool_result_tokens,
        )
    return result


# ---------------------------------------------------------------------------
# 3.  Drop oldest turns to meet token budget
# ---------------------------------------------------------------------------


def _collect_tool_use_ids(msg: Any) -> set[str]:
    """Return tool_use IDs present in an assistant message."""
    content = get_block_attr(msg, "content")
    if not isinstance(content, list):
        return set()
    ids: set[str] = set()
    for block in content:
        if get_block_type(block) == "tool_use":
            tid = get_block_attr(block, "id")
            if tid:
                ids.add(str(tid))
    return ids


def _collect_tool_result_ids(msg: Any) -> set[str]:
    """Return tool_use_ids referenced by tool_result blocks in a user message."""
    content = get_block_attr(msg, "content")
    if not isinstance(content, list):
        return set()
    ids: set[str] = set()
    for block in content:
        if get_block_type(block) == "tool_result":
            tid = get_block_attr(block, "tool_use_id")
            if tid:
                ids.add(str(tid))
    return ids


def _make_trimmed_marker_message(msg_template: Any) -> Any:
    """Create a user message with the trimmed-history marker.

    Uses the same type (Pydantic model or dict) as ``msg_template``.
    """
    if hasattr(msg_template, "model_copy"):
        return msg_template.model_copy(
            update={"role": "user", "content": _TRIMMED_MARKER}
        )
    return {"role": "user", "content": _TRIMMED_MARKER}


def _enforce_token_budget(
    messages: list[Any],
    system: Any,
    tools: Any,
    max_context_tokens: int,
) -> list[Any]:
    """Drop oldest messages until total tokens fit within ``max_context_tokens``."""
    if max_context_tokens <= 0 or not messages:
        return messages

    # Pre-calculate base token count for system + tools.
    base_tokens = get_token_count([], system, tools)

    # Pre-calculate token count for each individual message.
    msg_tokens = [get_token_count([msg]) for msg in messages]
    current_tokens = base_tokens + sum(msg_tokens)

    if current_tokens <= max_context_tokens:
        return messages

    # We always keep: first message (index 0) and the last 2 messages
    # (1 recent user/assistant pair).  Everything between is droppable.
    keep_tail = min(2, len(messages))
    keep_head = 1

    if len(messages) <= keep_head + keep_tail:
        return messages

    head = messages[:keep_head]
    droppable = list(messages[keep_head:-keep_tail])
    tail = messages[-keep_tail:]

    head_tokens = msg_tokens[0]
    tail_tokens = sum(msg_tokens[-keep_tail:])
    droppable_tokens = msg_tokens[keep_head:-keep_tail]

    marker_msg = _make_trimmed_marker_message(messages[0])
    marker_tokens = get_token_count([marker_msg])

    # Build a set of tool_use IDs required by the tail (tool_results that need
    # their corresponding assistant tool_use message kept).
    required_tool_use_ids: set[str] = set()
    for msg in tail:
        required_tool_use_ids.update(_collect_tool_result_ids(msg))

    # Also: if an assistant message in the tail has tool_use, we need to keep
    # its corresponding tool_result in tail (which it already is) but also
    # ensure we don't orphan it.
    tail_tool_use_ids: set[str] = set()
    for msg in tail:
        tail_tool_use_ids.update(_collect_tool_use_ids(msg))

    # Drop from the front of droppable until within budget.
    dropped_count = 0
    running_droppable_tokens = sum(droppable_tokens)

    while droppable:
        candidate = droppable[0]
        candidate_role = get_block_attr(candidate, "role")

        # Check if this message has tool_use IDs required by the tail.
        if candidate_role == "assistant":
            msg_tool_ids = _collect_tool_use_ids(candidate)
            if msg_tool_ids & required_tool_use_ids:
                # Cannot drop: tail has tool_results that reference this.
                break

        # Check if this is a user message with tool_results whose assistant
        # tool_use is in the tail.
        if candidate_role == "user":
            msg_result_ids = _collect_tool_result_ids(candidate)
            if msg_result_ids & tail_tool_use_ids:
                break

        dropped_token_val = droppable_tokens.pop(0)
        droppable.pop(0)
        running_droppable_tokens -= dropped_token_val
        dropped_count += 1

        test_tokens = (
            base_tokens
            + head_tokens
            + running_droppable_tokens
            + tail_tokens
            + marker_tokens
        )
        if test_tokens <= max_context_tokens:
            break

    if dropped_count == 0:
        return messages

    # Insert marker at the boundary.
    marker = _make_trimmed_marker_message(messages[0])
    trimmed = [*head, marker, *droppable, *tail]

    new_tokens = (
        base_tokens
        + head_tokens
        + running_droppable_tokens
        + tail_tokens
        + marker_tokens
    )
    logger.info(
        "CONTEXT_TRIM: dropped {} messages, tokens {} -> {} (budget={})",
        dropped_count,
        current_tokens,
        new_tokens,
        max_context_tokens,
    )
    return trimmed


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def trim_messages_for_context_budget(
    messages: list[Any],
    system: Any = None,
    tools: Any = None,
    *,
    max_context_tokens: int = 0,
    max_tool_result_tokens: int = 0,
) -> list[Any]:
    """Apply server-side context trimming to reduce provider token consumption.

    Strategies applied in order:

    1. Strip ``thinking`` / ``redacted_thinking`` blocks from assistant messages.
    2. Truncate oversized ``tool_result`` content blocks.
    3. Drop oldest conversation turns to meet ``max_context_tokens`` budget.

    When ``max_context_tokens`` is 0 (disabled), only steps 1-2 run
    (step 2 only if ``max_tool_result_tokens > 0``).

    Returns a new message list; original messages are not mutated.
    """
    if not messages:
        return messages

    # Deep copy to avoid mutating the caller's data.
    trimmed = deepcopy(messages)

    # 1. Strip thinking blocks (always, for non-Anthropic providers).
    trimmed = _strip_thinking_blocks(trimmed)

    # 2. Truncate oversized tool results.
    if max_tool_result_tokens > 0:
        trimmed = _truncate_tool_results(trimmed, max_tool_result_tokens)

    # 3. Enforce token budget.
    if max_context_tokens > 0:
        trimmed = _enforce_token_budget(trimmed, system, tools, max_context_tokens)

    return trimmed
