"""CLI entry points for the installed package."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import uvicorn

from api.admin_urls import local_proxy_root_url
from api.app import GracefulLifespanApp, create_app
from cli.process_registry import (
    kill_all_best_effort,
    kill_pid_tree_best_effort,
    register_pid,
    unregister_pid,
)
from config.settings import Settings, get_settings

PROXY_PREFLIGHT_PATH = "/health"
PROXY_PREFLIGHT_TIMEOUT_SECONDS = 1.5
SERVER_GRACEFUL_SHUTDOWN_SECONDS = 5


def _load_env_template() -> str:
    """Load the canonical root env template from package resources or source."""
    import importlib.resources

    packaged = importlib.resources.files("cli").joinpath("env.example")
    if packaged.is_file():
        return packaged.read_text("utf-8")

    source_template = Path(__file__).resolve().parents[1] / ".env.example"
    if source_template.is_file():
        return source_template.read_text(encoding="utf-8")

    raise FileNotFoundError("Could not find bundled or source .env.example template.")


def serve() -> None:
    """Start the FastAPI server (registered as `fcc-server` script)."""
    try:
        try:
            while True:
                settings = get_settings()
                if not _run_supervised_server(settings):
                    return
                get_settings.cache_clear()
        except KeyboardInterrupt:
            return
    finally:
        kill_all_best_effort()


def _run_supervised_server(settings: Settings) -> bool:
    """Run one uvicorn server instance; return whether admin requested restart."""

    restart_requested = False
    server_holder: dict[str, uvicorn.Server] = {}

    def request_restart() -> None:
        nonlocal restart_requested
        restart_requested = True
        if server := server_holder.get("server"):
            server.should_exit = True

    app = create_app(lifespan_enabled=False)
    app.state.admin_restart_callback = request_restart
    asgi_app = GracefulLifespanApp(app)
    config = uvicorn.Config(
        asgi_app,
        host=settings.host,
        port=settings.port,
        log_level="info",
        access_log=False,
        timeout_graceful_shutdown=SERVER_GRACEFUL_SHUTDOWN_SECONDS,
    )
    server = uvicorn.Server(config)
    server_holder["server"] = server
    server.run()
    return restart_requested


def init() -> None:
    """Scaffold config at ~/.config/free-claude-code/.env (registered as `fcc-init`)."""
    config_dir = Path.home() / ".config" / "free-claude-code"
    env_file = config_dir / ".env"

    if env_file.exists():
        print(f"Config already exists at {env_file}")
        print("Delete it first if you want to reset to defaults.")
        return

    config_dir.mkdir(parents=True, exist_ok=True)
    template = _load_env_template()
    env_file.write_text(template, encoding="utf-8")
    print(f"Config created at {env_file}")
    print("Edit it to set your API keys and model preferences, then run: fcc-server")


def _claude_child_env(
    settings: Settings, base_env: Mapping[str, str]
) -> dict[str, str]:
    """Return a Claude Code environment that targets this proxy."""

    env = {
        key: value
        for key, value in base_env.items()
        if not key.startswith("ANTHROPIC_")
    }
    env["ANTHROPIC_BASE_URL"] = local_proxy_root_url(settings)
    env["CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY"] = "1"
    if token := settings.anthropic_auth_token.strip():
        env["ANTHROPIC_AUTH_TOKEN"] = token
    return env


def _preflight_proxy(proxy_root_url: str) -> str | None:
    """Return an error message when the local proxy health check is unreachable."""

    url = f"{proxy_root_url.rstrip('/')}{PROXY_PREFLIGHT_PATH}"
    request = Request(url, method="GET")
    try:
        with urlopen(request, timeout=PROXY_PREFLIGHT_TIMEOUT_SECONDS) as response:
            status_code = response.getcode()
    except HTTPError as exc:
        return f"returned HTTP {exc.code}"
    except URLError as exc:
        return str(exc.reason)
    except OSError as exc:
        return str(exc)

    if not 200 <= status_code < 300:
        return f"returned HTTP {status_code}"
    return None


def _allocate_dynamic_port(main_proxy_root_url: str) -> int:
    """Request a dynamic port from the main fcc-server."""
    import json

    url = f"{main_proxy_root_url.rstrip('/')}/admin/api/ports/allocate"
    request = Request(url, method="POST", data=b"{}")
    request.add_header("Content-Type", "application/json")
    try:
        with urlopen(request, timeout=5.0) as response:
            data = json.loads(response.read().decode("utf-8"))
            return int(data["port"])
    except Exception as exc:
        print(
            f"Failed to allocate dynamic port from main server at {main_proxy_root_url}: {exc}",
            file=sys.stderr,
        )
        print(
            "Please ensure the main fcc-server is running on the default port first.",
            file=sys.stderr,
        )
        raise SystemExit(1) from None


def launch_claude(argv: Sequence[str] | None = None) -> None:
    """Launch Claude Code with Free Claude Code proxy environment variables."""

    raw_args = list(sys.argv[1:] if argv is None else argv)

    # Extract --port override before forwarding remaining args to Claude CLI.
    port_override: int | str | None = None
    forwarded_args: list[str] = []
    i = 0
    while i < len(raw_args):
        if raw_args[i] == "--port" and i + 1 < len(raw_args):
            val = raw_args[i + 1]
            if val.lower() == "auto":
                port_override = "auto"
            else:
                try:
                    port_override = int(val)
                except ValueError:
                    print(
                        f"Invalid --port value: {val}",
                        file=sys.stderr,
                    )
                    raise SystemExit(1) from None
            i += 2
            continue
        if raw_args[i].startswith("--port="):
            val = raw_args[i].split("=", 1)[1]
            if val.lower() == "auto":
                port_override = "auto"
            else:
                try:
                    port_override = int(val)
                except ValueError:
                    print(
                        f"Invalid --port value: {raw_args[i]}",
                        file=sys.stderr,
                    )
                    raise SystemExit(1) from None
            i += 1
            continue
        forwarded_args.append(raw_args[i])
        i += 1

    # Check environment variable override
    env_port = os.environ.get("FCC_PORT")
    if env_port and env_port.lower() == "auto" and port_override is None:
        port_override = "auto"

    settings = get_settings()
    if port_override is not None:
        if port_override == "auto":
            # Target the main server URL to allocate a port
            main_url = local_proxy_root_url(settings)
            allocated_port = _allocate_dynamic_port(main_url)
            print(f"Auto-allocated dynamic port: {allocated_port}", file=sys.stderr)
            settings.port = allocated_port
        else:
            # Override settings port for this fcc-claude session.
            settings.port = int(port_override)

    proxy_root_url = local_proxy_root_url(settings)
    if error := _preflight_proxy(proxy_root_url):
        print(
            f"Free Claude Code proxy is not reachable at {proxy_root_url}: {error}",
            file=sys.stderr,
        )
        print("Start it in another terminal with: fcc-server", file=sys.stderr)
        if port_override is None:
            print(
                "Tip: Multiple instances can share one fcc-server. "
                "Or use FCC_PORT=<port> to run separate servers.",
                file=sys.stderr,
            )
        raise SystemExit(1)

    claude_command = shutil.which(settings.claude_cli_bin)
    if claude_command is None:
        print(
            f"Could not find Claude Code command: {settings.claude_cli_bin}",
            file=sys.stderr,
        )
        print(
            "Install Claude Code with: npm install -g @anthropic-ai/claude-code",
            file=sys.stderr,
        )
        raise SystemExit(127)

    command = [claude_command, *forwarded_args]
    env = _claude_child_env(settings, os.environ)
    process: subprocess.Popen[bytes] | None = None
    try:
        process = subprocess.Popen(command, env=env)
        if process.pid:
            register_pid(process.pid)
        return_code = process.wait()
    except FileNotFoundError:
        print(
            f"Could not find Claude Code command: {settings.claude_cli_bin}",
            file=sys.stderr,
        )
        print(
            "Install Claude Code with: npm install -g @anthropic-ai/claude-code",
            file=sys.stderr,
        )
        raise SystemExit(127) from None
    except KeyboardInterrupt:
        if process is not None and process.pid:
            kill_pid_tree_best_effort(process.pid)
            process.wait()
        raise
    finally:
        if process is not None and process.pid:
            unregister_pid(process.pid)

    raise SystemExit(return_code)
