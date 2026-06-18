"""Session registry for tracking connected fcc-claude instances.

Provides server-side awareness of connected CLI instances, enabling
multi-tenant workflows and admin visibility.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from loguru import logger


@dataclass
class SessionMeta:
    """Metadata for a connected fcc-claude instance."""

    session_id: str
    created_at: float
    last_heartbeat: float
    pid: int | None = None
    model_override: str | None = None
    port: int | None = None
    status: str = "active"
    metadata: dict[str, Any] = field(default_factory=dict)


class SessionRegistry:
    """Server-side registry for tracking connected fcc-claude instances.

    Each fcc-claude instance registers itself on startup, sends periodic
    heartbeats, and unregisters on shutdown. The admin API uses this
    to provide visibility into connected instances.
    """

    def __init__(self, *, heartbeat_timeout: float = 60.0) -> None:
        self._sessions: dict[str, SessionMeta] = {}
        self._heartbeat_timeout = heartbeat_timeout

    def register(
        self,
        *,
        pid: int | None = None,
        model_override: str | None = None,
        port: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Register a new fcc-claude instance. Returns the session ID."""
        session_id = f"fcc-{uuid.uuid4().hex[:8]}"
        now = time.time()
        self._sessions[session_id] = SessionMeta(
            session_id=session_id,
            created_at=now,
            last_heartbeat=now,
            pid=pid,
            model_override=model_override,
            port=port,
            metadata=metadata or {},
        )
        logger.info(
            "SESSION_REGISTRY: registered session={} pid={} model={}",
            session_id,
            pid,
            model_override,
        )
        return session_id

    def heartbeat(self, session_id: str) -> bool:
        """Update the heartbeat timestamp for a session. Returns False if not found."""
        session = self._sessions.get(session_id)
        if session is None:
            return False
        session.last_heartbeat = time.time()
        return True

    def unregister(self, session_id: str) -> bool:
        """Unregister a session. Returns False if not found."""
        removed = self._sessions.pop(session_id, None)
        if removed is not None:
            logger.info("SESSION_REGISTRY: unregistered session={}", session_id)
            return True
        return False

    def get(self, session_id: str) -> SessionMeta | None:
        """Get session metadata by ID."""
        return self._sessions.get(session_id)

    def list_sessions(self) -> list[SessionMeta]:
        """List all registered sessions, cleaning up stale ones."""
        self._cleanup_stale()
        return list(self._sessions.values())

    def stop_session(self, session_id: str) -> bool:
        """Mark a session as stopped."""
        session = self._sessions.get(session_id)
        if session is None:
            return False
        session.status = "stopped"
        logger.info("SESSION_REGISTRY: stopped session={}", session_id)
        return True

    def get_stats(self) -> dict[str, Any]:
        """Get registry statistics."""
        self._cleanup_stale()
        active = [s for s in self._sessions.values() if s.status == "active"]
        return {
            "total_sessions": len(self._sessions),
            "active_sessions": len(active),
            "stopped_sessions": len(self._sessions) - len(active),
        }

    def _cleanup_stale(self) -> None:
        """Remove sessions that haven't sent a heartbeat within timeout."""
        now = time.time()
        stale = [
            sid
            for sid, meta in self._sessions.items()
            if now - meta.last_heartbeat > self._heartbeat_timeout
        ]
        for sid in stale:
            logger.info("SESSION_REGISTRY: removing stale session={}", sid)
            self._sessions.pop(sid)


_registry: SessionRegistry | None = None


def get_session_registry() -> SessionRegistry:
    """Get the global session registry singleton."""
    global _registry
    if _registry is None:
        _registry = SessionRegistry()
    return _registry
