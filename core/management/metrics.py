"""SOTA Metric Tracking and Resource Monitoring.
Provides real-time stats for tokens, lines, and hardware usage.
"""

from __future__ import annotations

import threading
import time
from typing import Any

import psutil


class SessionTracker:
    def __init__(self):
        self.total_in_tokens = 0
        self.total_out_tokens = 0
        self.total_lines_added = 0
        self.total_lines_removed = 0

    def update_request_metrics(self, in_t: int, out_t: int, added: int, removed: int):
        self.total_in_tokens += in_t
        self.total_out_tokens += out_t
        self.total_lines_added += added
        self.total_lines_removed += removed


class HardwareMonitor:
    def __init__(self):
        self.stats = {
            "cpu_percent": 0.0,
            "ram_percent": 0.0,
            "vram_used": 0,
            "vram_total": 0,
            "gpu_percent": 0.0,
        }
        self._running = False
        self._thread: threading.Thread | None = None

    def _poll_resources(self):
        while self._running:
            # CPU and RAM
            self.stats["cpu_percent"] = psutil.cpu_percent(interval=None)
            self.stats["ram_percent"] = psutil.virtual_memory().percent

            # GPU implementation (simplified for cross-platform)
            # In SOTA, we would use nvidia-smi or pycuda
            self.stats["gpu_percent"] = 0.0

            time.sleep(1)

    def start(self):
        if not self._running:
            self._running = True
            self._thread = threading.Thread(target=self._poll_resources, daemon=True)
            self._thread.start()

    def stop(self):
        self._running = False

    def get_current_stats(self) -> dict[str, Any]:
        return self.stats
