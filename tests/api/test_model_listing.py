from fastapi.testclient import TestClient
from pydantic import SecretStr

from api.app import create_app
from api.dependencies import get_settings
from config.settings import Settings
from providers.model_listing import ProviderModelInfo
from providers.registry import ProviderRegistry


def _settings(
    *,
    model: str = "deepseek/deepseek-chat",
    model_opus: str | None = "open_router/anthropic/claude-opus",
    model_haiku: str | None = "deepseek/deepseek-chat",
) -> Settings:
    return Settings.model_construct(
        model=model,
        model_opus=model_opus,
        model_sonnet=None,
        model_haiku=model_haiku,
        anthropic_auth_token=SecretStr(""),
    )


def test_models_list_includes_configured_refs_cached_provider_models_and_aliases():
    app = create_app(lifespan_enabled=False)
    settings = _settings()
    registry = ProviderRegistry()
    registry.cache_model_ids("deepseek", {"deepseek-chat"})
    registry.cache_model_ids("open_router", {"meta/llama-3.3", "anthropic/claude-opus"})
    app.state.provider_registry = registry
    app.dependency_overrides[get_settings] = lambda: settings

    try:
        response = TestClient(app).get("/v1/models")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    ids = [item["id"] for item in data["data"]]

    assert ids[:6] == [
        "anthropic/deepseek/deepseek-chat",
        "claude-3-freecc-no-thinking/deepseek/deepseek-chat",
        "anthropic/open_router/anthropic/claude-opus",
        "claude-3-freecc-no-thinking/open_router/anthropic/claude-opus",
        "anthropic/open_router/meta/llama-3.3",
        "claude-3-freecc-no-thinking/open_router/meta/llama-3.3",
    ]
    assert ids.count("anthropic/deepseek/deepseek-chat") == 1
    assert ids.count("claude-3-freecc-no-thinking/deepseek/deepseek-chat") == 1
    assert ids.count("anthropic/open_router/anthropic/claude-opus") == 1
    assert (
        ids.count("claude-3-freecc-no-thinking/open_router/anthropic/claude-opus") == 1
    )
    display_names = {item["id"]: item["display_name"] for item in data["data"]}
    assert (
        display_names["anthropic/open_router/meta/llama-3.3"]
        == "open_router/meta/llama-3.3"
    )
    assert (
        display_names["claude-3-freecc-no-thinking/open_router/meta/llama-3.3"]
        == "open_router/meta/llama-3.3 (no thinking)"
    )
    assert "claude-sonnet-4-20250514" in ids
    assert data["first_id"] == ids[0]
    assert data["last_id"] == ids[-1]
    assert data["has_more"] is False

    # Verify enrichment round-trips: deepseek-chat is in _KNOWN_MODEL_CAPABILITIES
    # with context_window=64_000 and max_output_tokens=8_000.
    for item in data["data"]:
        if item["id"] in (
            "anthropic/deepseek/deepseek-chat",
            "claude-3-freecc-no-thinking/deepseek/deepseek-chat",
        ):
            assert item["context_window"] == 64_000
            assert item["max_output_tokens"] == 8_000


def test_models_list_uses_openrouter_thinking_metadata_for_cached_models():
    app = create_app(lifespan_enabled=False)
    settings = _settings(model_opus=None)
    registry = ProviderRegistry()
    registry.cache_model_ids("deepseek", {"deepseek-chat"})
    registry.cache_model_infos(
        "open_router",
        {
            ProviderModelInfo(
                "reasoning-model",
                supports_thinking=True,
                context_window=200_000,
                max_output_tokens=8192,
                supports_vision=True,
                supports_tools=True,
            ),
            ProviderModelInfo(
                "plain-model",
                supports_thinking=False,
                context_window=128_000,
                max_output_tokens=4096,
                supports_vision=False,
                supports_tools=True,
            ),
        },
    )
    app.state.provider_registry = registry
    app.dependency_overrides[get_settings] = lambda: settings

    try:
        response = TestClient(app).get("/v1/models")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()["data"]
    ids = [item["id"] for item in data]
    assert "anthropic/open_router/reasoning-model" in ids
    assert "claude-3-freecc-no-thinking/open_router/reasoning-model" in ids
    assert "anthropic/open_router/plain-model" not in ids
    assert "claude-3-freecc-no-thinking/open_router/plain-model" in ids

    # Verify capability fields are exposed in the response
    for item in data:
        if (
            item["id"] == "anthropic/open_router/reasoning-model"
            or item["id"] == "claude-3-freecc-no-thinking/open_router/reasoning-model"
        ):
            assert item["context_window"] == 200_000
            assert item["max_output_tokens"] == 8192
            assert item["supports_vision"] is True
            assert item["supports_tools"] is True
        elif item["id"] == "claude-3-freecc-no-thinking/open_router/plain-model":
            assert item["context_window"] == 128_000
            assert item["max_output_tokens"] == 4096
            assert item["supports_vision"] is False
            assert item["supports_tools"] is True


def test_models_list_uses_cached_metadata_for_configured_openrouter_refs():
    app = create_app(lifespan_enabled=False)
    settings = _settings(
        model="open_router/plain-model",
        model_opus=None,
        model_haiku=None,
    )
    registry = ProviderRegistry()
    registry.cache_model_infos(
        "open_router",
        {ProviderModelInfo("plain-model", supports_thinking=False)},
    )
    app.state.provider_registry = registry
    app.dependency_overrides[get_settings] = lambda: settings

    try:
        response = TestClient(app).get("/v1/models")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    ids = [item["id"] for item in response.json()["data"]]
    assert "anthropic/open_router/plain-model" not in ids
    assert ids[0] == "claude-3-freecc-no-thinking/open_router/plain-model"


def test_models_list_includes_cached_wafer_models():
    app = create_app(lifespan_enabled=False)
    settings = _settings(
        model="wafer/DeepSeek-V4-Pro",
        model_opus=None,
        model_haiku=None,
    )
    registry = ProviderRegistry()
    registry.cache_model_infos(
        "wafer",
        {
            ProviderModelInfo(
                "DeepSeek-V4-Pro",
                context_window=1_000_000,
                max_output_tokens=384_000,
                supports_vision=True,
                supports_thinking=True,
            ),
            ProviderModelInfo(
                "MiniMax-M2.7",
                context_window=1_048_576,
                max_output_tokens=128_000,
                supports_vision=False,
                supports_thinking=None,
            ),
        },
    )
    app.state.provider_registry = registry
    app.dependency_overrides[get_settings] = lambda: settings

    try:
        response = TestClient(app).get("/v1/models")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()["data"]
    ids = [item["id"] for item in data]
    assert "anthropic/wafer/DeepSeek-V4-Pro" in ids
    assert "claude-3-freecc-no-thinking/wafer/DeepSeek-V4-Pro" in ids
    assert "anthropic/wafer/MiniMax-M2.7" in ids
    assert "claude-3-freecc-no-thinking/wafer/MiniMax-M2.7" in ids

    # Verify enriched capability fields round-trip through the pipeline.
    for item in data:
        if item["id"] in (
            "anthropic/wafer/DeepSeek-V4-Pro",
            "claude-3-freecc-no-thinking/wafer/DeepSeek-V4-Pro",
        ):
            assert item["context_window"] == 1_000_000
            assert item["max_output_tokens"] == 384_000
            assert item["supports_vision"] is True
        elif item["id"] in (
            "anthropic/wafer/MiniMax-M2.7",
            "claude-3-freecc-no-thinking/wafer/MiniMax-M2.7",
        ):
            assert item["context_window"] == 1_048_576
            assert item["max_output_tokens"] == 128_000
            assert item["supports_vision"] is False


# =============================================================================
# _lookup_known_capabilities unit tests
# =============================================================================


def test_lookup_known_capabilities_exact_match():
    """Exact model ID in _KNOWN_MODEL_CAPABILITIES returns its capabilities."""
    from providers.model_listing import _lookup_known_capabilities

    result = _lookup_known_capabilities("deepseek-v4-pro")
    assert result is not None
    assert result["context_window"] == 1_000_000
    assert result["max_output_tokens"] == 384_000


def test_lookup_known_capabilities_exact_match_preferred_over_prefix():
    """Exact match is preferred; a prefix that would also match is ignored."""
    from providers.model_listing import _lookup_known_capabilities

    # deepseek-chat exists as exact -- its data is returned, not deepseek prefix.
    result = _lookup_known_capabilities("deepseek-chat")
    assert result is not None
    assert result["context_window"] == 64_000
    assert result["max_output_tokens"] == 8_000


def test_lookup_known_capabilities_tag_prefix_match():
    """Ollama-style 'name:tag' IDs match the prefix before the colon."""
    from providers.model_listing import _lookup_known_capabilities

    result = _lookup_known_capabilities("llama3.1:8b")
    assert result is not None
    assert result["context_window"] == 128_000
    assert "max_output_tokens" not in result


def test_lookup_known_capabilities_ollama_tag_preserves_prefix():
    """Version tags like ':latest' are stripped to match the base prefix."""
    from providers.model_listing import _lookup_known_capabilities

    result = _lookup_known_capabilities("qwen2.5:7b-instruct-q4_K_M")
    assert result is not None
    assert result["context_window"] == 32_768


def test_lookup_known_capabilities_progressive_strip_hyphen():
    """Progressive '-' strip resolves deepseek-coder-v2 -> deepseek-coder."""
    from providers.model_listing import _lookup_known_capabilities

    result = _lookup_known_capabilities("deepseek-coder-v2:latest")
    assert result is not None
    assert result["context_window"] == 128_000


def test_lookup_known_capabilities_multi_level_progressive_strip():
    """Multiple '-' progressive strip: command-r-plus strips to command-r."""
    from providers.model_listing import _lookup_known_capabilities

    # command-r-plus:latest → strip tag → command-r-plus →
    # progressive '-' strip: [command, r, plus] → command-r → match
    result = _lookup_known_capabilities("command-r-plus:latest")
    assert result is not None
    assert result["context_window"] == 128_000


def test_lookup_known_capabilities_no_match():
    """Unknown model ID returns None."""
    from providers.model_listing import _lookup_known_capabilities

    result = _lookup_known_capabilities("completely-unknown-model-9000")
    assert result is None


def test_lookup_known_capabilities_no_match_empty_string():
    """Empty string returns None (no match)."""
    from providers.model_listing import _lookup_known_capabilities

    result = _lookup_known_capabilities("")
    assert result is None


def test_models_list_works_without_provider_registry():
    app = create_app(lifespan_enabled=False)
    settings = _settings()
    app.dependency_overrides[get_settings] = lambda: settings

    try:
        response = TestClient(app).get("/v1/models")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    ids = [item["id"] for item in response.json()["data"]]
    assert ids[:4] == [
        "anthropic/deepseek/deepseek-chat",
        "claude-3-freecc-no-thinking/deepseek/deepseek-chat",
        "anthropic/open_router/anthropic/claude-opus",
        "claude-3-freecc-no-thinking/open_router/anthropic/claude-opus",
    ]
    assert "claude-sonnet-4-20250514" in ids
