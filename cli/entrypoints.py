"""CLI entry points for the installed package."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from pathlib import Path

import httpx
import uvicorn
from loguru import logger

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
SERVER_GRACEFUL_SHUTDOWN_SECONDS = 2


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
    # Backoff parameters for crash-loop prevention
    backoff = 0.5  # start with half-second delay
    max_backoff = 30.0  # cap backoff at 30 seconds
    try:
        # Outer loop restarts the server after normal admin-requested restarts
        while True:
            settings = get_settings()
            try:
                # Run one server instance; returns True if admin requested restart
                restart_requested = _run_supervised_server(settings)
                # Normal exit (admin did not request restart) - exit the supervisor
                if not restart_requested:
                    return
                # Admin-requested restart: reset backoff and continue immediately
                backoff = 0.5
                # Clear cached settings to pick up any changes
                get_settings.cache_clear()
            except Exception:
                # Unexpected crash - log and apply exponential backoff before retrying
                logger.exception(
                    "Server crashed unexpectedly; restarting after backoff"
                )
                sleep_time = min(backoff, max_backoff)
                logger.info(f"Waiting {sleep_time:.1f}s before server restart")
                time.sleep(sleep_time)
                backoff = min(max_backoff, backoff * 2)
                # Continue loop to attempt restart
                continue
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
    if token := settings.anthropic_auth_token.get_secret_value().strip():
        env["ANTHROPIC_AUTH_TOKEN"] = token
    return env


def _preflight_proxy(proxy_root_url: str) -> str | None:
    """Return an error message when the local proxy health check is unreachable."""

    url = f"{proxy_root_url.rstrip('/')}{PROXY_PREFLIGHT_PATH}"
    try:
        with httpx.Client(timeout=PROXY_PREFLIGHT_TIMEOUT_SECONDS) as client:
            response = client.get(url)
            if not 200 <= response.status_code < 300:
                return f"returned HTTP {response.status_code}"
    except httpx.ConnectError:
        return "Connection refused"
    except httpx.TimeoutException:
        return "Timed out"
    except OSError as exc:
        return str(exc)
    return None


def launch_claude(argv: Sequence[str] | None = None) -> None:
    """Launch Claude Code with Free Claude Code proxy environment variables."""

    settings = get_settings()
    proxy_root_url = local_proxy_root_url(settings)
    if error := _preflight_proxy(proxy_root_url):
        print(
            f"Free Claude Code proxy is not reachable at {proxy_root_url}: {error}",
            file=sys.stderr,
        )
        print("Start it in another terminal with: fcc-server", file=sys.stderr)
        raise SystemExit(1)

    args = list(sys.argv[1:] if argv is None else argv)
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

    command = [claude_command, *args]
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


def completions() -> None:
    """Print shell completion script for fcc-* commands.

    Usage:
        eval "$(fcc-completions)"       # bash
        eval "$(fcc-completions)"      # zsh
    """
    shell = os.environ.get("SHELL", "")
    if "zsh" in shell:
        script = """#compdef fcc-server fcc-init fcc-claude fcc-completions
_fcc_claude_commands() {
  local -a commands
  commands=(
    "server:Start the proxy server"
    "init:Initialize .env configuration"
    "claude:Launch Claude Code CLI"
    "completions:Print shell completion"
  )
  _describe 'command' commands
}
compdef _fcc_claude_commands fcc-server fcc-init fcc-claude fcc-completions
"""
    else:
        script = """_fcc_claude_commands() {
  local cur="$2"
  case "$cur" in
    -*)
      COMPREPLY=()
      ;;
    *)
      COMPREPLY=( $(compgen -W "server init claude completions" -- "$cur") )
      ;;
  esac
}
complete -F _fcc_claude_commands fcc-server fcc-init fcc-claude fcc-completions
"""
    print(script)
