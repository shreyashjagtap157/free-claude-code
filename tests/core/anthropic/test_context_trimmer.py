"""Tests for ``core.anthropic.context_trimmer``."""

from __future__ import annotations

from typing import Any

from api.models.anthropic import (
    ContentBlockText,
    ContentBlockThinking,
    ContentBlockToolResult,
    ContentBlockToolUse,
    Message,
)
from core.anthropic.context_trimmer import (
    _TRIMMED_MARKER,
    _enforce_token_budget,
    _strip_thinking_blocks,
    _truncate_tool_results,
    trim_messages_for_context_budget,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _user(text: str) -> Message:
    return Message(role="user", content=text)


def _assistant(text: str) -> Message:
    return Message(role="assistant", content=text)


def _assistant_with_thinking(text: str, thinking: str) -> Message:
    return Message(
        role="assistant",
        content=[
            ContentBlockThinking(type="thinking", thinking=thinking),
            ContentBlockText(type="text", text=text),
        ],
    )


def _assistant_tool_use(tool_id: str, name: str, inp: dict[str, Any]) -> Message:
    return Message(
        role="assistant",
        content=[
            ContentBlockToolUse(type="tool_use", id=tool_id, name=name, input=inp),
        ],
    )


def _user_tool_result(tool_use_id: str, content: str) -> Message:
    return Message(
        role="user",
        content=[
            ContentBlockToolResult(
                type="tool_result", tool_use_id=tool_use_id, content=content
            ),
        ],
    )


def _long_text(n_chars: int = 20_000) -> str:
    """Generate a long repeating string of approximately ``n_chars`` characters."""
    base = "Lorem ipsum dolor sit amet, consectetur adipiscing elit. "
    return (base * (n_chars // len(base) + 1))[:n_chars]


# ---------------------------------------------------------------------------
# 1. No-op when disabled
# ---------------------------------------------------------------------------


class TestNoOp:
    def test_disabled_returns_messages_unchanged(self):
        msgs = [_user("hello"), _assistant("hi")]
        result = trim_messages_for_context_budget(
            msgs, max_context_tokens=0, max_tool_result_tokens=0
        )
        # Still strips thinking blocks by default.
        assert len(result) == len(msgs)

    def test_empty_messages(self):
        result = trim_messages_for_context_budget([])
        assert result == []


# ---------------------------------------------------------------------------
# 2. Thinking block stripping
# ---------------------------------------------------------------------------


class TestStripThinking:
    def test_strips_thinking_blocks_from_assistant(self):
        msgs = [
            _user("hello"),
            _assistant_with_thinking("response", "my internal reasoning"),
        ]
        result = _strip_thinking_blocks(msgs)
        assert len(result) == 2
        # Assistant message should have only text block now.
        assistant_content = result[1].content
        assert isinstance(assistant_content, list)
        assert len(assistant_content) == 1
        assert assistant_content[0].type == "text"
        assert assistant_content[0].text == "response"

    def test_preserves_user_messages(self):
        msgs = [_user("hello")]
        result = _strip_thinking_blocks(msgs)
        assert len(result) == 1
        assert result[0].content == "hello"

    def test_preserves_assistant_text_only(self):
        msgs = [_assistant("just text")]
        result = _strip_thinking_blocks(msgs)
        assert len(result) == 1
        assert result[0].content == "just text"


# ---------------------------------------------------------------------------
# 3. Tool result truncation
# ---------------------------------------------------------------------------


class TestTruncateToolResults:
    def test_truncates_large_tool_result(self):
        big_content = _long_text(40_000)  # ~10k tokens
        msgs = [_user_tool_result("t1", big_content)]
        result = _truncate_tool_results(msgs, max_tool_result_tokens=1000)
        truncated_content = result[0].content[0].content
        assert isinstance(truncated_content, str)
        assert len(truncated_content) < len(big_content)
        assert "truncated" in truncated_content

    def test_leaves_small_tool_result_unchanged(self):
        small_content = "short result"
        msgs = [_user_tool_result("t1", small_content)]
        result = _truncate_tool_results(msgs, max_tool_result_tokens=1000)
        assert result[0].content[0].content == small_content

    def test_disabled_when_zero(self):
        big_content = _long_text(40_000)
        msgs = [_user_tool_result("t1", big_content)]
        result = _truncate_tool_results(msgs, max_tool_result_tokens=0)
        assert result[0].content[0].content == big_content


# ---------------------------------------------------------------------------
# 4. Token budget enforcement
# ---------------------------------------------------------------------------


class TestEnforceTokenBudget:
    def test_no_trimming_when_within_budget(self):
        msgs = [_user("hello"), _assistant("hi")]
        result = _enforce_token_budget(msgs, None, None, max_context_tokens=100_000)
        assert len(result) == len(msgs)

    def test_drops_oldest_messages_when_over_budget(self):
        # Build a conversation with many turns.
        msgs: list[Message] = []
        for i in range(20):
            msgs.append(_user(f"Question {i}: " + _long_text(2000)))
            msgs.append(_assistant(f"Answer {i}: " + _long_text(2000)))

        # Very tight budget.
        result = _enforce_token_budget(msgs, None, None, max_context_tokens=5000)
        assert len(result) < len(msgs)
        # First message kept.
        assert result[0].content == msgs[0].content
        # Last messages kept.
        assert result[-1].content == msgs[-1].content

    def test_injects_trimmed_marker(self):
        msgs: list[Message] = []
        for i in range(20):
            msgs.append(_user(f"Q{i}: " + _long_text(2000)))
            msgs.append(_assistant(f"A{i}: " + _long_text(2000)))

        result = _enforce_token_budget(msgs, None, None, max_context_tokens=5000)
        # Marker should be present.
        marker_msgs = [
            m
            for m in result
            if isinstance(m.content, str) and _TRIMMED_MARKER in m.content
        ]
        assert len(marker_msgs) == 1

    def test_disabled_when_zero(self):
        msgs = [_user("hello"), _assistant("hi")]
        result = _enforce_token_budget(msgs, None, None, max_context_tokens=0)
        assert len(result) == len(msgs)


# ---------------------------------------------------------------------------
# 5. Tool pair preservation
# ---------------------------------------------------------------------------


class TestToolPairPreservation:
    def test_keeps_tool_pairs_when_tail_references_them(self):
        """When a tool_result in the tail references a tool_use, that tool_use must be kept."""
        msgs = [
            _user("start"),
            _assistant("ok"),
            # Middle: a tool call and result
            _assistant_tool_use("tool_1", "Read", {"path": "/a.py"}),
            _user_tool_result("tool_1", _long_text(10_000)),
            # Recent: references a tool
            _assistant_tool_use("tool_2", "Write", {"path": "/b.py"}),
            _user_tool_result("tool_2", "done"),
            _assistant("final answer"),
            _user("follow up"),
        ]
        # Budget should be enough for head + tail + marker, but not all middle.
        result = _enforce_token_budget(msgs, None, None, max_context_tokens=5000)
        # The tail (last 4 messages) must be present.
        assert result[-1].content == "follow up"


# ---------------------------------------------------------------------------
# 6. First + last message preservation
# ---------------------------------------------------------------------------


class TestBoundaryPreservation:
    def test_first_user_message_always_kept(self):
        msgs: list[Message] = []
        for i in range(20):
            msgs.append(_user(f"Q{i}: " + _long_text(2000)))
            msgs.append(_assistant(f"A{i}: " + _long_text(2000)))

        result = _enforce_token_budget(msgs, None, None, max_context_tokens=5000)
        # First message content matches.
        first_original = msgs[0].content
        assert isinstance(first_original, str)
        assert result[0].content == first_original

    def test_single_turn_never_dropped(self):
        msgs = [_user("hello")]
        result = _enforce_token_budget(msgs, None, None, max_context_tokens=100)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# 7. System prompt + tools budget accounting
# ---------------------------------------------------------------------------


class TestBudgetAccounting:
    def test_large_system_prompt_reduces_message_budget(self):
        system = _long_text(80_000)  # ~20k tokens from system alone
        msgs: list[Message] = []
        for i in range(10):
            msgs.append(_user(f"Q{i}: " + _long_text(4000)))
            msgs.append(_assistant(f"A{i}: " + _long_text(4000)))

        result = _enforce_token_budget(msgs, system, None, max_context_tokens=20_000)
        # With 20k system, only ~10k left for messages => significant trimming.
        assert len(result) < len(msgs)


# ---------------------------------------------------------------------------
# 8. Full pipeline integration
# ---------------------------------------------------------------------------


class TestFullPipeline:
    def test_all_strategies_compose(self):
        """End-to-end: thinking strip + tool truncation + budget enforcement."""
        msgs: list[Message] = [_user("initial question")]

        # Add turns with thinking and large tool results.
        for i in range(15):
            msgs.append(_assistant_with_thinking(f"text_{i}", f"thinking_{i} " * 200))
            msgs.append(_user(f"follow up {i}"))

        # Add a large tool result.
        msgs.append(_assistant_tool_use("t1", "Read", {"path": "big.py"}))
        msgs.append(_user_tool_result("t1", _long_text(40_000)))
        msgs.append(_assistant("final"))
        msgs.append(_user("last question"))

        result = trim_messages_for_context_budget(
            msgs,
            max_context_tokens=10_000,
            max_tool_result_tokens=500,
        )

        # Thinking blocks should be stripped.
        for msg in result:
            if isinstance(msg.content, list):
                for block in msg.content:
                    assert block.type != "thinking"

        # Total should be within reasonable bounds.
        from core.anthropic.tokens import get_token_count

        total = get_token_count(result, None, None)
        assert total <= 15_000  # Some overhead is fine.

    def test_does_not_mutate_original(self):
        msgs = [
            _user("hello"),
            _assistant_with_thinking("reply", "deep thoughts" * 100),
        ]
        original_content_len = len(msgs[1].content)
        trim_messages_for_context_budget(
            msgs,
            max_context_tokens=500,
            max_tool_result_tokens=100,
        )
        # Original message unchanged.
        assert len(msgs[1].content) == original_content_len


class TestToolOrphanPrevention:
    """Verify that context trimming never orphans tool_result blocks."""

    def test_trimmer_does_not_orphan_tool_results_in_tail(self):
        """If the tail has a tool_result referencing an assistant's tool_use,
        that assistant must not be dropped even under budget pressure.

        Dropping it would produce a role:'tool' message without a matching
        tool_call, causing Gemini's 'function_response.name cannot be empty'.
        """
        msgs: list[Message] = [_user("initial")]

        # Pad with enough conversation to force trimming.
        for i in range(10):
            msgs.append(_assistant(_long_text(2000)))
            msgs.append(_user(f"q{i}"))

        # The assistant with tool_use that we must keep.
        msgs.append(_assistant_tool_use("critical_t1", "Read", {"path": "x"}))
        # This tool_result referencing the above will end up in the tail.
        msgs.append(_user_tool_result("critical_t1", "file contents"))

        result = _enforce_token_budget(msgs, None, None, max_context_tokens=3000)

        # Verify the assistant with tool_use "critical_t1" was kept.
        kept_tool_use_ids: set[str] = set()
        kept_tool_result_ids: set[str] = set()
        for msg in result:
            content = msg.content if isinstance(msg.content, list) else []
            for block in content:
                if getattr(block, "type", None) == "tool_use":
                    kept_tool_use_ids.add(block.id)
                elif getattr(block, "type", None) == "tool_result":
                    kept_tool_result_ids.add(block.tool_use_id)

        # Every tool_result must have its matching tool_use present.
        orphaned = kept_tool_result_ids - kept_tool_use_ids
        assert not orphaned, (
            f"Orphaned tool_result IDs (no matching tool_use): {orphaned}"
        )

    def test_trimmer_keeps_tool_pairs_in_middle_droppable(self):
        """Tool_use/tool_result pairs in the droppable region are kept together."""
        msgs: list[Message] = [_user("initial")]

        # Filler before the tool pair.
        for i in range(4):
            msgs.append(_assistant(_long_text(2000)))
            msgs.append(_user(f"q{i}"))

        # Tool pair in the middle of droppable.
        msgs.append(_assistant_tool_use("mid_t1", "Search", {"q": "x"}))
        msgs.append(_user_tool_result("mid_t1", "result"))

        # More filler after.
        for i in range(4):
            msgs.append(_assistant(_long_text(2000)))
            msgs.append(_user(f"q_after_{i}"))

        result = _enforce_token_budget(msgs, None, None, max_context_tokens=5000)

        kept_tool_use_ids: set[str] = set()
        kept_tool_result_ids: set[str] = set()
        for msg in result:
            content = msg.content if isinstance(msg.content, list) else []
            for block in content:
                if getattr(block, "type", None) == "tool_use":
                    kept_tool_use_ids.add(block.id)
                elif getattr(block, "type", None) == "tool_result":
                    kept_tool_result_ids.add(block.tool_use_id)

        orphaned = kept_tool_result_ids - kept_tool_use_ids
        assert not orphaned, (
            f"Orphaned tool_result IDs (no matching tool_use): {orphaned}"
        )
