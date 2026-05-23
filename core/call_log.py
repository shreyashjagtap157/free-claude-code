"""In-memory ring buffer of recent provider API calls for Admin UI visibility."""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from threading import Lock
from typing import Any

MAX_CALLS = 200
_RECORDS: list[dict[str, Any]] = []
_LOCK = Lock()


@dataclass(slots=True)
class ApiCallRecord:
    provider: str
    model: str
    status: str
    duration_s: float
    input_tokens: int = 0
    output_tokens: int = 0
    error: str = ""
    timestamp: float = field(default_factory=time.time)


def push(record: ApiCallRecord) -> None:
    with _LOCK:
        _RECORDS.append(
            {
                "provider": record.provider,
                "model": record.model,
                "status": record.status,
                "duration_s": round(record.duration_s, 3),
                "input_tokens": record.input_tokens,
                "output_tokens": record.output_tokens,
                "error": record.error,
                "timestamp": record.timestamp,
            }
        )
        while len(_RECORDS) > MAX_CALLS:
            _RECORDS.pop(0)


def recent() -> Sequence[dict[str, Any]]:
    with _LOCK:
        return list(_RECORDS)
