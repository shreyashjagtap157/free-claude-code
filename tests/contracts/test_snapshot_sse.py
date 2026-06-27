"""Snapshot tests for deterministic SSE event output (TST-05).

Uses ``syrupy`` for snapshot comparison. Run with:

    uv run pytest tests/contracts/test_snapshot_sse.py --snapshot-update

to create/update snapshots, then subsequent runs compare against them.
"""

from __future__ import annotations

import json

import pytest

from core.anthropic.sse import SSEBuilder
from core.anthropic.stream_contracts import parse_sse_lines


class TestSSEBuilderOutput:
    """Verify SSE event output shape with snapshot testing."""

    def _events_to_json(self, sse_events: str) -> str:
        """Convert raw SSE text to structured JSON for deterministic comparison."""
        lines = sse_events.strip().split("\n")
        events = []
        for line in lines:
            if line.startswith("data: "):
                try:
                    events.append(json.loads(line[6:]))
                except json.JSONDecodeError:
                    events.append({"raw": line})
            elif line.startswith("event: "):
                events.append({"event_type": line[7:]})
            elif line == "":
                events.append({"blank": True})
        return json.dumps(events, indent=2, sort_keys=True)

    def collect(self, *event_groups) -> str:
        """Collect SSE event strings from multiple groups and return as JSON."""
        all_events: list[str] = []
        for group in event_groups:
            if isinstance(group, str):
                all_events.append(group)
            else:
                all_events.extend(group)
        return self._events_to_json("\n".join(all_events))

    def test_text_message_snapshot(self, snapshot):
        """A simple text message produces deterministic SSE events."""
        builder = SSEBuilder("msg_snap_01", "claude-sonnet-4-20250514")
        event_str = (
            builder.message_start()
            + builder.content_block_start(0, "text")
            + builder.content_block_delta(
                0, "text_delta", "Hello, this is a test message."
            )
            + builder.content_block_stop(0)
            + builder.message_delta("end_turn", 10)
            + builder.message_stop()
        )
        assert snapshot == self._events_to_json(event_str)

    def test_text_then_tool_snapshot(self, snapshot):
        """Text block followed by a tool block produces deterministic events."""
        builder = SSEBuilder("msg_snap_02", "claude-sonnet-4-20250514")
        event_str = (
            builder.message_start()
            + builder.content_block_start(0, "text")
            + builder.content_block_delta(0, "text_delta", "Let me check that.")
            + builder.content_block_stop(0)
            + builder.content_block_start(1, "tool_use", id="tu_01", name="read_file")
            + builder.content_block_delta(1, "input_json_delta", '{"path":"')
            + builder.content_block_delta(1, "input_json_delta", '/tmp/test.txt"}')
            + builder.content_block_stop(1)
            + builder.message_delta("tool_use", 15)
            + builder.message_stop()
        )
        assert snapshot == self._events_to_json(event_str)

    def test_thinking_then_text_snapshot(self, snapshot):
        """Thinking block followed by a text block."""
        builder = SSEBuilder("msg_snap_03", "claude-sonnet-4-20250514")
        event_str = (
            builder.message_start()
            + builder.content_block_start(0, "thinking")
            + builder.content_block_delta(
                0, "thinking_delta", "I need to reason about this."
            )
            + builder.content_block_stop(0)
            + builder.content_block_start(1, "text")
            + builder.content_block_delta(1, "text_delta", "Here is my answer.")
            + builder.content_block_stop(1)
            + builder.message_delta("end_turn", 20)
            + builder.message_stop()
        )
        assert snapshot == self._events_to_json(event_str)

    def test_top_level_error_snapshot(self, snapshot):
        """A top-level error produces a deterministic error SSE event."""
        builder = SSEBuilder("msg_snap_err", "claude-sonnet-4-20250514")
        error_event = builder.emit_top_level_error("API rate limit exceeded")
        assert snapshot == error_event

    def test_emit_error_snapshot(self, snapshot):
        """An assistant-text error block produces deterministic SSE events."""
        builder = SSEBuilder("msg_snap_err2", "claude-sonnet-4-20250514")
        event_str = builder.message_start() + "".join(
            builder.emit_error("Model unavailable")
        )
        assert snapshot == self._events_to_json(event_str)


class TestSSEParsing:
    """Snapshot tests for SSE line parsing."""

    def test_parse_standard_sse(self, snapshot):
        """Parse a standard SSE event stream with text content."""
        sse_input = (
            "event: message_start\n"
            'data: {"type":"message_start","message":{"id":"msg_1"}}\n'
            "\n"
            "event: content_block_start\n"
            'data: {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}}\n'
            "\n"
            "event: content_block_delta\n"
            'data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"Hello"}}\n'
            "\n"
            "event: message_stop\n"
            'data: {"type":"message_stop"}\n'
            "\n"
        )
        events = list(parse_sse_lines(sse_input))
        assert snapshot == json.dumps(events, indent=2)

    def test_parse_error_sse(self, snapshot):
        """Parse an SSE stream containing an API error."""
        sse_input = (
            "event: error\n"
            'data: {"type":"error","error":{"type":"overloaded_error","message":"Overloaded"}}\n'
            "\n"
        )
        events = list(parse_sse_lines(sse_input))
        assert snapshot == json.dumps(events, indent=2)


@pytest.mark.skip(reason="Requires --snapshot-update to create initial snapshots")
def test_snapshot_generation_required():
    """This test passes only after snapshots exist.

    Run: uv run pytest tests/contracts/test_snapshot_sse.py --snapshot-update
    to create the initial snapshots, then remove this skip marker.
    """
    pass
