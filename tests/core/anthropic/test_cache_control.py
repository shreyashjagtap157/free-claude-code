"""Tests for cache-control marker injection on Anthropic-native request bodies."""

from __future__ import annotations

from core.anthropic.cache_control import (
    _body_has_cache_control,
    inject_cache_control,
)


def _desc(d: dict) -> str:
    """Return the ``type`` field from the last system block, or 'no-system'."""
    sys_blocks = d.get("system")
    if isinstance(sys_blocks, list) and sys_blocks:
        return str(sys_blocks[-1].get("type", "no-type"))
    return "absent"


class TestBodyHasCacheControl:
    def test_no_cache_control_returns_false(self) -> None:
        body = {
            "system": [{"type": "text", "text": "be brief"}],
            "messages": [{"role": "user", "content": [{"type": "text", "text": "hi"}]}],
        }
        assert _body_has_cache_control(body) is False

    def test_cache_control_on_system_returns_true(self) -> None:
        body = {
            "system": [
                {
                    "type": "text",
                    "text": "be brief",
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            "messages": [],
        }
        assert _body_has_cache_control(body) is True

    def test_cache_control_on_tools_returns_true(self) -> None:
        body = {
            "tools": [
                {
                    "name": "foo",
                    "input_schema": {},
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            "messages": [],
        }
        assert _body_has_cache_control(body) is True

    def test_cache_control_on_user_block_returns_true(self) -> None:
        body = {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "hi",
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                }
            ],
        }
        assert _body_has_cache_control(body) is True


class TestInjectCacheControl:
    def test_string_system_prompt_not_converted(self) -> None:
        """String system prompt is left as-is; only list content gets cache_control."""
        body = {"system": "be brief", "messages": [{"role": "user", "content": "hi"}]}
        inject_cache_control(body)
        # String system prompt should not be converted to list
        assert body["system"] == "be brief"

    def test_injects_on_list_system_prompt(self) -> None:
        body = {
            "system": [{"type": "text", "text": "be brief"}],
            "messages": [{"role": "user", "content": "hi"}],
        }
        inject_cache_control(body)
        assert body["system"][-1]["cache_control"] == {"type": "ephemeral"}

    def test_injects_on_tools(self) -> None:
        body = {
            "tools": [
                {"name": "foo", "input_schema": {"type": "object"}},
                {"name": "bar", "input_schema": {"type": "object"}},
            ],
            "messages": [{"role": "user", "content": "hi"}],
        }
        inject_cache_control(body)
        assert "cache_control" not in body["tools"][0]
        assert body["tools"][1]["cache_control"] == {"type": "ephemeral"}

    def test_injects_on_first_user_message_content_list(self) -> None:
        body = {
            "messages": [
                {"role": "user", "content": [{"type": "text", "text": "hello"}]},
                {"role": "assistant", "content": "ok"},
            ]
        }
        inject_cache_control(body)
        assert body["messages"][0]["content"][-1]["cache_control"] == {
            "type": "ephemeral"
        }

    def test_skips_when_already_present(self) -> None:
        body = {
            "system": [
                {"type": "text", "text": "s", "cache_control": {"type": "ephemeral"}}
            ],
            "messages": [{"role": "user", "content": "hi"}],
        }
        inject_cache_control(body)
        # System should only have one cache_control object, not two.
        sys_blocks = body["system"]
        assert len(sys_blocks) == 1
        assert sys_blocks[0]["cache_control"] == {"type": "ephemeral"}

    def test_no_system_does_not_crash(self) -> None:
        body: dict = {"messages": [{"role": "user", "content": "hi"}]}
        inject_cache_control(body)
        assert "system" not in body or body["system"] is None

    def test_no_messages_does_not_crash(self) -> None:
        body = {"system": "be brief", "messages": []}
        inject_cache_control(body)
        # String system is left as-is (no conversion to list w/ cache_control)
        assert body["system"] == "be brief"

    def test_empty_tools_does_not_crash(self) -> None:
        body = {"tools": [], "messages": [{"role": "user", "content": "hi"}]}
        inject_cache_control(body)
        assert body["tools"] == []

    def test_no_body_does_not_crash(self) -> None:
        body: dict = {}
        inject_cache_control(body)
        assert body == {}

    def test_string_user_content_not_converted(self) -> None:
        """String user content is left as-is; cache_control only injects on list content."""
        body = {"messages": [{"role": "user", "content": "plain text"}]}
        inject_cache_control(body)
        # String content should not be converted to list
        assert body["messages"][0]["content"] == "plain text"
        # No cache_control injected since we don't convert strings
        assert "cache_control" not in body["messages"][0]

    def test_skips_assistant_message_user_content(self) -> None:
        body = {
            "messages": [
                {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "response"}],
                },
                {"role": "user", "content": [{"type": "text", "text": "follow up"}]},
            ]
        }
        inject_cache_control(body)
        # Should inject on the user message, not assistant
        assert body["messages"][1]["content"][-1]["cache_control"] == {
            "type": "ephemeral"
        }
