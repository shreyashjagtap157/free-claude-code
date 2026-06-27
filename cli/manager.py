"""
CLI Session Manager for Multi-Instance Claude CLI Support

Manages a pool of CLISession instances, each handling one conversation.
This enables true parallel processing where multiple conversations run
simultaneously in separate CLI processes.
"""

import asyncio
import contextlib
import time
import uuid

from loguru import logger

from .session import CLISession


class CLISessionManager:
    """
    Manages multiple CLISession instances for parallel conversation processing.

    Each new conversation gets its own CLISession with its own subprocess.
    Replies to existing conversations reuse the same CLISession instance.
    """

    def __init__(
        self,
        workspace_path: str,
        api_url: str,
        allowed_dirs: list[str] | None = None,
        plans_directory: str | None = None,
        claude_bin: str = "claude",
        *,
        log_raw_cli_diagnostics: bool = False,
        log_messaging_error_details: bool = False,
        auto_compact_enabled: bool = True,
        auto_compact_threshold: float = 0.75,
        auto_compact_context_window: int = 200_000,
        supports_vision: bool | None = None,
        supports_tools: bool | None = None,
        max_output_tokens: int | None = None,
        max_sessions: int = 20,
        session_ttl: float = 3600.0,
        reaper_interval: float = 300.0,
    ):
        """
        Initialize the session manager.

        Args:
            workspace_path: Working directory for CLI processes
            api_url: API URL for the proxy
            allowed_dirs: Directories the CLI is allowed to access
            plans_directory: Directory for Claude Code CLI plan files (passed via --settings)
            max_sessions: Maximum concurrent sessions (default 20)
            session_ttl: Max idle time in seconds before auto-removal (default 1 hour)
            reaper_interval: How often to check for stale sessions (default 5 min)
        """
        self.workspace = workspace_path
        self.api_url = api_url
        self.allowed_dirs = allowed_dirs or []
        self.plans_directory = plans_directory
        self.claude_bin = claude_bin
        self._max_sessions = max_sessions
        self._session_ttl = session_ttl
        self._reaper_interval = reaper_interval
        self._log_raw_cli_diagnostics = log_raw_cli_diagnostics
        self._log_messaging_error_details = log_messaging_error_details
        self._auto_compact_enabled = auto_compact_enabled
        self._auto_compact_threshold = auto_compact_threshold
        self._auto_compact_context_window = auto_compact_context_window
        self._supports_vision: bool | None = supports_vision
        self._supports_tools: bool | None = supports_tools
        self._max_output_tokens: int | None = max_output_tokens

        self._sessions: dict[str, CLISession] = {}
        self._pending_sessions: dict[str, CLISession] = {}
        self._temp_to_real: dict[str, str] = {}
        self._real_to_temp: dict[str, str] = {}
        self._last_active: dict[str, float] = {}
        self._lock = asyncio.Lock()
        self._reaper_task: asyncio.Task | None = None

    async def _reaper_loop(self) -> None:
        """Periodically reap idle sessions that have exceeded the TTL."""
        while True:
            await asyncio.sleep(self._reaper_interval)
            try:
                await self._reap_idle_sessions()
            except Exception as e:
                logger.error("Session reaper error: exc_type={}", type(e).__name__)

    async def _reap_idle_sessions(self) -> None:
        """Remove sessions that have been idle beyond session_ttl."""
        now = time.monotonic()
        async with self._lock:
            stale_real: list[str] = []
            for sid, last_active in list(self._last_active.items()):
                if sid not in self._sessions:
                    continue
                if self._sessions[sid].is_busy:
                    continue
                idle_time = now - last_active
                if idle_time >= self._session_ttl:
                    stale_real.append(sid)

            stale_pending = [
                sid
                for sid in list(self._pending_sessions)
                if not self._pending_sessions[sid].is_busy
            ]

        for sid in stale_real:
            await self.remove_session(sid)
            logger.info("Reaped idle session: {} (idle > {}s)", sid, self._session_ttl)

        for sid in stale_pending:
            async with self._lock:
                if sid in self._pending_sessions:
                    session = self._pending_sessions.pop(sid)
                    await session.stop()
                    self._last_active.pop(sid, None)
                    logger.info("Reaped stale pending session: {}", sid)

    def start_reaper(self) -> None:
        """Start the background idle session reaper task."""
        if self._reaper_task is None or self._reaper_task.done():
            self._reaper_task = asyncio.create_task(self._reaper_loop())
            logger.debug(
                "Session reaper started (ttl={}s, interval={}s)",
                self._session_ttl,
                self._reaper_interval,
            )

    async def stop_reaper(self) -> None:
        """Stop the background idle session reaper task."""
        if self._reaper_task is not None and not self._reaper_task.done():
            self._reaper_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._reaper_task
            self._reaper_task = None
            logger.debug("Session reaper stopped")

    async def get_or_create_session(
        self, session_id: str | None = None
    ) -> tuple[CLISession, str, bool]:
        """
        Get an existing session or create a new one.

        Returns:
            Tuple of (CLISession instance, session_id, is_new_session)
        """
        async with self._lock:
            if session_id:
                lookup_id = self._temp_to_real.get(session_id, session_id)

                if lookup_id in self._sessions:
                    self._last_active[lookup_id] = time.monotonic()
                    return self._sessions[lookup_id], lookup_id, False
                if lookup_id in self._pending_sessions:
                    return self._pending_sessions[lookup_id], lookup_id, False

            # Enforce max_sessions limit before creating a new one
            total = len(self._sessions) + len(self._pending_sessions)
            if total >= self._max_sessions:
                raise RuntimeError(
                    f"Maximum concurrent sessions ({self._max_sessions}) reached. "
                    f"Active: {len(self._sessions)}, Pending: {len(self._pending_sessions)}. "
                    "Wait for an existing session to complete or increase max_sessions."
                )

            temp_id = session_id if session_id else f"pending_{uuid.uuid4().hex[:8]}"

            new_session = CLISession(
                workspace_path=self.workspace,
                api_url=self.api_url,
                allowed_dirs=self.allowed_dirs,
                plans_directory=self.plans_directory,
                claude_bin=self.claude_bin,
                log_raw_cli_diagnostics=self._log_raw_cli_diagnostics,
                auto_compact_enabled=self._auto_compact_enabled,
                auto_compact_threshold=self._auto_compact_threshold,
                context_window=self._auto_compact_context_window,
                supports_vision=self._supports_vision,
                supports_tools=self._supports_tools,
                max_output_tokens=self._max_output_tokens,
            )
            self._pending_sessions[temp_id] = new_session
            self._last_active[temp_id] = time.monotonic()

            return new_session, temp_id, True

    async def register_real_session_id(
        self, temp_id: str, real_session_id: str
    ) -> bool:
        """Register the real session ID from CLI output."""
        async with self._lock:
            if temp_id not in self._pending_sessions:
                logger.warning(f"Temp session {temp_id} not found")
                return False

            session = self._pending_sessions.pop(temp_id)
            self._sessions[real_session_id] = session
            self._temp_to_real[temp_id] = real_session_id
            self._real_to_temp[real_session_id] = temp_id
            active_time = self._last_active.pop(temp_id, time.monotonic())
            self._last_active[real_session_id] = active_time

            logger.info(f"Registered session: {temp_id} -> {real_session_id}")
            return True

    async def remove_session(self, session_id: str) -> bool:
        """Remove a session from the manager."""
        async with self._lock:
            if session_id in self._pending_sessions:
                session = self._pending_sessions.pop(session_id)
                self._last_active.pop(session_id, None)
                await session.stop()
                return True

            if session_id in self._sessions:
                session = self._sessions.pop(session_id)
                self._last_active.pop(session_id, None)
                await session.stop()
                temp_id = self._real_to_temp.pop(session_id, None)
                if temp_id is not None:
                    self._temp_to_real.pop(temp_id, None)
                return True

            return False

    async def stop_all(self):
        """Stop all sessions concurrently."""
        await self.stop_reaper()
        async with self._lock:
            all_sessions = list(self._sessions.values()) + list(
                self._pending_sessions.values()
            )
            results = await asyncio.gather(
                *[session.stop() for session in all_sessions],
                return_exceptions=True,
            )
            for _, result in zip(all_sessions, results, strict=False):
                if isinstance(result, Exception):
                    if self._log_messaging_error_details:
                        logger.error(
                            "Error stopping session: {}: {}",
                            type(result).__name__,
                            result,
                        )
                    else:
                        logger.error(
                            "Error stopping session: exc_type={}",
                            type(result).__name__,
                        )

            self._sessions.clear()
            self._pending_sessions.clear()
            self._temp_to_real.clear()
            self._real_to_temp.clear()
            self._last_active.clear()
            logger.info("All sessions stopped")

    def get_stats(self) -> dict:
        """Get session statistics."""
        return {
            "active_sessions": len(self._sessions),
            "pending_sessions": len(self._pending_sessions),
            "busy_count": sum(1 for s in self._sessions.values() if s.is_busy),
        }
