"""Model management for the Sovereign CLI.
Handles local model loading, provider mapping, and VRAM lifecycle.
"""

from __future__ import annotations

from typing import Any

from loguru import logger


class ModelStatus:
    LOADED = "loaded"
    UNLOADED = "unloaded"
    REMOTE = "remote"


class ModelManager:
    def __init__(self):
        self.local_models: dict[str, dict[str, Any]] = {}  # name -> {path, status}
        self.remote_models: dict[str, str] = {}  # model_name -> provider_id

    def add_local_model(self, name: str, path: str):
        self.local_models[name] = {"path": path, "status": ModelStatus.UNLOADED}
        logger.info("Local model {} registered at {}", name, path)

    def load_model(self, name: str):
        if name in self.local_models:
            self.local_models[name]["status"] = ModelStatus.LOADED
            logger.info("Model {} loaded into VRAM", name)
            return True
        return False

    def unload_model(self, name: str):
        if name in self.local_models:
            self.local_models[name]["status"] = ModelStatus.UNLOADED
            logger.info("Model {} unloaded from VRAM", name)
            return True
        return False

    def link_provider_model(self, model_name: str, provider_id: str):
        self.remote_models[model_name] = provider_id

    def get_all_models(self) -> dict[str, list[dict[str, Any]]]:
        return {
            "local": [
                {"name": k, "status": v["status"], "path": v["path"]}
                for k, v in self.local_models.items()
            ],
            "remote": [
                {"name": k, "provider": v} for k, v in self.remote_models.items()
            ],
        }
