"""Tests for the session registry and per-instance model override."""

from __future__ import annotations

import time

from core.session_registry import SessionRegistry


class TestSessionRegistry:
    def test_register_returns_session_id(self) -> None:
        reg = SessionRegistry()
        sid = reg.register(pid=1234, model_override="openai/gpt-4")
        assert sid.startswith("fcc-")
        assert len(sid) == 12  # "fcc-" + 8 hex chars

    def test_register_stores_metadata(self) -> None:
        reg = SessionRegistry()
        sid = reg.register(pid=1234, model_override="openai/gpt-4", port=8082)
        meta = reg.get(sid)
        assert meta is not None
        assert meta.pid == 1234
        assert meta.model_override == "openai/gpt-4"
        assert meta.port == 8082
        assert meta.status == "active"

    def test_heartbeat_updates_timestamp(self) -> None:
        reg = SessionRegistry()
        sid = reg.register()
        meta = reg.get(sid)
        assert meta is not None
        old_heartbeat = meta.last_heartbeat
        time.sleep(0.01)
        assert reg.heartbeat(sid) is True
        assert meta.last_heartbeat > old_heartbeat

    def test_heartbeat_returns_false_for_unknown(self) -> None:
        reg = SessionRegistry()
        assert reg.heartbeat("nonexistent") is False

    def test_unregister_removes_session(self) -> None:
        reg = SessionRegistry()
        sid = reg.register()
        assert reg.unregister(sid) is True
        assert reg.get(sid) is None

    def test_unregister_returns_false_for_unknown(self) -> None:
        reg = SessionRegistry()
        assert reg.unregister("nonexistent") is False

    def test_list_sessions(self) -> None:
        reg = SessionRegistry()
        reg.register(pid=1)
        reg.register(pid=2)
        reg.register(pid=3)
        sessions = reg.list_sessions()
        assert len(sessions) == 3
        pids = {s.pid for s in sessions}
        assert pids == {1, 2, 3}

    def test_stop_session(self) -> None:
        reg = SessionRegistry()
        sid = reg.register()
        assert reg.stop_session(sid) is True
        meta = reg.get(sid)
        assert meta is not None
        assert meta.status == "stopped"

    def test_stop_session_returns_false_for_unknown(self) -> None:
        reg = SessionRegistry()
        assert reg.stop_session("nonexistent") is False

    def test_get_stats(self) -> None:
        reg = SessionRegistry()
        reg.register()
        sid = reg.register()
        reg.register()
        reg.stop_session(sid)
        stats = reg.get_stats()
        assert stats["total_sessions"] == 3
        assert stats["active_sessions"] == 2
        assert stats["stopped_sessions"] == 1

    def test_stale_sessions_cleaned_up(self) -> None:
        reg = SessionRegistry(heartbeat_timeout=0.01)
        sid = reg.register()
        time.sleep(0.02)
        sessions = reg.list_sessions()
        assert len(sessions) == 0
        assert reg.get(sid) is None

    def test_active_session_not_cleaned(self) -> None:
        reg = SessionRegistry(heartbeat_timeout=10.0)
        sid = reg.register()
        reg.heartbeat(sid)
        sessions = reg.list_sessions()
        assert len(sessions) == 1

    def test_multiple_registries_are_independent(self) -> None:
        reg1 = SessionRegistry()
        reg2 = SessionRegistry()
        sid1 = reg1.register(pid=1)
        sid2 = reg2.register(pid=2)
        assert len(reg1.list_sessions()) == 1
        assert len(reg2.list_sessions()) == 1
        assert reg1.get(sid2) is None
        assert reg2.get(sid1) is None


class TestModelOverride:
    def test_model_override_takes_precedence(self, monkeypatch) -> None:
        from config.settings import Settings

        monkeypatch.setitem(Settings.model_config, "env_file", ())
        settings = Settings(
            model="nvidia_nim/minimaxai/minimax-m2.7",
            model_override="openai/gpt-4o",
        )
        resolved = settings.resolve_model("claude-sonnet-4-20250514")
        assert resolved == "openai/gpt-4o"

    def test_no_model_override_uses_normal_resolution(self, monkeypatch) -> None:
        from config.settings import Settings

        monkeypatch.setitem(Settings.model_config, "env_file", ())
        monkeypatch.setenv("MODEL", "nvidia_nim/minimaxai/minimax-m2.7")
        monkeypatch.setenv("MODEL_SONNET", "open_router/anthropic/claude-sonnet-4")
        settings = Settings()
        resolved = settings.resolve_model("claude-sonnet-4-20250514")
        assert resolved == "open_router/anthropic/claude-sonnet-4"

    def test_model_override_none_falls_through(self, monkeypatch) -> None:
        from config.settings import Settings

        monkeypatch.setitem(Settings.model_config, "env_file", ())
        settings = Settings(
            model="nvidia_nim/minimaxai/minimax-m2.7",
            model_override=None,
        )
        resolved = settings.resolve_model("claude-haiku-4-20250514")
        assert resolved == "nvidia_nim/minimaxai/minimax-m2.7"

    def test_model_copy_with_override(self, monkeypatch) -> None:
        from config.settings import Settings

        monkeypatch.setitem(Settings.model_config, "env_file", ())
        settings = Settings(model="nvidia_nim/minimaxai/minimax-m2.7")
        overridden = settings.model_copy(update={"model_override": "openai/gpt-4o"})
        assert overridden.model_override == "openai/gpt-4o"
        assert settings.model_override is None
        assert overridden.model == settings.model


class TestSessionRegistryAdminAPI:
    def test_list_sessions_endpoint(self) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from core.session_registry import get_session_registry

        app = FastAPI()
        registry = get_session_registry()
        sid = registry.register(pid=999, model_override="test/model")

        @app.get("/admin/api/sessions")
        async def list_sessions():
            sessions = registry.list_sessions()
            return {
                "sessions": [
                    {
                        "session_id": s.session_id,
                        "pid": s.pid,
                        "model_override": s.model_override,
                        "status": s.status,
                    }
                    for s in sessions
                ],
                **registry.get_stats(),
            }

        client = TestClient(app)
        response = client.get("/admin/api/sessions")
        assert response.status_code == 200
        data = response.json()
        assert data["total_sessions"] >= 1
        session_ids = [s["session_id"] for s in data["sessions"]]
        assert sid in session_ids
        registry.unregister(sid)

    def test_stop_session_endpoint(self) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from core.session_registry import get_session_registry

        app = FastAPI()
        registry = get_session_registry()
        sid = registry.register()

        @app.post("/admin/api/sessions/{session_id}/stop")
        async def stop_session(session_id: str):
            if registry.stop_session(session_id):
                return {"ok": True}
            return {"ok": False}

        client = TestClient(app)
        response = client.post(f"/admin/api/sessions/{sid}/stop")
        assert response.status_code == 200
        assert response.json()["ok"] is True
        meta = registry.get(sid)
        assert meta is not None
        assert meta.status == "stopped"
        registry.unregister(sid)
