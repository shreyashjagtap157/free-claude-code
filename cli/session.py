"""Claude Code CLI session management."""

import asyncio
import json
import os
from collections.abc import AsyncGenerator, AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from config.constants import (
    AUTO_COMPACT_OUTPUT_MULTIPLIER,
    DEFAULT_AUTO_COMPACT_THRESHOLD,
    DEFAULT_CONTEXT_WINDOW,
)
from core.trace import trace_event

from .process_registry import kill_pid_tree_best_effort, register_pid, unregister_pid

# Cap stderr capture so a runaway child cannot exhaust memory; pipe is still drained.
_MAX_STDERR_CAPTURE_BYTES = 256 * 1024


class LineStreamReader:
    """Async iterator that reads from a StreamReader and yields complete lines.

    Handles the bytearray line-splitting logic that was previously inline in
    ``start_task``, making it independently testable and reusable.
    """

    def __init__(self, stream: asyncio.StreamReader, chunk_size: int = 65536) -> None:
        self._stream = stream
        self._chunk_size = chunk_size

    async def read_lines(self) -> AsyncIterator[str]:
        """Yield complete lines (without trailing newline) until EOF."""
        buffer = bytearray()
        while True:
            chunk = await self._stream.read(self._chunk_size)
            if not chunk:
                # Flush remaining buffer (no newline at EOF)
                if buffer:
                    line_str = buffer.decode("utf-8", errors="replace").strip()
                    if line_str:
                        yield line_str
                return

            buffer.extend(chunk)
            while True:
                newline_pos = buffer.find(b"\n")
                if newline_pos == -1:
                    break
                line = buffer[:newline_pos]
                buffer = buffer[newline_pos + 1 :]
                line_str = line.decode("utf-8", errors="replace").strip()
                if line_str:
                    yield line_str


@dataclass(frozen=True, slots=True)
class ClaudeCliConfig:
    """Configuration for a managed Claude CLI subprocess."""

    workspace_path: str
    api_url: str
    allowed_dirs: list[str] = field(default_factory=list)
    plans_directory: str | None = None
    claude_bin: str = "claude"


class CLISession:
    """Manages a single persistent Claude Code CLI subprocess."""

    def __init__(
        self,
        workspace_path: str,
        api_url: str,
        allowed_dirs: list[str] | None = None,
        plans_directory: str | None = None,
        claude_bin: str = "claude",
        *,
        log_raw_cli_diagnostics: bool = False,
        context_window: int = DEFAULT_CONTEXT_WINDOW,
        auto_compact_threshold: float = DEFAULT_AUTO_COMPACT_THRESHOLD,
        auto_compact_enabled: bool = True,
        supports_vision: bool | None = None,
        supports_tools: bool | None = None,
        max_output_tokens: int | None = None,
    ):
        self.config = ClaudeCliConfig(
            workspace_path=os.path.normpath(os.path.abspath(workspace_path)),
            api_url=api_url,
            allowed_dirs=[os.path.normpath(d) for d in (allowed_dirs or [])],
            plans_directory=plans_directory,
            claude_bin=claude_bin,
        )
        self.workspace = self.config.workspace_path
        self.api_url = self.config.api_url
        self.allowed_dirs = self.config.allowed_dirs
        self.plans_directory = self.config.plans_directory
        self.claude_bin = self.config.claude_bin
        self._log_raw_cli_diagnostics = log_raw_cli_diagnostics
        self.process: asyncio.subprocess.Process | None = None
        self.current_session_id: str | None = None
        self._is_busy = False
        self._cli_lock = asyncio.Lock()

        # Auto-compact state (persists across turns in the same session)
        self._accumulated_tokens: int = 0
        self._context_window: int = context_window
        self._auto_compact_threshold: float = auto_compact_threshold
        self._auto_compact_enabled: bool = auto_compact_enabled
        self._supports_vision: bool | None = supports_vision
        self._supports_tools: bool | None = supports_tools
        self._max_output_tokens: int | None = max_output_tokens

    @staticmethod
    async def _drain_stderr_bounded(
        process: asyncio.subprocess.Process,
        *,
        max_bytes: int = _MAX_STDERR_CAPTURE_BYTES,
    ) -> bytes:
        """Read stderr concurrently with stdout to avoid subprocess pipe deadlocks.

        Retains at most ``max_bytes`` for logging; any excess is discarded, but
        the pipe is read until EOF so a noisy child cannot fill the buffer and
        block forever.
        """
        if not process.stderr:
            return b""
        parts: list[bytes] = []
        received = 0
        while True:
            chunk = await process.stderr.read(65_536)
            if not chunk:
                break
            if received < max_bytes:
                take = min(len(chunk), max_bytes - received)
                if take:
                    parts.append(chunk[:take])
                    received += take
        return b"".join(parts)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_busy(self) -> bool:
        return self._is_busy

    @property
    def accumulated_tokens(self) -> int:
        return self._accumulated_tokens

    @accumulated_tokens.setter
    def accumulated_tokens(self, value: int) -> None:
        self._accumulated_tokens = max(0, value)

    @property
    def context_window(self) -> int:
        return self._context_window

    @context_window.setter
    def context_window(self, value: int) -> None:
        self._context_window = max(1024, value)

    @property
    def supports_vision(self) -> bool | None:
        return self._supports_vision

    @property
    def supports_tools(self) -> bool | None:
        return self._supports_tools

    @property
    def max_output_tokens(self) -> int | None:
        return self._max_output_tokens

    # ------------------------------------------------------------------
    # Token estimation / auto-compact
    # ------------------------------------------------------------------

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        return max(1, len(text) // 4)

    def prepare_auto_compact_prompt(self, prompt: str) -> tuple[str, bool]:
        if not self._auto_compact_enabled:
            return prompt, False

        estimated_input = self._estimate_tokens(prompt)
        estimated_total = estimated_input * (1 + AUTO_COMPACT_OUTPUT_MULTIPLIER)
        projected_total = self._accumulated_tokens + estimated_total
        threshold_tokens = int(self._context_window * self._auto_compact_threshold)

        if projected_total <= threshold_tokens:
            return prompt, False

        modified = f"/compact\n\n{prompt}"
        return modified, True

    def update_accumulated_tokens(
        self, prompt: str, prompt_tokens: int | None = None
    ) -> None:
        input_tokens = (
            prompt_tokens
            if prompt_tokens is not None
            else self._estimate_tokens(prompt)
        )
        estimated_output = int(input_tokens * AUTO_COMPACT_OUTPUT_MULTIPLIER)
        self._accumulated_tokens += input_tokens + estimated_output

    # ------------------------------------------------------------------
    # Child process environment & command building (TaskContext concern)
    # ------------------------------------------------------------------

    def _build_child_env(self) -> dict[str, str]:
        """Build the environment dict for the Claude CLI child process."""
        env = dict(os.environ)
        env.update(
            {
                "ANTHROPIC_API_KEY": "sk-placeholder-key-for-proxy",
                "ANTHROPIC_API_URL": self.api_url,
                "TERM": "dumb",
                "PYTHONIOENCODING": "utf-8",
            }
        )
        if self.api_url.endswith("/v1"):
            env["ANTHROPIC_BASE_URL"] = self.api_url[:-3]
        else:
            env["ANTHROPIC_BASE_URL"] = self.api_url

        # Forward model capability hints so the client can adapt behavior
        # without waiting for the /v1/models response.
        if self._max_output_tokens is not None:
            env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] = str(self._max_output_tokens)
        if self._supports_vision is not None:
            env["CLAUDE_CODE_SUPPORTS_VISION"] = str(self._supports_vision).lower()
        if self._supports_tools is not None:
            env["CLAUDE_CODE_SUPPORTS_TOOLS"] = str(self._supports_tools).lower()

        return env

    def _build_child_cmd(
        self, prompt: str, session_id: str | None, fork_session: bool
    ) -> list[str]:
        """Build the command list for the Claude CLI child process."""
        if session_id and not session_id.startswith("pending_"):
            cmd = [self.claude_bin, "--resume", session_id]
            if fork_session:
                cmd.append("--fork-session")
        else:
            cmd = [self.claude_bin]

        cmd += [
            "-p",
            prompt,
            "--output-format",
            "stream-json",
            "--dangerously-skip-permissions",
            "--verbose",
        ]

        if self.allowed_dirs:
            for d in self.allowed_dirs:
                cmd.extend(["--add-dir", d])

        if self.plans_directory is not None:
            settings_json = json.dumps({"plansDirectory": self.plans_directory})
            cmd.extend(["--settings", settings_json])

        return cmd

    # ------------------------------------------------------------------
    # Process spawning and lifecycle (TaskContext concern)
    # ------------------------------------------------------------------

    async def _spawn_process(self, cmd: list[str], env: dict[str, str]) -> bool:
        """Spawn the subprocess, register PID, return whether stdout is available."""
        self.process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.workspace,
            env=env,
            limit=1024 * 1024,
        )
        if self.process and self.process.pid:
            register_pid(self.process.pid)
        return bool(self.process and self.process.stdout)

    # ------------------------------------------------------------------
    # Line processing and event emission (OutputProcessor concern)
    # ------------------------------------------------------------------

    async def _handle_line_gen(
        self, line_str: str, session_id_extracted: bool
    ) -> AsyncGenerator[dict]:
        """Parse a single JSON line and yield events."""
        try:
            event = json.loads(line_str)
            if not session_id_extracted:
                extracted_id = self._extract_session_id(event)
                if extracted_id:
                    self.current_session_id = extracted_id
                    logger.info(f"Extracted session ID: {extracted_id}")
                    yield {"type": "session_info", "session_id": extracted_id}
            yield event
        except json.JSONDecodeError:
            if self._log_raw_cli_diagnostics:
                logger.debug("Non-JSON output: {}", line_str)
            else:
                logger.debug("Non-JSON CLI line: char_len={}", len(line_str))
            yield {"type": "raw", "content": line_str}

    def _extract_session_id(self, event: Any) -> str | None:
        """Extract session ID from CLI event."""
        if not isinstance(event, dict):
            return None
        if "session_id" in event:
            return event["session_id"]
        if "sessionId" in event:
            return event["sessionId"]
        for key in ["init", "system", "result", "metadata"]:
            if key in event and isinstance(event[key], dict):
                nested = event[key]
                if "session_id" in nested:
                    return nested["session_id"]
                if "sessionId" in nested:
                    return nested["sessionId"]
        if "conversation" in event and isinstance(event["conversation"], dict):
            conv = event["conversation"]
            if "id" in conv:
                return conv["id"]
        return None

    # ------------------------------------------------------------------
    # Stderr output handling (OutputProcessor concern)
    # ------------------------------------------------------------------

    @staticmethod
    def _format_stderr_text(stderr_bytes: bytes) -> str | None:
        """Decode and strip stderr bytes; return None when empty."""
        if not stderr_bytes:
            return None
        text = stderr_bytes.decode("utf-8", errors="replace").strip()
        return text if text else None

    # ------------------------------------------------------------------
    # Main task entry point
    # ------------------------------------------------------------------

    async def start_task(
        self, prompt: str, session_id: str | None = None, fork_session: bool = False
    ) -> AsyncGenerator[dict]:
        """
        Start a new task or continue an existing session.

        Orchestrates: prompt validation, child process env/cmd/spawn,
        stdout line reading, stderr draining, and event emission.

        Args:
            prompt: The user's message/prompt
            session_id: Optional session ID to resume

        Yields:
            Event dictionaries from the CLI
        """
        if len(prompt) > 120_000:
            logger.warning("Prompt too long ({} chars), truncating", len(prompt))
            prompt = prompt[:120_000]

        async with self._cli_lock:
            self._is_busy = True

            env = self._build_child_env()
            cmd = self._build_child_cmd(prompt, session_id, fork_session)

            trace_event(
                stage="claude_cli",
                event="claude_cli.process.launch",
                source="claude_cli",
                resume_session_id=(
                    session_id
                    if session_id and not session_id.startswith("pending_")
                    else None
                ),
                fork_session=fork_session,
                prompt=prompt,
                cwd=self.workspace,
                claude_binary=self.claude_bin,
                cli_argv=cmd,
            )

            try:
                has_stdout = await self._spawn_process(cmd, env)
                if not has_stdout:
                    yield {"type": "exit", "code": 1}
                    return

                process = self.process
                assert process is not None and process.stdout is not None

                session_id_extracted = False
                stderr_task: asyncio.Task[bytes] | None = None
                if process.stderr:
                    stderr_task = asyncio.create_task(
                        self._drain_stderr_bounded(process)
                    )

                try:
                    reader = LineStreamReader(process.stdout)
                    async for line_str in reader.read_lines():
                        async for event in self._handle_line_gen(
                            line_str, session_id_extracted
                        ):
                            if event.get("type") == "session_info":
                                session_id_extracted = True
                            yield event
                except asyncio.CancelledError:
                    await asyncio.shield(self.stop())
                    raise
                finally:
                    stderr_bytes = b""
                    if stderr_task is not None:
                        stderr_bytes = await stderr_task

                stderr_text = self._format_stderr_text(stderr_bytes)
                if stderr_text:
                    if self._log_raw_cli_diagnostics:
                        logger.error("Claude CLI stderr: {}", stderr_text)
                    else:
                        logger.error(
                            "Claude CLI stderr: bytes={} text_chars={}",
                            len(stderr_bytes),
                            len(stderr_text),
                        )
                    logger.info("CLI_SESSION: Yielding error event from stderr")
                    yield {"type": "error", "error": {"message": stderr_text}}

                return_code = await process.wait()
                logger.info(
                    f"Claude CLI exited with code {return_code}, stderr_present={bool(stderr_text)}"
                )
                if return_code != 0 and not stderr_text:
                    logger.warning(
                        f"CLI_SESSION: Process exited with code {return_code} but no stderr captured"
                    )
                yield {
                    "type": "exit",
                    "code": return_code,
                    "stderr": stderr_text,
                }
            finally:
                self._is_busy = False
                if self.process and self.process.pid:
                    unregister_pid(self.process.pid)

    async def stop(self):
        """Stop the CLI process."""
        if self.process and self.process.returncode is None:
            try:
                logger.info(f"Stopping Claude CLI process {self.process.pid}")
                kill_pid_tree_best_effort(self.process.pid)
                try:
                    await asyncio.wait_for(self.process.wait(), timeout=2.0)
                except TimeoutError:
                    self.process.kill()
                    await self.process.wait()
                if self.process and self.process.pid:
                    unregister_pid(self.process.pid)
                return True
            except Exception as e:
                if self._log_raw_cli_diagnostics:
                    logger.error(
                        "Error stopping process: {}: {}",
                        type(e).__name__,
                        e,
                    )
                else:
                    logger.error(
                        "Error stopping process: exc_type={}",
                        type(e).__name__,
                    )
                return False
        return False
