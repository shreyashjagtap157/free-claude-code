"""Provider model-list response parsing helpers."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from providers.exceptions import ModelListResponseError


@dataclass(frozen=True, slots=True)
class ProviderModelInfo:
    """Internal provider model metadata used for gateway model-list shaping."""

    model_id: str
    supports_thinking: bool | None = None
    context_window: int | None = None
    max_output_tokens: int | None = None
    supports_vision: bool | None = None
    supports_tools: bool | None = None
    supports_streaming: bool | None = None


# Known model capability defaults by exact model ID (matched first).
# Providers that don't expose capability metadata in their /models endpoint
# can rely on these table-driven defaults for well-known models.
_KNOWN_MODEL_CAPABILITIES: dict[str, dict[str, int | bool | None]] = {
    # ==================== DeepSeek family ====================
    "deepseek-v4-pro": {"context_window": 1_000_000, "max_output_tokens": 384_000},
    "deepseek-v4-flash": {"context_window": 1_000_000, "max_output_tokens": 384_000},
    "deepseek-v3": {"context_window": 64_000, "max_output_tokens": 8_000},
    "deepseek-chat": {"context_window": 64_000, "max_output_tokens": 8_000},
    # ==================== Wafer (pass.wafer.ai) ====================
    # Context windows from Wafer docs; max_output_tokens not documented per model.
    "MiniMax-M3": {"context_window": 1_048_576},
    "MiniMax-M2.7": {"context_window": 1_048_576},
    "Kimi-K2.6": {"context_window": 262_144},
    "Qwen3.5-397B-A17B": {"context_window": 262_144},
    "Qwen3.6-35B-A3B": {"context_window": 256_000},
    "qwen3.6-max-preview": {"context_window": 256_000},
    "qwen3.7-max": {"context_window": 256_000},
    "GLM-5.1": {"context_window": 202_752},
    # ==================== NVIDIA NIM hosted models ====================
    "z-ai/glm-5.1": {"context_window": 202_752},
    "moonshotai/kimi-k2.6": {"context_window": 262_144},
    "minimaxai/minimax-m2.7": {"context_window": 1_048_576},
    "minimaxai/minimax-m3": {"context_window": 1_048_576},
    "deepseek-ai/deepseek-v4-pro": {
        "context_window": 1_000_000,
        "max_output_tokens": 384_000,
    },
    "deepseek-ai/deepseek-v4-flash": {
        "context_window": 1_000_000,
        "max_output_tokens": 384_000,
    },
}

# Known model capability defaults by model-ID prefix (matched after exact match fails).
# This handles models that include version tags or size suffixes
# (e.g. "llama3.1:8b", "qwen2.5:7b", "mistral:7b").
_KNOWN_MODEL_PREFIXES: dict[str, dict[str, int | bool | None]] = {
    # ==================== Ollama / open-source families ====================
    # Ollama default context windows from the Ollama library. No separate
    # max_output_tokens limit is enforced by Ollama (output is bounded by the
    # total context window).
    "llama3.2": {"context_window": 128_000},
    "llama3.1": {"context_window": 128_000},
    "llama3": {"context_window": 8_000},
    "llama2": {"context_window": 4_096},
    "mistral": {"context_window": 32_000},
    "mixtral": {"context_window": 32_000},
    "gemma2": {"context_window": 8_000},
    "gemma": {"context_window": 8_000},
    "phi4": {"context_window": 128_000},
    "phi-4": {"context_window": 128_000},
    "phi3": {"context_window": 128_000},
    "phi-3": {"context_window": 128_000},
    "qwen2.5": {"context_window": 32_768},
    "qwen2": {"context_window": 32_768},
    "qwen": {"context_window": 32_768},
    "deepseek-coder": {"context_window": 128_000},
    "deepseek-r1": {"context_window": 128_000},
    "falcon": {"context_window": 8_192},
    "codestral": {"context_window": 256_000},
    "starcoder2": {"context_window": 16_384},
    "command-r": {"context_window": 128_000},
    "dbrx": {"context_window": 32_768},
}


def _lookup_known_capabilities(
    model_id: str,
) -> dict[str, int | bool | None] | None:
    """Look up known capabilities for a model ID.

    Tries exact match in ``_KNOWN_MODEL_CAPABILITIES`` first, then strips the
    version tag after ``:`` (e.g. ``llama3.1:8b`` → ``llama3.1``), then
    progressively strips the last component separated by ``/`` or ``-``
    (e.g. ``deepseek-coder-v2`` → ``deepseek-coder`` → ``deepseek``).
    """
    known = _KNOWN_MODEL_CAPABILITIES.get(model_id)
    if known is not None:
        return known

    # Strip tag after ":" to get clean base name (handles Ollama "name:tag").
    base = model_id.split(":")[0]
    known = _KNOWN_MODEL_PREFIXES.get(base)
    if known is not None:
        return known

    # Progressively strip last component by "/" or "-" on the clean base name.
    for separator in ("/", "-"):
        parts = base.split(separator)
        while len(parts) > 1:
            parts = parts[:-1]
            candidate = separator.join(parts)
            known = _KNOWN_MODEL_PREFIXES.get(candidate)
            if known is not None:
                return known

    return None


def _enrich_model_infos(
    model_infos: frozenset[ProviderModelInfo],
) -> frozenset[ProviderModelInfo]:
    """Apply static known-capability defaults for well-known model IDs.

    Provider model-list endpoints (OpenAI-compatible or native) generally do
    not return capability metadata. This helper fills in ``context_window``
    and ``max_output_tokens`` from known capability tables for recognized
    model IDs without overwriting values already present on the input
    ``ProviderModelInfo`` objects.

    Exact match in ``_KNOWN_MODEL_CAPABILITIES`` is tried first, then prefix
    match in ``_KNOWN_MODEL_PREFIXES`` (handles version-tagged model IDs).
    """
    enriched: list[ProviderModelInfo] = []
    for info in model_infos:
        known = _lookup_known_capabilities(info.model_id)
        if known is None:
            enriched.append(info)
            continue
        enriched.append(
            ProviderModelInfo(
                model_id=info.model_id,
                supports_thinking=info.supports_thinking,
                context_window=info.context_window or known.get("context_window"),
                max_output_tokens=info.max_output_tokens
                or known.get("max_output_tokens"),
                supports_vision=info.supports_vision,
                supports_tools=info.supports_tools,
                supports_streaming=info.supports_streaming,
            )
        )
    return frozenset(enriched)


def model_infos_from_ids(
    model_ids: Iterable[str], *, supports_thinking: bool | None = None
) -> frozenset[ProviderModelInfo]:
    """Build unknown-capability model metadata from plain provider model ids."""
    return _enrich_model_infos(
        frozenset(
            ProviderModelInfo(model_id=model_id, supports_thinking=supports_thinking)
            for model_id in model_ids
            if model_id.strip()
        )
    )


def extract_openai_model_ids(payload: Any, *, provider_name: str) -> frozenset[str]:
    """Extract model ids from an OpenAI-compatible ``/models`` response."""
    data = _field(payload, "data")
    if not _is_sequence(data):
        raise _malformed(provider_name, "expected top-level data array")

    model_ids: set[str] = set()
    for item in data:
        model_id = _field(item, "id")
        if not isinstance(model_id, str) or not model_id.strip():
            raise _malformed(provider_name, "expected every data item to include id")
        model_ids.add(model_id)

    if not model_ids:
        raise _malformed(provider_name, "response did not include any model ids")
    return frozenset(model_ids)


def extract_openrouter_tool_model_ids(
    payload: Any, *, provider_name: str
) -> frozenset[str]:
    """Extract OpenRouter model ids that advertise tool-use support."""
    return frozenset(
        info.model_id
        for info in extract_openrouter_tool_model_infos(
            payload, provider_name=provider_name
        )
    )


def extract_openrouter_tool_model_infos(
    payload: Any, *, provider_name: str
) -> frozenset[ProviderModelInfo]:
    """Extract OpenRouter tool-capable model ids with thinking capability metadata."""
    data = _field(payload, "data")
    if not _is_sequence(data):
        raise _malformed(provider_name, "expected top-level data array")

    model_infos: set[ProviderModelInfo] = set()
    for item in data:
        model_id = _field(item, "id")
        if not isinstance(model_id, str) or not model_id.strip():
            raise _malformed(provider_name, "expected every data item to include id")

        supported_parameters = _field(item, "supported_parameters")
        if not _is_sequence(supported_parameters):
            continue
        supported_parameter_names = {
            param for param in supported_parameters if isinstance(param, str)
        }
        if supported_parameter_names.isdisjoint({"tools", "tool_choice"}):
            continue

        # Extract context_window from context_length (OpenRouter-specific field).
        context_length = _field(item, "context_length")
        context_window: int | None = (
            context_length
            if isinstance(context_length, int) and context_length > 0
            else None
        )

        # Extract vision support from architecture.modality / input_modalities.
        architecture = _field(item, "architecture")
        supports_vision: bool | None = _resolve_openrouter_vision_support(architecture)

        # Extract max_output_tokens from top_provider.max_completion_tokens
        # (preferred) or per_request_limits.completion_tokens (fallback).
        max_output_tokens: int | None = None
        top_provider = _field(item, "top_provider")
        if isinstance(top_provider, dict):
            mct = top_provider.get("max_completion_tokens")
            if isinstance(mct, int) and mct > 0:
                max_output_tokens = mct
        if max_output_tokens is None:
            per_request_limits = _field(item, "per_request_limits")
            if isinstance(per_request_limits, dict):
                ct = per_request_limits.get("completion_tokens")
                if isinstance(ct, int) and ct > 0:
                    max_output_tokens = ct

        model_infos.add(
            ProviderModelInfo(
                model_id=model_id,
                supports_thinking="reasoning" in supported_parameter_names,
                context_window=context_window,
                max_output_tokens=max_output_tokens,
                supports_vision=supports_vision,
            )
        )

    return frozenset(model_infos)


def _resolve_openrouter_vision_support(architecture: Any) -> bool | None:
    """Determine vision support from an OpenRouter architecture object.

    Checks ``input_modalities`` (array) first, then falls back to
    ``modality`` (string). Returns ``True`` when image input is
    indicated, ``False`` when explicitly text-only, and ``None``
    when no architecture metadata is available.
    """
    if not isinstance(architecture, dict):
        return None

    # Prefer the structured input_modalities array.
    input_modalities = architecture.get("input_modalities")
    if isinstance(input_modalities, list):
        return "image" in input_modalities

    # Fall back to the modality string (e.g. "text+image->text").
    modality = architecture.get("modality")
    if isinstance(modality, str):
        return "image" in modality.lower()

    return None


def extract_ollama_model_ids(payload: Any, *, provider_name: str) -> frozenset[str]:
    """Extract model ids from Ollama's native ``/api/tags`` response."""
    models = _field(payload, "models")
    if not _is_sequence(models):
        raise _malformed(provider_name, "expected top-level models array")

    model_ids: set[str] = set()
    for item in models:
        item_ids: list[str] = []
        for key in ("model", "name"):
            value = _field(item, key)
            if isinstance(value, str) and value.strip():
                item_ids.append(value)
        if not item_ids:
            raise _malformed(
                provider_name,
                "expected every models item to include model or name",
            )
        model_ids.update(item_ids)

    if not model_ids:
        raise _malformed(provider_name, "response did not include any model ids")
    return frozenset(model_ids)


def _field(item: Any, name: str) -> Any:
    if isinstance(item, Mapping):
        return item.get(name)
    return getattr(item, name, None)


def _is_sequence(value: Any) -> bool:
    return isinstance(value, Sequence) and not isinstance(
        value, str | bytes | bytearray
    )


def _malformed(provider_name: str, reason: str) -> ModelListResponseError:
    return ModelListResponseError(
        f"{provider_name} model-list response is malformed: {reason}"
    )
