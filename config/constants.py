"""Shared defaults used by config models and provider adapters."""

# HTTP client connect timeout (seconds). Keep aligned with README.md and .env.example.
HTTP_CONNECT_TIMEOUT_DEFAULT = 10.0

# Anthropic Messages API default when the client omits max_tokens.
ANTHROPIC_DEFAULT_MAX_OUTPUT_TOKENS = 81920

# Max bytes read from a non-200 native messages response when verbose error logging is on.
NATIVE_MESSAGES_ERROR_BODY_LOG_CAP_BYTES = 4096

# ==================== Auto-Compact ====================
# Default context window (tokens) when the model is unknown.
DEFAULT_CONTEXT_WINDOW: int = 200_000

# Default fraction of context window that triggers automatic /compact.
DEFAULT_AUTO_COMPACT_THRESHOLD: float = 0.75

# Token estimation multiplier for output (conservative overestimate).
# Each turn's total estimated consumption = input_tokens * (1 + OUTPUT_MULTIPLIER)
AUTO_COMPACT_OUTPUT_MULTIPLIER: float = 1.5
