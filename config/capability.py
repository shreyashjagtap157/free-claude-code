"""Capability enumeration for provider descriptors.

Provides type-safe capability metadata for :class:`~config.provider_catalog.ProviderDescriptor`.
"""

from __future__ import annotations

from enum import StrEnum


class Capability(StrEnum):
    """Provider capability flags used in :data:`~config.provider_catalog.PROVIDER_CATALOG`."""

    CHAT = "chat"
    STREAMING = "streaming"
    TOOLS = "tools"
    THINKING = "thinking"
    VISION = "vision"
    NATIVE_ANTHROPIC = "native_anthropic"
    LOCAL = "local"
    RATE_LIMIT = "rate_limit"
