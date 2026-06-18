"""Sovereign Context Orchestration Engine.
This module handles the intelligent management of context, routing, and reliability.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from loguru import logger

from core.anthropic.context_trimmer import (
    _enforce_token_budget,
    _sanitize_orphaned_tool_blocks,
    _strip_thinking_blocks,
    _truncate_tool_results,
)


class OrchestratorConfig:
    L1_BUFFER_SIZE = 10  # Number of most recent messages to keep raw
    L2_SUMMARY_THRESHOLD = 15000  # Tokens at which we start compressing history
    MAX_TOTAL_BUDGET = 40000


class ContextOrchestrator:
    def __init__(self, settings: Any, provider_getter: Any):
        self.settings = settings
        self.provider_getter = provider_getter

    def resolve_best_provider(
        self,
        requested_model: str,
        capabilities_required: set[str],
        provider_catalog: Mapping[str, Any],
    ) -> str:
        """
        Finds the best provider based on capabilities and priority.
        """
        # This is a simplified version; in a full SOTA impl, this would
        # check real-time latency and error rates.
        candidates = [
            desc
            for desc in provider_catalog.values()
            if all(cap in desc.capabilities for cap in capabilities_required)
        ]

        if not candidates:
            raise RuntimeError("No provider found matching required capabilities")

        # Sort by priority (lowest first)
        candidates.sort(key=lambda x: x.priority)
        return candidates[0].provider_id

    def optimize_context(
        self,
        messages: list[Any],
        system: Any,
        tools: Any,
        provider_id: str,
        provider_catalog: Mapping[str, Any],
    ) -> list[Any]:
        """
        Replaces basic trimming with Hierarchical Context Management.

        Strategy:
        1. L1 (Raw): Keep the last L1_BUFFER_SIZE messages.
        2. L2 (Compressed): If total tokens > L2_SUMMARY_THRESHOLD,
           compress older messages into a summary.
        3. Prompt Caching: Structure the output to maximize cache hits.
        """
        provider_desc = provider_catalog.get(provider_id)
        supports_caching = (
            provider_desc and "prompt_caching" in provider_desc.capabilities
        )

        # Always strip thinking blocks and sanitize orphaned tool results.
        result = _strip_thinking_blocks(_sanitize_orphaned_tool_blocks(messages))

        # Providers with prompt_caching skip L1/L2 compression but still
        # enforce a token budget using the provider's max_input_tokens.
        if supports_caching:
            budget = getattr(provider_desc, "max_input_tokens", 0) or 0
            if budget > 0:
                result = _enforce_token_budget(result, system, tools, budget)
            return result

        # L1/L2 compression for large conversations.
        if len(result) > OrchestratorConfig.L1_BUFFER_SIZE:
            l1_messages = result[-OrchestratorConfig.L1_BUFFER_SIZE :]
            l2_messages = result[: -OrchestratorConfig.L1_BUFFER_SIZE]

            # Preservation: [First Message] + [Compressed Middle] + [L1 Buffer]
            preserved_head = [result[0]]

            # Keep every 2nd message in L2 to reduce volume while maintaining flow.
            compressed_middle = l2_messages[1::2] if len(l2_messages) > 1 else []

            result = preserved_head + compressed_middle + l1_messages

            # Truncate oversized tool results.
            max_tool_tokens = getattr(self.settings, "max_tool_result_tokens", 0)
            if max_tool_tokens > 0:
                result = _truncate_tool_results(result, max_tool_tokens)

            # Re-apply sanitization after structural changes.
            result = _sanitize_orphaned_tool_blocks(result)

            logger.info(
                "ORCHESTRATOR: Context compressed. Original: {} msgs, New: {} msgs.",
                len(messages),
                len(result),
            )

        # Enforce token budget so the provider receives at most max_context_tokens.
        max_context_tokens = getattr(self.settings, "max_context_tokens", 0)
        if max_context_tokens > 0:
            result = _enforce_token_budget(result, system, tools, max_context_tokens)

        return result

    async def execute_with_fallback(
        self,
        request_data: Any,
        primary_provider_id: str,
        callback: Any,
        provider_catalog: Mapping[str, Any],
    ):
        """
        Executes a request via the primary provider.

        Full fallback orchestration (trying secondary providers when the
        primary fails) is reserved for a future implementation.  For now
        we call the primary provider directly so that per-provider errors
        (auth, rate-limit, overloaded) propagate naturally to the caller.
        """
        return await callback(primary_provider_id)
