"""In-memory LRU response cache with request-keyed lookup."""

from __future__ import annotations

import hashlib
import json
from collections import OrderedDict
from collections.abc import AsyncIterator
from typing import Any


def _stable_hash(obj: Any) -> str:
    """Return a stable SHA-256 hex digest for a JSON-serializable object."""
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:16]


def cache_key_for_request(
    *,
    model: str,
    system: Any,
    messages: list[Any],
    tools: Any,
    stream: bool,
) -> str:
    """Derive a cache key from the canonical parts of a messages request."""
    system_digest = _stable_hash(system) if system else ""
    msgs_digest = _stable_hash(messages)
    tools_digest = _stable_hash(tools) if tools else ""
    raw = f"{model}::s:{system_digest}::m:{msgs_digest}::t:{tools_digest}::stream:{stream}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


class PromptCache:
    """In-memory LRU response cache for exact-match prompt deduplication."""

    def __init__(self, max_entries: int = 256, ttl_seconds: int = 300) -> None:
        self._max_entries = max_entries
        self._ttl_seconds = ttl_seconds
        self._data: OrderedDict[str, _CachedEntry] = OrderedDict()
        self._hit_count = 0
        self._miss_count = 0

    @property
    def max_entries(self) -> int:
        return self._max_entries

    @property
    def ttl_seconds(self) -> int:
        return self._ttl_seconds

    @property
    def size(self) -> int:
        return len(self._data)

    @property
    def hit_count(self) -> int:
        return self._hit_count

    @property
    def miss_count(self) -> int:
        return self._miss_count

    def get(self, key: str) -> list[str] | None:
        """Return cached SSE lines for *key*, or ``None`` on miss/expiry."""
        if key not in self._data:
            self._miss_count += 1
            return None
        entry = self._data[key]
        if entry.is_expired(self._ttl_seconds):
            del self._data[key]
            self._miss_count += 1
            return None
        self._data.move_to_end(key)
        self._hit_count += 1
        return entry.sse_lines

    def set(self, key: str, sse_lines: list[str]) -> None:
        """Store *sse_lines* under *key*, evicting oldest if at capacity."""
        if key in self._data:
            self._data.move_to_end(key)
            self._data[key] = _CachedEntry(sse_lines)
            return
        if len(self._data) >= self._max_entries:
            self._data.popitem(last=False)
        self._data[key] = _CachedEntry(sse_lines)

    def clear(self) -> None:
        """Evict all entries and reset counters."""
        self._data.clear()
        self._hit_count = 0
        self._miss_count = 0

    def stats(self) -> dict[str, Any]:
        """Return cache statistics."""
        total = self._hit_count + self._miss_count
        return {
            "size": self.size,
            "max_entries": self._max_entries,
            "ttl_seconds": self._ttl_seconds,
            "hit_count": self._hit_count,
            "miss_count": self._miss_count,
            "hit_rate": round(self._hit_count / total, 4) if total > 0 else 0.0,
        }


class _CachedEntry:
    __slots__ = ("created_at", "sse_lines")

    def __init__(self, sse_lines: list[str]) -> None:
        import time

        self.sse_lines = sse_lines
        self.created_at = time.monotonic()

    def is_expired(self, ttl: int) -> bool:
        import time

        return ttl > 0 and (time.monotonic() - self.created_at) > ttl


async def make_cached_stream(
    sse_lines: list[str],
) -> AsyncIterator[str]:
    """Yield pre-recorded SSE lines from cache (instant replay)."""
    for line in sse_lines:
        yield line


class CacheCollector:
    """Async iterator wrapper that records yielded items for caching."""

    def __init__(self, inner: AsyncIterator[str]) -> None:
        self._inner = inner
        self.collected: list[str] = []
        self.final_exception: BaseException | None = None

    def __aiter__(self) -> AsyncIterator[str]:
        return self._aiter()

    async def _aiter(self) -> AsyncIterator[str]:
        try:
            async for chunk in self._inner:
                self.collected.append(chunk)
                yield chunk
        except BaseException as exc:
            self.final_exception = exc
            raise
