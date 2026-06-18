"""Runtime management for the Sovereign CLI.
Handles detection, installation, and path management of LLM runtimes.
"""

from __future__ import annotations

import platform
import shutil
from typing import Any

from loguru import logger


class RuntimeDescriptor:
    def __init__(
        self, name: str, recommended: bool, default_path: str, description: str
    ):
        self.name = name
        self.recommended = recommended
        self.default_path = default_path
        self.description = description


class RuntimeManager:
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.runtimes: dict[str, str] = {}  # name -> path
        self.available_runtimes = {
            "ollama": RuntimeDescriptor(
                "ollama", True, "ollama", "Standard for local LLMs"
            ),
            "llama.cpp": RuntimeDescriptor(
                "llama.cpp", True, "llama-cli", "High performance C++ inference"
            ),
            "vllm": RuntimeDescriptor(
                "vllm", False, "vllm", "Production grade throughput"
            ),
        }
        self._load_config()

    def _load_config(self):
        # In a real impl, this would read from a JSON/YAML file in .letta/
        # For now, we use a placeholder.
        pass

    def detect_best_runtime(self) -> str:
        """Detect hardware and recommend a runtime."""
        system = platform.system()
        # Simple detection logic
        if system == "Windows":
            return "ollama" if shutil.which("ollama") else "llama.cpp"
        return "ollama"

    def add_runtime(self, name: str, path: str):
        self.runtimes[name] = path
        logger.info("Runtime {} added at path {}", name, path)

    def get_runtime_path(self, name: str) -> str | None:
        if name not in self.available_runtimes:
            return None
        desc = self.available_runtimes[name]
        return self.runtimes.get(name) or desc.default_path

    def list_suitable_runtimes(self) -> list[dict[str, Any]]:
        return [
            {"name": k, "recommended": v.recommended, "desc": v.description}
            for k, v in self.available_runtimes.items()
        ]
