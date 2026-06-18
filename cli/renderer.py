"""SOTA TUI Rendering Layer for the Sovereign CLI.
Handles rich colors, real-time metrics, and hardware dashboards.
"""

from __future__ import annotations

import time
from typing import Any

from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.text import Text


class SovereignRenderer:
    def __init__(self, session_tracker: Any, hw_monitor: Any):
        self.console = Console()
        self.tracker = session_tracker
        self.hw = hw_monitor
        self.start_time = None

    def render_header(self) -> Panel:
        """Render the SOTA top bar with session totals and hardware stats."""
        stats = self.hw.get_current_stats()

        # Session Metrics
        metrics = Text()
        metrics.append(f" {self.tracker.total_in_tokens} ↓ ", style="blue")
        metrics.append(f" {self.tracker.total_out_tokens} ↑ ", style="magenta")
        metrics.append(f" | {self.tracker.total_lines_added} + ", style="green")
        metrics.append(f" {self.tracker.total_lines_removed} - ", style="red")

        # Hardware Stats
        hw_stats = Text()
        hw_stats.append(f" CPU: {stats['cpu_percent']}% ", style="yellow")
        hw_stats.append(f" RAM: {stats['ram_percent']}% ", style="yellow")
        hw_stats.append(f" GPU: {stats['gpu_percent']}% ", style="cyan")

        return Panel(
            Columns([metrics, hw_stats], align="left"),
            style="bold white on blue",
            title="[bold]SOVEREIGN CONTROL PLANE[/bold]",
            border_style="bright_blue",
        )

    def render_event(self, event: dict[str, Any]) -> Text | None:
        """Transform a CLI event into a rich color-coded block."""
        etype = event.get("type")

        if etype == "text":
            content = event.get("content", "")
            # Check if it's thinking
            if "thinking" in event or "thought" in content.lower():
                return Text(content, style="dim italic grey50")
            return Text(content, style="white")

        if etype == "tool_use":
            tool_name = event.get("name", "tool")
            return Text(f"🛠️ Calling {tool_name}...", style="bold cyan")

        if etype == "tool_result":
            return Text("✅ Tool Response received", style="bold yellow")

        if etype == "error":
            return Text(f"❌ Error: {event.get('error', 'Unknown')}", style="bold red")

        return None

    def render_request_metrics(
        self, in_t: int, out_t: int, added: int, removed: int, duration: float
    ) -> Panel:
        """Render the per-request summary block."""
        text = Text()
        text.append(f" {in_t} ↓ ", style="blue")
        text.append(f" {out_t} ↑ ", style="magenta")
        text.append(f" | {added} + ", style="green")
        text.append(f" {removed} - ", style="red")
        text.append(f" | {duration:.2f}s", style="dim")

        return Panel(text, style="dim", border_style="grey37")

    def start_timer(self):
        self.start_time = time.time()

    def stop_timer(self) -> float:
        if not self.start_time:
            return 0.0
        duration = time.time() - self.start_time
        self.start_time = None
        return duration
