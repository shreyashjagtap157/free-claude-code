"""FastAPI route handlers."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from loguru import logger

from config.settings import Settings
from core.anthropic import get_token_count
from core.trace import trace_event
from providers.registry import ProviderRegistry

from . import dependencies
from .dependencies import get_settings, require_api_key
from .gateway_model_ids import gateway_model_id, no_thinking_gateway_model_id
from .models.anthropic import MessagesRequest, TokenCountRequest
from .models.responses import ModelResponse, ModelsListResponse
from .services import ClaudeProxyService

router = APIRouter()

DISCOVERED_MODEL_CREATED_AT = "1970-01-01T00:00:00Z"


SUPPORTED_CLAUDE_MODELS = [
    ModelResponse(
        id="claude-opus-4-20250514",
        display_name="Claude Opus 4",
        created_at="2025-05-14T00:00:00Z",
        context_window=200_000,
        max_output_tokens=8192,
        supports_vision=True,
        supports_tools=True,
    ),
    ModelResponse(
        id="claude-sonnet-4-20250514",
        display_name="Claude Sonnet 4",
        created_at="2025-05-14T00:00:00Z",
        context_window=200_000,
        max_output_tokens=8192,
        supports_vision=True,
        supports_tools=True,
    ),
    ModelResponse(
        id="claude-haiku-4-20250514",
        display_name="Claude Haiku 4",
        created_at="2025-05-14T00:00:00Z",
        context_window=200_000,
        max_output_tokens=8192,
        supports_vision=True,
        supports_tools=True,
    ),
    ModelResponse(
        id="claude-3-opus-20240229",
        display_name="Claude 3 Opus",
        created_at="2024-02-29T00:00:00Z",
        context_window=200_000,
        max_output_tokens=4096,
        supports_vision=True,
        supports_tools=True,
    ),
    ModelResponse(
        id="claude-3-5-sonnet-20241022",
        display_name="Claude 3.5 Sonnet",
        created_at="2024-10-22T00:00:00Z",
        context_window=200_000,
        max_output_tokens=8192,
        supports_vision=True,
        supports_tools=True,
    ),
    ModelResponse(
        id="claude-3-haiku-20240307",
        display_name="Claude 3 Haiku",
        created_at="2024-03-07T00:00:00Z",
        context_window=200_000,
        max_output_tokens=4096,
        supports_vision=True,
        supports_tools=True,
    ),
    ModelResponse(
        id="claude-3-5-haiku-20241022",
        display_name="Claude 3.5 Haiku",
        created_at="2024-10-22T00:00:00Z",
        context_window=200_000,
        max_output_tokens=8192,
        supports_vision=True,
        supports_tools=True,
    ),
]


def get_proxy_service(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> ClaudeProxyService:
    """Build the request service for route handlers."""
    registry = getattr(request.app.state, "provider_registry", None)
    provider_registry = registry if isinstance(registry, ProviderRegistry) else None
    return ClaudeProxyService(
        settings,
        provider_getter=lambda provider_type: dependencies.resolve_provider(
            provider_type, app=request.app, settings=settings
        ),
        token_counter=get_token_count,
        provider_registry=provider_registry,
    )


def _probe_response(allow: str) -> Response:
    """Return an empty success response for compatibility probes."""
    return Response(status_code=204, headers={"Allow": allow})


def _discovered_model_response(
    model_id: str,
    *,
    display_name: str,
    context_window: int | None = None,
    max_output_tokens: int | None = None,
    supports_vision: bool | None = None,
    supports_tools: bool | None = None,
) -> ModelResponse:
    return ModelResponse(
        id=model_id,
        display_name=display_name,
        created_at=DISCOVERED_MODEL_CREATED_AT,
        context_window=context_window,
        max_output_tokens=max_output_tokens,
        supports_vision=supports_vision,
        supports_tools=supports_tools,
    )


def _append_unique_model(
    models: list[ModelResponse], seen: set[str], model: ModelResponse
) -> None:
    if model.id in seen:
        return
    seen.add(model.id)
    models.append(model)


def _append_provider_model_variants(
    models: list[ModelResponse],
    seen: set[str],
    provider_model_ref: str,
    *,
    supports_thinking: bool | None = None,
    context_window: int | None = None,
    max_output_tokens: int | None = None,
    supports_vision: bool | None = None,
    supports_tools: bool | None = None,
) -> None:
    if supports_thinking is not False:
        _append_unique_model(
            models,
            seen,
            _discovered_model_response(
                gateway_model_id(provider_model_ref),
                display_name=provider_model_ref,
                context_window=context_window,
                max_output_tokens=max_output_tokens,
                supports_vision=supports_vision,
                supports_tools=supports_tools,
            ),
        )
    _append_unique_model(
        models,
        seen,
        _discovered_model_response(
            no_thinking_gateway_model_id(provider_model_ref),
            display_name=f"{provider_model_ref} (no thinking)",
            context_window=context_window,
            max_output_tokens=max_output_tokens,
            supports_vision=supports_vision,
            supports_tools=supports_tools,
        ),
    )


def _resolve_model_info(
    provider_registry: ProviderRegistry | None,
    provider_id: str,
    model_id: str,
) -> tuple[bool | None, int | None, int | None, bool | None, bool | None]:
    """Resolve capability fields from the registry for a provider model ref.

    Returns (supports_thinking, context_window, max_output_tokens,
             supports_vision, supports_tools).
    All fields are ``None`` when the registry or model is unknown.
    """
    if provider_registry is None:
        return None, None, None, None, None
    info = provider_registry.cached_model_info(provider_id, model_id)
    if info is None:
        return None, None, None, None, None
    return (
        info.supports_thinking,
        info.context_window,
        info.max_output_tokens,
        info.supports_vision,
        info.supports_tools,
    )


def _build_models_list_response(
    settings: Settings, provider_registry: ProviderRegistry | None
) -> ModelsListResponse:
    models: list[ModelResponse] = []
    seen: set[str] = set()

    for ref in settings.configured_chat_model_refs():
        (
            supports_thinking,
            context_window,
            max_output_tokens,
            supports_vision,
            supports_tools,
        ) = _resolve_model_info(provider_registry, ref.provider_id, ref.model_id)
        _append_provider_model_variants(
            models,
            seen,
            ref.model_ref,
            supports_thinking=supports_thinking,
            context_window=context_window,
            max_output_tokens=max_output_tokens,
            supports_vision=supports_vision,
            supports_tools=supports_tools,
        )

    if provider_registry is not None:
        for model_info in provider_registry.cached_prefixed_model_infos():
            _append_provider_model_variants(
                models,
                seen,
                model_info.model_id,
                supports_thinking=model_info.supports_thinking,
                context_window=model_info.context_window,
                max_output_tokens=model_info.max_output_tokens,
                supports_vision=model_info.supports_vision,
                supports_tools=model_info.supports_tools,
            )

    for model in SUPPORTED_CLAUDE_MODELS:
        _append_unique_model(models, seen, model)

    return ModelsListResponse(
        data=models,
        first_id=models[0].id if models else None,
        has_more=False,
        last_id=models[-1].id if models else None,
    )


# =============================================================================
# Routes
# =============================================================================
@router.post("/v1/messages", tags=["messages"])
async def create_message(
    request_data: MessagesRequest,
    service: ClaudeProxyService = Depends(get_proxy_service),
    _auth=Depends(require_api_key),
):
    """Create a message (always streaming)."""
    return service.create_message(request_data)


@router.api_route("/v1/messages", methods=["HEAD", "OPTIONS"], tags=["messages"])
async def probe_messages(_auth=Depends(require_api_key)):
    """Respond to Claude compatibility probes for the messages endpoint."""
    return _probe_response("POST, HEAD, OPTIONS")


@router.post("/v1/messages/count_tokens", tags=["messages"])
async def count_tokens(
    request_data: TokenCountRequest,
    service: ClaudeProxyService = Depends(get_proxy_service),
    _auth=Depends(require_api_key),
):
    """Count tokens for a request."""
    return service.count_tokens(request_data)


@router.api_route(
    "/v1/messages/count_tokens", methods=["HEAD", "OPTIONS"], tags=["messages"]
)
async def probe_count_tokens(_auth=Depends(require_api_key)):
    """Respond to Claude compatibility probes for the token count endpoint."""
    return _probe_response("POST, HEAD, OPTIONS")


@router.get("/", tags=["system"])
async def root(
    settings: Settings = Depends(get_settings), _auth=Depends(require_api_key)
):
    """Root endpoint."""
    return {
        "status": "ok",
        "provider": settings.provider_type,
        "model": settings.model,
    }


@router.api_route("/", methods=["HEAD", "OPTIONS"], tags=["system"])
async def probe_root():
    """Respond to unauthenticated local compatibility probes for the root endpoint."""
    return _probe_response("GET, HEAD, OPTIONS")


@router.get("/health", tags=["health"])
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


@router.api_route("/health", methods=["HEAD", "OPTIONS"], tags=["health"])
async def probe_health():
    """Respond to compatibility probes for the health endpoint."""
    return _probe_response("GET, HEAD, OPTIONS")


@router.get("/v1/models", response_model=ModelsListResponse, tags=["models"])
async def list_models(
    request: Request,
    settings: Settings = Depends(get_settings),
    _auth=Depends(require_api_key),
):
    """List the model ids this proxy advertises to Claude-compatible clients."""
    trace_event(stage="ingress", event="api.models.list", source="api")
    registry = getattr(request.app.state, "provider_registry", None)
    provider_registry = registry if isinstance(registry, ProviderRegistry) else None
    return _build_models_list_response(settings, provider_registry)


@router.post("/stop", tags=["system"])
async def stop_cli(request: Request, _auth=Depends(require_api_key)):
    """Stop all CLI sessions and pending tasks."""
    handler = getattr(request.app.state, "message_handler", None)
    if not handler:
        # Fallback if messaging not initialized
        cli_manager = getattr(request.app.state, "cli_manager", None)
        if cli_manager:
            await cli_manager.stop_all()
            logger.info("STOP_CLI: source=cli_manager cancelled_count=N/A")
            return {"status": "stopped", "source": "cli_manager"}
        raise HTTPException(status_code=503, detail="Messaging system not initialized")

    count = await handler.stop_all_tasks()
    trace_event(
        stage="ingress",
        event="api.cli.stop_via_handler",
        source="api",
        cancelled_nodes=count,
    )
    logger.info("STOP_CLI: source=handler cancelled_count={}", count)
    return {"status": "stopped", "cancelled_count": count}
