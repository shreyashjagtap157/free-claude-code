"""Tests for core/anthropic/request_body_utils.py — shared request body utilities."""

from core.anthropic.request_body_utils import (
    clone_body_without_reasoning_content,
    clone_body_without_reasoning_effort,
    strip_message_reasoning_content,
)


class TestStripMessageReasoningContent:
    def test_strips_reasoning_content_from_assistant_messages(self):
        body = {
            "messages": [
                {"role": "user", "content": "hi"},
                {
                    "role": "assistant",
                    "content": "answer",
                    "reasoning_content": "thought",
                },
            ]
        }
        assert strip_message_reasoning_content(body) is True
        assert "reasoning_content" not in body["messages"][1]
        assert body["messages"][1]["content"] == "answer"

    def test_returns_false_when_no_reasoning_content(self):
        body = {
            "messages": [
                {"role": "user", "content": "hi"},
                {"role": "assistant", "content": "answer"},
            ]
        }
        assert strip_message_reasoning_content(body) is False

    def test_returns_false_for_non_list_messages(self):
        body = {"messages": "not a list"}
        assert strip_message_reasoning_content(body) is False

    def test_returns_false_for_missing_messages(self):
        body = {"model": "test"}
        assert strip_message_reasoning_content(body) is False

    def test_strips_from_multiple_assistant_messages(self):
        body = {
            "messages": [
                {"role": "user", "content": "q1"},
                {
                    "role": "assistant",
                    "content": "a1",
                    "reasoning_content": "t1",
                },
                {"role": "user", "content": "q2"},
                {
                    "role": "assistant",
                    "content": "a2",
                    "reasoning_content": "t2",
                },
            ]
        }
        assert strip_message_reasoning_content(body) is True
        assert "reasoning_content" not in body["messages"][1]
        assert "reasoning_content" not in body["messages"][3]


class TestCloneBodyWithoutReasoningContent:
    def test_clones_and_strips(self):
        body = {
            "model": "test",
            "messages": [
                {"role": "user", "content": "hi"},
                {
                    "role": "assistant",
                    "content": "answer",
                    "reasoning_content": "secret",
                },
            ],
        }
        cloned = clone_body_without_reasoning_content(body)
        assert cloned is not None
        assert "reasoning_content" not in cloned["messages"][1]
        # Original is not mutated.
        assert body["messages"][1]["reasoning_content"] == "secret"

    def test_returns_none_when_unchanged(self):
        body = {
            "model": "test",
            "messages": [{"role": "user", "content": "hi"}],
        }
        assert clone_body_without_reasoning_content(body) is None


class TestCloneBodyWithoutReasoningEffort:
    def test_clones_and_strips(self):
        body = {
            "model": "test",
            "messages": [{"role": "user", "content": "hi"}],
            "reasoning_effort": "high",
        }
        cloned = clone_body_without_reasoning_effort(body)
        assert cloned is not None
        assert "reasoning_effort" not in cloned
        # Original is not mutated.
        assert body["reasoning_effort"] == "high"

    def test_returns_none_when_field_absent(self):
        body = {
            "model": "test",
            "messages": [{"role": "user", "content": "hi"}],
        }
        assert clone_body_without_reasoning_effort(body) is None
