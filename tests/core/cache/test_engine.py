"""Tests for the enterprise prompt response cache."""

from __future__ import annotations

import pytest

from core.cache.engine import (
    CacheCollector,
    PromptCache,
    cache_key_for_request,
    make_cached_stream,
)


class TestCacheKeyForRequest:
    def test_same_request_produces_same_key(self) -> None:
        msgs = [{"role": "user", "content": "hello"}]
        k1 = cache_key_for_request(
            model="m", system=None, messages=msgs, tools=None, stream=True
        )
        k2 = cache_key_for_request(
            model="m", system=None, messages=msgs, tools=None, stream=True
        )
        assert k1 == k2
        assert len(k1) == 32

    def test_different_model_produces_different_key(self) -> None:
        msgs = [{"role": "user", "content": "hello"}]
        k1 = cache_key_for_request(
            model="a", system=None, messages=msgs, tools=None, stream=True
        )
        k2 = cache_key_for_request(
            model="b", system=None, messages=msgs, tools=None, stream=True
        )
        assert k1 != k2

    def test_different_messages_produces_different_key(self) -> None:
        msgs1 = [{"role": "user", "content": "hello"}]
        msgs2 = [{"role": "user", "content": "world"}]
        k1 = cache_key_for_request(
            model="m", system=None, messages=msgs1, tools=None, stream=True
        )
        k2 = cache_key_for_request(
            model="m", system=None, messages=msgs2, tools=None, stream=True
        )
        assert k1 != k2

    def test_stream_flag_affects_key(self) -> None:
        msgs = [{"role": "user", "content": "hello"}]
        k1 = cache_key_for_request(
            model="m", system=None, messages=msgs, tools=None, stream=True
        )
        k2 = cache_key_for_request(
            model="m", system=None, messages=msgs, tools=None, stream=False
        )
        assert k1 != k2

    def test_system_affects_key(self) -> None:
        msgs = [{"role": "user", "content": "hello"}]
        k1 = cache_key_for_request(
            model="m", system="sys1", messages=msgs, tools=None, stream=True
        )
        k2 = cache_key_for_request(
            model="m", system="sys2", messages=msgs, tools=None, stream=True
        )
        assert k1 != k2

    def test_tools_affects_key(self) -> None:
        msgs = [{"role": "user", "content": "hello"}]
        tools1 = [{"name": "foo", "input_schema": {"type": "object"}}]
        tools2 = [{"name": "bar", "input_schema": {"type": "object"}}]
        k1 = cache_key_for_request(
            model="m", system=None, messages=msgs, tools=tools1, stream=True
        )
        k2 = cache_key_for_request(
            model="m", system=None, messages=msgs, tools=tools2, stream=True
        )
        assert k1 != k2


class TestPromptCache:
    def test_get_set_round_trip(self) -> None:
        cache = PromptCache(max_entries=10, ttl_seconds=0)
        lines = [
            "event: message_start\ndata: {}\n\n",
            "event: message_stop\ndata: {}\n\n",
        ]
        cache.set("key1", lines)
        assert cache.get("key1") == lines
        assert cache.size == 1

    def test_miss_returns_none(self) -> None:
        cache = PromptCache(max_entries=10, ttl_seconds=0)
        assert cache.get("nonexistent") is None
        assert cache.miss_count == 1

    def test_lru_eviction(self) -> None:
        cache = PromptCache(max_entries=2, ttl_seconds=0)
        cache.set("a", ["a1"])
        cache.set("b", ["b1"])
        cache.set("c", ["c1"])
        assert cache.size == 2
        assert cache.get("a") is None
        assert cache.get("c") is not None

    def test_lru_recent_access_preserves_entry(self) -> None:
        cache = PromptCache(max_entries=2, ttl_seconds=0)
        cache.set("a", ["a1"])
        cache.set("b", ["b1"])
        cache.get("a")  # Access a, making b the LRU
        cache.set("c", ["c1"])
        assert cache.get("a") is not None
        assert cache.get("b") is None

    def test_clear_resets_everything(self) -> None:
        cache = PromptCache(max_entries=10, ttl_seconds=0)
        cache.set("a", ["a1"])
        cache.get("a")
        cache.set("b", ["b1"])
        cache.get("b")
        cache.clear()
        assert cache.size == 0
        assert cache.hit_count == 0
        assert cache.miss_count == 0

    def test_stats(self) -> None:
        cache = PromptCache(max_entries=10, ttl_seconds=0)
        cache.set("a", ["a1"])
        cache.get("a")
        cache.get("b")
        stats = cache.stats()
        assert stats["size"] == 1
        assert stats["hit_count"] == 1
        assert stats["miss_count"] == 1
        assert stats["hit_rate"] == 0.5
        assert stats["max_entries"] == 10

    def test_zero_stats_on_empty_cache(self) -> None:
        cache = PromptCache(max_entries=10, ttl_seconds=0)
        stats = cache.stats()
        assert stats["hit_rate"] == 0.0

    def test_key_update_does_not_change_eviction_order(self) -> None:
        cache = PromptCache(max_entries=2, ttl_seconds=0)
        cache.set("a", ["a1"])
        cache.set("b", ["b2"])
        cache.set("a", ["a2"])  # Update a, moves to end
        cache.set("c", ["c1"])  # Evicts b (oldest)
        assert cache.get("b") is None
        assert cache.get("a") == ["a2"]


class TestMakeCachedStream:
    @pytest.mark.asyncio
    async def test_yields_all_lines_in_order(self) -> None:
        lines = ["line1\n", "line2\n", "line3\n"]
        collected = [chunk async for chunk in make_cached_stream(lines)]
        assert collected == lines

    @pytest.mark.asyncio
    async def test_empty_list_yields_nothing(self) -> None:
        collected = [chunk async for chunk in make_cached_stream([])]
        assert collected == []


class TestCacheCollector:
    @pytest.mark.asyncio
    async def test_collects_all_items(self) -> None:
        async def source():
            yield "a"
            yield "b"

        collector = CacheCollector(source())
        collected = [chunk async for chunk in collector]
        assert collected == ["a", "b"]
        assert collector.collected == ["a", "b"]
        assert collector.final_exception is None

    @pytest.mark.asyncio
    async def test_completed_without_exception(self) -> None:
        async def source():
            yield "only"

        collector = CacheCollector(source())
        async for _ in collector:
            pass
        assert collector.collected == ["only"]
        assert collector.final_exception is None

    @pytest.mark.asyncio
    async def test_empty_source(self) -> None:
        async def source():
            if False:
                yield ""

        collector = CacheCollector(source())
        collected = [chunk async for chunk in collector]
        assert collected == []
        assert collector.collected == []
        assert collector.final_exception is None
