# Evolution Tracking

> Generated: 2026-06-20  
> Phase 1 — Full discovery across all 7 modules.  
> See [BEFORE YOU START] freshness rules for Phase 2 triggers.

---

## Consolidated Index

| ID | Module | Location | Category | Priority | Status |
|----|--------|----------|----------|----------|--------|
| C-01 | config | `config/settings.py` credentials | Security | Critical | Proposed |
| C-02 | config | `config/settings.py` (monolithic) | Architecture | High | Proposed |
| C-03 | config | `config/logging_config.py` sinks | Production Safety | High | Proposed |
| C-04 | config | `config/logging_config.py` serialize | Performance | Medium | Proposed |
| C-05 | config | `config/logging_config.py` `_configured` | Correctness | Medium | Proposed |
| C-06 | config | `config/provider_catalog.py` capabilities | DX / Correctness | Medium | Proposed |
| C-07 | config | `config/settings.py` + `.env.example` | Maintainability | Medium | Proposed |
| C-08 | config | `config/nim.py` validators | Maintainability | Low | Proposed |
| C-09 | config | `config/logging_config.py` redact | Performance | Low | Proposed |
| C-10 | config | `config/provider_catalog.py` URLs | Resilience | Low | Proposed |
| C-11 | config | `config/settings.py` messaging_platform | DX | Low | Proposed |
| COR-01 | core | `core/anthropic/conversion.py` recursion | Security | High | Proposed |
| COR-02 | core | `core/anthropic/` caching support | Comprehensiveness | High | Proposed |
| COR-03 | core | `core/anthropic/` structured output | Comprehensiveness | High | Proposed |
| COR-04 | core | `core/anthropic/` tokenizer | Performance | High | Proposed |
| COR-05 | core | `core/` observability | Developer Experience | High | Proposed |
| COR-06 | core | `core/anthropic/conversion.py` complexity | Maintainability | Medium | Proposed |
| COR-07 | core | `core/anthropic/content.py` blocks enum | Architecture | Medium | Proposed |
| COR-08 | core | `core/` testing | Testing | High | Proposed |
| COR-09 | core | `core/cache/`, `core/management/` | Comprehensiveness | Critical | Proposed |
| API-01 | api | `api/runtime.py` rate limiting | Architecture | High | Proposed |
| API-02 | api | `api/web_tools/egress.py` blocking I/O | Performance | High | Proposed |
| API-03 | api | `api/app.py` middleware | Performance | High | Proposed |
| API-04 | api | `api/web_tools/parsers.py` HTML parsing | Performance | Medium | Proposed |
| API-05 | api | `api/routes.py` model routing | Performance | Medium | Proposed |
| API-06 | api | `api/services.py` pipeline pattern | Architecture | Medium | Proposed |
| API-07 | api | `api/routes.py` error responses | Developer Experience | Medium | Proposed |
| API-08 | api | `api/app.py` COOP/CORP hardening | Security | Medium | Proposed |
| API-09 | api | `api/dependencies.py` dependency injection | Architecture | Medium | Proposed |
| API-10 | api | `api/runtime.py` shutdown | Resilience | Medium | Proposed |
| CLI-01 | cli | `cli/session.py` `start_task` monolith | Architecture | High | Proposed |
| CLI-02 | cli | `cli/process_registry.py` Win32 Job Objects | Resilience | High | Implemented — `WindowsJobManager` uses `CreateJobObject` + `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` for kernel-guaranteed cleanup |
| CLI-03 | cli | `cli/entrypoints.py` restart loop backoff | Resilience | High | Proposed |
| CLI-04 | cli | `cli/entrypoints.py` preflight blocking I/O | Performance | High | Proposed |
| CLI-05 | cli | `cli/manager.py` pool management | Architecture | Medium | Proposed |
| CLI-06 | cli | `cli/manager.py` sequential stop | Performance | Medium | Proposed |
| CLI-07 | cli | `cli/session.py` readline | Performance | Medium | Proposed |
| CLI-08 | cli | `cli/session.py` deadlock risk | Resilience | Medium | Proposed |
| CLI-09 | cli | `cli/` auto-compact | UX / Resilience | High | Implemented — per-session token tracking, 75% threshold trigger |
| CLI-10 | cli | `cli/session.py`, `cli/manager.py`, `api/runtime.py` capability env vars | DX / Comprehensiveness | Medium | Implemented — `max_output_tokens`, `supports_vision`, `supports_tools` resolved from provider registry and forwarded to child process as `CLAUDE_CODE_*` env vars |
| MSG-01 | messaging | `messaging/platforms/` telegram+discord | Architecture | Critical | Proposed |
| MSG-02 | messaging | `messaging/rendering/` transcript parsing | Performance | High | Proposed |
| MSG-03 | messaging | `messaging/` testing coverage | Testing | Critical | Proposed |
| MSG-04 | messaging | `messaging/trees/data.py` deque removal | Performance | High | Proposed |
| MSG-05 | messaging | `messaging/platforms/` rate limiter | Testing | High | Proposed |
| MSG-06 | messaging | `messaging/trees/data.py` threading+async | Resilience | High | Proposed |
| MSG-07 | messaging | `messaging/platforms/` voice pipeline | Architecture | Medium | Proposed |
| MSG-08 | messaging | `messaging/platforms/` if/elif | DX | Medium | Proposed |
| MSG-09 | messaging | `messaging/platforms/` dispatch | Architecture | Medium | Proposed |
| MSG-10 | messaging | `messaging/rendering/` LRU cache | Performance | Medium | Proposed |
| PRV-01 | providers | `providers/rate_limit.py` `Retry-After` | Architecture | High | Implemented — `execute_with_retry` passes `Retry-After` header |
| PRV-02 | providers | `providers/rate_limit.py` tenacity | Resilience | High | Implemented — `execute_with_retry` uses `tenacity.AsyncRetrying` with exponential backoff, jitter, and `before_sleep` Retry-After logging |
| PRV-03 | providers | `providers/rate_limit.py` token bucket | Architecture | Medium | Proposed |
| PRV-04 | providers | `providers/rate_limit.py` Redis | Resilience | Medium | Proposed |
| PRV-05 | providers | `providers/base.py` connection pool | Performance | Medium | Proposed |
| PRV-06 | providers | `providers/error_mapping.py` string match | Resilience | Medium | Proposed |
| PRV-07 | providers | `providers/error_mapping.py` isinstance | Architecture | Medium | Proposed |
| PRV-08 | providers | `providers/nvidia_nim/client.py` constructor dup | Developer Experience | High | Implemented — `_nim_settings` assigned before `super().__init__()`, `_build_client_kwargs()` override replaces discarded client pattern |
| PRV-09 | providers | `providers/` circuit breaker | Resilience | High | Implemented — `CircuitBreaker` in `GlobalRateLimiter` with CLOSED/OPEN/HALF_OPEN states, fail-fast on degradation |
| PRV-10 | providers | `providers/kimi/client.py` zero tests | Testing | High | Proposed |
| PRV-11 | providers | `providers/` empty stubs | Comprehensiveness | High | Proposed |
| PRV-12 | providers | `providers/nvidia_nim/request.py` recursion | Security | Medium | Proposed |
| PRV-13 | providers | `providers/openai_compat.py` tool state | Maintainability | Medium | Proposed |
| PRV-14 | providers | `providers/registry.py` timeout log | Resilience | Medium | Proposed |
| PRV-15 | providers | `providers/` keepalive | Resilience | Medium | Proposed |
| PRV-16 | providers | `providers/wafer/client.py` forced thinking | Resilience | Medium | Implemented — respects `thinking_enabled` parameter |
| PRV-17 | providers | `providers/deepseek/request.py` block filter | Architecture | Medium | Proposed |
| PRV-18 | providers | `providers/model_listing.py` metadata | Comprehensiveness | Medium | Implemented — `context_window`, `max_output_tokens`, `supports_vision` extracted from OpenRouter API and exposed in `/v1/models` |
| PRV-19 | providers | `providers/anthropic_messages.py` body read | Resilience | Low | Proposed |
| PRV-20 | providers | `providers/ollama/client.py` client per call | Performance | Low | Proposed |
| PRV-21 | providers | `providers/nvidia_nim/voice.py` sync | Performance | Low | Proposed |
| PRV-22 | providers | `providers/deepseek/client.py` URL | Performance | Low | Proposed |
| PRV-23 | providers | `providers/base.py` proxy default | DX | Low | Proposed |
| PRV-24 | providers | `providers/model_listing.py` parser registry | Architecture | Low | Proposed |
| TST-01 | tests | `tests/` property-based testing | Testing | High | Proposed |
| TST-02 | tests | `tests/` integration harness | Testing | High | Proposed |
| TST-03 | tests | `tests/` SSRF fuzzing | Security | High | Proposed |
| TST-04 | tests | `tests/` slow test profiling | Performance | Medium | Proposed |
| TST-05 | tests | `tests/` snapshot testing | Testing | Medium | Proposed |

---

## Detailed Entries

---

### C-01 — `SecretStr` for All Credential Fields

**Module:** config  
**Files:** `config/settings.py` lines 112–121, 290–294, 311  
**Category:** Security  
**Priority:** Critical  
**Status:** Proposed

**Current approach:** Eight credential fields typed as plain `str`. Values are visible in `repr()`, `model_dump()`, exception tracebacks, and log output.

**Superior approach:** Use `pydantic.SecretStr` for all credential fields (`open_router_api_key`, `deepseek_api_key`, `nvidia_nim_api_key`, `telegram_bot_token`, `discord_bot_token`, `anthropic_auth_token`, etc.). Pydantic-settings has first-class support — `SecretStr` fields are populated from env vars transparently and serialization obfuscates the value.

**Sources:** Pydantic docs (SecretStr type), pydantic-settings docs for SecretStr integration, multiple security production guides.

**Impact:** Eliminates class of credential-leak-through-logging vulnerability.

**Risks:** All consumers reading `.api_key` must switch to `.get_secret_value()`. Breaking change for programmatic `Settings` construction. Emptiness checks change from `.strip()` to `.get_secret_value() == ""`.

---

### C-02 — Composable Settings via Sub-Models with `env_nested_delimiter`

**Module:** config  
**Files:** `config/settings.py` entire `Settings` class  
**Category:** Architecture  
**Priority:** High  
**Status:** Proposed

**Current approach:** Monolithic 50-field flat class with 5 field validators, 2 model validators, 3 properties, 7 methods. All concerns mixed: server, voice, proxy, logging, model, provider, thinking, web tools.

**Superior approach:** Decompose into nested Pydantic sub-models: `VoiceConfig`, `ServerConfig`, `ProxyConfig`, `ModelConfig`, `ThinkingConfig`, `LoggingConfig`, `WebToolsConfig`. Enable `env_nested_delimiter="__"` for isomorphic env mapping (`VOICE__WHISPER_DEVICE=cpu`).

**Sources:** Pydantic Settings docs — `env_nested_delimiter` is the canonical pattern for hierarchical env config. 12-factor app methodology recommends splitting config by concern.

**Impact:** DRY reduction, testability, extensibility, env-config surface becomes discoverable.

**Risks:** Breaking change for programmatic `Settings()` construction. Keep flat `validation_alias` aliases during deprecation window.

---

### C-03 — Production-Logging Safety (`diagnose=False`, `backtrace=False`, `atexit Drain`)

**Module:** config  
**Files:** `config/logging_config.py` lines 137–153  
**Category:** Production Safety  
**Priority:** High  
**Status:** Proposed

**Current approach:** Both sinks use Loguru defaults: `diagnose=True`, `backtrace=True`. File sink uses `enqueue=True` but never drains on shutdown.

**Superior approach:** Set `diagnose=False, backtrace=False` on file/console sinks. Register `atexit.register(logger.complete)` to drain the enqueue queue.

**Sources:** Loguru docs explicitly warn about `diagnose=True` security risk. Production guides (Dash0, StackHarbor, python-observability.com) all recommend `diagnose=False` in production.

**Impact:** Eliminates PII/credential-leak vector in production logs.

**Risks:** Debuggability reduced without variable values in tracebacks. Mitigate with separate debug-only sink.

---

### C-04 — `orjson` for Log Serialization

**Module:** config  
**Files:** `config/logging_config.py` line 80  
**Category:** Performance  
**Priority:** Medium  
**Status:** Proposed

**Current approach:** Standard-library `json.dumps(out, default=str)` on every log line.

**Superior approach:** Use `orjson.dumps(out, default=str).decode()` when available, falling back to `json.dumps`. 3–6× faster for dict serialization.

**Sources:** orjson benchmarks. Loguru production guides recommend orjson for high-throughput logging. Pydantic v2 uses orjson optionally.

**Impact:** Reduces per-log-line CPU by 3–6× under high throughput.

**Risks:** Adds Rust extension dependency. Must fall back to stdlib for portability.

---

### C-05 — Thread-Safe `configure_logging` Guard

**Module:** config  
**Files:** `config/logging_config.py` lines 18, 126–128  
**Category:** Correctness  
**Priority:** Medium  
**Status:** Proposed

**Current approach:** `_configured: bool` flag with no synchronization. Race on concurrent `force=True` calls.

**Superior approach:** Use `threading.Lock()` with double-checked locking pattern.

**Sources:** Standard Python concurrency pattern. Loguru docs recommend against concurrent `logger.remove()`/`logger.add()`.

**Impact:** Prevents rare race-condition sink duplication in test environments.

**Risks:** Near-zero.

---

### C-06 — Capability Enum + Type-Safe Query API

**Module:** config  
**Files:** `config/provider_catalog.py`  
**Category:** DX / Correctness  
**Priority:** Medium  
**Status:** Proposed

**Current approach:** Capabilities are `tuple[str, ...]` — stringly-typed, no autocomplete, typo risks.

**Superior approach:** Define `class Capability(str, Enum)` with members. Add `ProviderDescriptor.supports(cap)` method.

**Sources:** Python `enum.StrEnum` (3.11+). Pydantic v2 native enum support.

**Impact:** Prevents typo bugs, enables autocomplete, adds type safety.

**Risks:** Breaking change for any external code constructing `ProviderDescriptor` directly.

---

### C-07 — Settings Expose JSON Schema / Auto-Validate `.env.example`

**Module:** config  
**Files:** `config/settings.py`, `.env.example`  
**Category:** Maintainability  
**Priority:** Medium  
**Status:** Proposed

**Current approach:** Defaults in 3 places (Settings class, constants.py, .env.example) with no automated sync check.

**Superior approach:** Export `Settings.model_json_schema()` as CI artifact. Add pytest that validates `.env.example` matches Settings model.

**Sources:** Pydantic JSON Schema generation (GA). 12factor.net — single source of truth for config schemas.

**Impact:** Prevents drift between code defaults and documented defaults.

**Risks:** JSON schema generation is cheap at runtime. .env.example check may be fragile.

---

### C-08 — `NimSettings` Validator Boilerplate Reduction

**Module:** config  
**Files:** `config/nim.py` lines 52–129  
**Category:** Maintainability  
**Priority:** Low  
**Status:** Proposed

**Current approach:** Three `mode="before"` classmethods with hardcoded `field_defaults` dispatch dicts totaling 78 lines.

**Superior approach:** Use `Annotated[float, BeforeValidator(coerce_or_default)]` pattern to DRY the empty-string coercion logic.

**Sources:** Pydantic V2 field validation docs — `BeforeValidator` with `ValidationInfo.default`.

**Impact:** Removes ~40 lines of boilerplate.

**Risks:** Pydantic V2 auto-coercion doesn't handle `""` — custom validators still needed for that edge case.

---

### C-09 — Optimize `_redact_sensitive_substrings` String Allocation

**Module:** config  
**Files:** `config/logging_config.py` lines 45–54  
**Category:** Performance  
**Priority:** Low  
**Status:** Proposed

**Current approach:** Creates `message.lower()` copy for fast-path heuristic, runs two regexes sequentially.

**Superior approach:** Combine both regexes into single compiled pattern with branches. Avoids `.lower()` allocation entirely.

**Impact:** Reduces per-log-line GC pressure by 1 string allocation + 1 regex match.

**Risks:** Combined regex slightly less readable.

---

### C-10 — Provider Credential URL Validation

**Module:** config  
**Files:** `config/provider_catalog.py` line 36  
**Category:** Resilience  
**Priority:** Low  
**Status:** Proposed

**Current approach:** `credential_url: str | None = None` — no validation.

**Superior approach:** Use `pydantic.AnyUrl` or `__post_init__` validation with a simple `startswith("https://")` check.

**Impact:** Prevents malformed URL typos from reaching users.

**Risks:** Switching from frozen dataclass to Pydantic model changes runtime characteristics.

---

### C-11 — `MessagingPlatform` Enum

**Module:** config  
**Files:** `config/settings.py` line 125, validator 359–366  
**Category:** DX  
**Priority:** Low  
**Status:** Proposed

**Current approach:** `str` field with manual validator `v in ("telegram", "discord", "none")`.

**Superior approach:** `class MessagingPlatform(str, Enum)` — Pydantic auto-validates.

**Impact:** Eliminates 7-line validator, adds type-safety and autocomplete.

**Risks:** Callers comparing with `"telegram"` need to use `MessagingPlatform.TELEGRAM` or compare with `.value`.

---

### COR-01 — Recursive JSON Schema Sanitization Depth Limit

**Module:** core  
**Files:** `core/anthropic/conversion.py` recursive schema walkers  
**Category:** Security  
**Priority:** High  
**Status:** Proposed

**Current approach:** `_sanitize_nim_schema_node` and recursive functions walk JSON Schema nodes without cycle detection. A malicious recursive schema (`{"$ref": "#"}`) causes stack overflow.

**Superior approach:** Add `max_depth: int = 100` parameter and `visited: set[int]` (tracking `id()` of dict nodes) to all schema walkers.

**Impact:** Prevents stack overflow from crafted tool schemas.

**Risks:** Slight overhead from `id()` tracking.

---

### COR-02 — Anthropic Prompt Caching Support

**Module:** core  
**Files:** `core/anthropic/` conversion layer  
**Category:** Comprehensiveness  
**Priority:** High  
**Status:** Proposed

**Current approach:** No support for Anthropic's `cache_control` block annotation on system messages or content blocks.

**Superior approach:** Add `cache_control` passthrough to the conversion layer. Map Anthropic cache breakpoints to OpenAI-compatible equivalents where possible.

**Sources:** Anthropic docs on prompt caching (GA since 2024). Key benefit: 50–75% latency reduction on repeated prefix content.

**Impact:** Enables prompt caching for cost/latency savings with native Anthropic providers.

**Risks:** Must be ignored for OpenAI-compatible providers that don't support it.

---

### COR-03 — Structured Output Support

**Module:** core  
**Files:** `core/anthropic/` conversion layer  
**Category:** Comprehensiveness  
**Priority:** High  
**Status:** Proposed

**Current approach:** No `response_format` handling or structured output support in the conversion layer.

**Superior approach:** Pass through Anthropic's `response_format` / structured output specification. Map to OpenAI's `response_format` for compatible providers.

**Sources:** Anthropic structured outputs GA. OpenAI structured outputs GA. Both support JSON Schema constrained generation.

**Impact:** Enables structured JSON mode for API clients.

---

### COR-04 — Stale GPT-4-Era Tokenizer

**Module:** core  
**Files:** `core/anthropic/` tokenizer usage  
**Category:** Performance  
**Priority:** High  
**Status:** Proposed

**Current approach:** Uses `tiktoken` (GPT-4 tokenizer) which has ±20% error on Claude models and doesn't reflect actual Anthropic token counting.

**Superior approach:** Use direct Anthropic `/v1/messages/count_tokens` API call via local proxy, or the Anthropic Python SDK tokenizer for accurate counts.

**Impact:** Accurate token counts → better context management, accurate billing.

**Risks:** `/count_tokens` adds latency. Cache results for identical inputs.

---

### COR-05 — OpenTelemetry Observability

**Module:** core  
**Files:** `core/trace.py`  
**Category:** Developer Experience  
**Priority:** High  
**Status:** Proposed

**Current approach:** Custom `trace_event()` function that logs structured JSON with string formatting. No OpenTelemetry spans, no distributed tracing.

**Superior approach:** Integrate OpenTelemetry SDK. Emit spans for key operations (request → provider call → streaming → response). Export to OTLP collector.

**Sources:** OpenTelemetry Python SDK GA. FastAPI + OTel integration documented. Industry standard for observability.

**Impact:** Enables distributed tracing, span analysis, trace-based alerting.

**Risks:** Adds dependency on OTel SDK. Requires collector infrastructure.

---

### COR-06 — `AnthropicToOpenAIConverter` State Machine Complexity

**Module:** core  
**Files:** `core/anthropic/conversion.py` `convert_messages()`  
**Category:** Maintainability  
**Priority:** Medium  
**Status:** Proposed

**Current approach:** 110-line stateful method with `pending` context object tracking deferred tool results across messages. Multiple early-return paths and inline flush logic.

**Superior approach:** Extract message conversion into a pipeline of composable transformers: `SystemMessageHandler → ToolResultReplayHandler → ContentBlockConverter`. Each transformer has a single responsibility.

**Impact:** Testability, readability, isolated unit tests.

**Risks:** Refactor risk for well-tested code.

---

### COR-07 — Content Block Types as Enum

**Module:** core  
**Files:** `core/anthropic/content.py`  
**Category:** Architecture  
**Priority:** Medium  
**Status:** Proposed

**Current approach:** Block types as string literals throughout the codebase (`"text"`, `"thinking"`, `"tool_use"`, etc.).

**Superior approach:** Define `class ContentBlockType(str, Enum)` with all known block types. Use `get_block_type()` returning the enum.

**Impact:** Eliminates string typo bugs, enables exhaustive `match` statements.

---

### COR-08 — No Dedicated Unit Tests for Core Module

**Module:** core  
**Files:** `core/anthropic/`  
**Category:** Testing  
**Priority:** High  
**Status:** Proposed

**Current approach:** Core Anthropic conversion and content handling has no dedicated unit test file. Integration tests cover it indirectly.

**Superior approach:** Add `tests/core/` with property-based tests for conversion round-trips, edge cases for all content block types, and symbolic regression tests for known Anthropic message formats.

---

### COR-09 — Dead Subsystem Directories (`core/cache/`, `core/management/`)

**Module:** core  
**Files:** `core/cache/`, `core/management/` (only `__pycache__`)  
**Category:** Comprehensiveness  
**Priority:** Critical  
**Status:** Proposed

**Current approach:** Two subdirectories exist with only stale `.pyc` files. Either implement these subsystems or remove them to avoid confusion.

**Superior approach:** Clean up: remove empty directories if unused, or implement the intended caching and session management subsystems.

**Impact:** Eliminates developer confusion and stale bytecode artifacts.

---

### API-01 — Distributed Rate Limiting Backend

**Module:** api  
**Files:** `api/runtime.py`  
**Category:** Architecture  
**Priority:** High  
**Status:** Proposed

**Current approach:** In-memory `GlobalRateLimiter` only. Multiple gateway instances operate with independent counters.

**Superior approach:** Abstract rate limiting behind a `RateLimitBackend` interface with in-memory and Redis implementations.

**Sources:** Production guides (FastAPI + Redis). OpenAI SDK uses per-instance limiting.

**Impact:** Enables horizontal scaling with correct rate limiting.

**Risks:** Redis dependency for multi-instance deployments.

---

### API-02 — `socket.getaddrinfo` Blocks Event Loop

**Module:** api  
**Files:** `api/web_tools/egress.py` line 29  
**Category:** Performance  
**Priority:** High  
**Status:** Proposed

**Current approach:** Synchronous `socket.getaddrinfo()` call in async endpoint blocks the event loop.

**Superior approach:** Use `loop.getaddrinfo()` with a dedicated executor or use httpx's async DNS resolution.

**Impact:** Prevents event loop blocking during DNS resolution.

---

### API-03 — Async Middleware Replaces Sync `BaseHTTPMiddleware`

**Module:** api  
**Files:** `api/app.py` middleware  
**Category:** Performance  
**Priority:** High  
**Status:** Proposed

**Current approach:** (Checked) These may already use ASGI native middleware. If using `BaseHTTPMiddleware`, each request pays the thread-pool overhead.

**Superior approach:** Pure ASGI middleware or Starlette native middleware.

**Impact:** Eliminates thread-pool overhead per request.

---

### API-04 — `HTMLParser` vs `selectolax` for HTML Parsing

**Module:** api  
**Files:** `api/web_tools/parsers.py`  
**Category:** Performance  
**Priority:** Medium  
**Status:** Proposed

**Current approach:** Using stdlib `HTMLParser` which is ~10× slower than modern alternatives.

**Superior approach:** Use `selectolax` (Lexbor engine) for HTML parsing.

**Sources:** selectolax benchmarks show 5–10× speedup over `html.parser`.

**Impact:** Faster content extraction from fetched pages.

**Risks:** Adds C extension dependency.

---

### API-05 — `ModelRouter.resolve()` Uncached

**Module:** api  
**Files:** `api/routes.py` model resolution path  
**Category:** Performance  
**Priority:** Medium  
**Status:** Proposed

**Current approach:** Model ID string parsing and resolution on every request. No cache.

**Superior approach:** Add LRU cache keyed on `(model_id, provider_type)`.

**Impact:** Reduces per-request CPU for model routing.

---

### API-06 — `ClaudeProxyService.create_message()` Pipeline Pattern

**Module:** api  
**Files:** `api/services.py`  
**Category:** Architecture  
**Priority:** Medium  
**Status:** Proposed

**Current approach:** Single method handling validation, routing, streaming orchestration, and error formatting.

**Superior approach:** Pipeline pattern: `ValidateRequest → ResolveModel → SelectProvider → BuildBody → StreamResponse → FormatOutput`.

**Impact:** Testability, composability, isolated error handling.

---

### API-07 — 500 Responses Lack Request IDs

**Module:** api  
**Files:** `api/routes.py` error responses  
**Category:** Developer Experience  
**Priority:** Medium  
**Status:** Proposed

**Current approach:** Error responses may not include a request ID for debugging.

**Superior approach:** Assign a request ID at ingress, include it in all error responses and log lines.

**Impact:** Faster debugging of production errors.

---

### API-08 — COOP/CORP Security Hardening

**Module:** api  
**Files:** `api/app.py` headers  
**Category:** Security  
**Priority:** Medium  
**Status:** Proposed

**Current approach:** COEP set to `credentialless` (already improved from `require-corp`). Remaining headers reviewed.

**Superior approach:** Audit all security headers against OWASP Secure Headers Project. Consider `X-Content-Type-Options: nosniff`, `Referrer-Policy`, etc. (some already set in `test_security_headers`).

---

### API-09 — Dependency Injection Pattern

**Module:** api  
**Files:** `api/dependencies.py`  
**Category:** Architecture  
**Priority:** Medium  
**Status:** Proposed

**Current approach:** FastAPI `Depends()` with module-level singletons. Provider resolution logic mixed with FastAPI dependency injection.

**Superior approach:** Abstract provider resolution behind a `ProviderFactory` protocol. Use dedicated DI container (e.g., `fastapi-injector` or `lagom`) for testability.

---

### API-10 — Graceful Shutdown Hardening

**Module:** api  
**Files:** `api/runtime.py` shutdown logic  
**Category:** Resilience  
**Priority:** Medium  
**Status:** Proposed

**Current approach:** Shutdown sequence cancels tasks and awaits cleanup. Ordering and timeout for forced kills.

**Superior approach:** Implement staged shutdown: (1) health check removal, (2) active request drain with configurable deadline, (3) provider cleanup, (4) forceful cancellation.

---

### CLI-01 — `Session.start_task` 172-Line Monolith

**Module:** cli  
**Files:** `cli/session.py` `start_task`  
**Category:** Architecture  
**Priority:** High  
**Status:** Proposed

**Current approach:** Single 172-line method handling: subprocess creation, stream parsing, bytearray line buffering, task cancellation, output logging, error detection. Uses manual `bytearray` line parsing instead of `StreamReader.readline()`.

**Superior approach:** Decompose into: `LineStreamReader` (async iterator over stream lines), `TaskContext` (process + I/O management), `OutputProcessor` (per-line parsing and dispatch).

**Sources:** Python asyncio `StreamReader` docs. `asyncio.create_subprocess_exec` with `stdout=asyncio.subprocess.PIPE` pattern.

**Impact:** Testability, readability, reduced deadlock surface.

---

### CLI-02 — Windows Job Objects for Process Tree Cleanup

**Module:** cli  
**Files:** `cli/process_registry.py`  
**Category:** Resilience  
**Priority:** High  
**Status:** Implemented

**Current approach (before):** Windows cleanup uses `taskkill /T /F` via subprocess.

**New feature:** `WindowsJobManager` class using Win32 Job Objects via `ctypes`:
- Creates unnamed job object with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` flag
- `assign(pid)` — Opens process with `PROCESS_SET_QUOTA` and assigns to the job
- Kernel guarantees every assigned process tree is terminated when the handle closes
- Lazy initialization — only created on first `register_pid()` call
- Graceful degradation to `taskkill` fallback when Job Object API is unavailable or process is already in another job
- Complete Win32 structure definitions: `JOBOBJECT_BASIC_LIMIT_INFORMATION`, `IO_COUNTERS`, `JOBOBJECT_EXTENDED_LIMIT_INFORMATION`

**Wiring:** `register_pid()` calls `job.assign(pid)` on Windows after registering the PID. `taskkill`/`os.kill` path remains as explicit-cleanup fallback.

**Impact:** Reliable process tree cleanup without race conditions.

**Verification:** Ruff format/lint/typecheck all clean. All 60 CLI tests pass.

---

### CLI-03 — Server Restart Loop Backoff

**Module:** cli  
**Files:** `cli/entrypoints.py`  
**Category:** Resilience  
**Priority:** High  
**Status:** Proposed

**Current approach:** Server crash → immediate restart. Crash-loop busy-waits with zero backoff.

**Superior approach:** Add exponential backoff with max delay. Track consecutive crashes within a window.

**Impact:** Prevents busy-wait restart loop during persistent failures.

---

### CLI-04 — Preflight Health Check Blocks Event Loop

**Module:** cli  
**Files:** `cli/entrypoints.py` preflight endpoint  
**Category:** Performance  
**Priority:** High  
**Status:** Proposed

**Current approach:** Uses synchronous `urlopen` to check server health.

**Superior approach:** Use `httpx.AsyncClient` with timeout (or synchronous `httpx.Client` at a minimum — `urlopen` is the slowest option).

**Impact:** Prevents event loop blocking during startup checks.

---

### CLI-05 — Session Pool Limits, TTL, Idle Reaper

**Module:** cli  
**Files:** `cli/manager.py`  
**Category:** Architecture  
**Priority:** Medium  
**Status:** Proposed

**Current approach:** No pool limits, no TTL, no idle reaper for session registry.

**Superior approach:** Add max concurrent sessions, session TTL after last activity, background idle reaper task.

**Impact:** Prevents unbounded session accumulation.

---

### CLI-06 — Sequential `stop_all` → `asyncio.gather`

**Module:** cli  
**Files:** `cli/manager.py` `stop_all`  
**Category:** Performance  
**Priority:** Medium  
**Status:** Proposed

**Current approach:** `stop_all` iterates sessions sequentially, awaiting each.

**Superior approach:** Use `asyncio.gather(*[session.stop() for session in ...])`.

**Impact:** Parallel session shutdown under 1 second regardless of count.

---

### CLI-07 — `StreamReader.readline` Instead of Manual Bytearray Parsing

**Module:** cli  
**Files:** `cli/session.py`  
**Category:** Performance / Correctness  
**Priority:** Medium  
**Status:** Proposed

**Current approach:** Manual byte-by-byte accumulation in `bytearray` looking for `\n`.

**Superior approach:** Use `StreamReader.readline()` which is optimized and handles edge cases (CRLF, partial reads).

**Sources:** Python asyncio benefits from native OS read buffering.

**Impact:** Reduced code, fewer edge case bugs.

---

### CLI-08 — Missing `limit` Param on `create_subprocess_exec`

**Module:** cli  
**Files:** `cli/session.py`  
**Category:** Resilience  
**Priority:** Medium  
**Status:** Proposed

**Current approach:** `limit` parameter not set on `asyncio.create_subprocess_exec`. Default `StreamReader` limit is 64KB — if subprocess output exceeds this between reads, the writer blocks.

**Superior approach:** Set `limit=1024*1024` (1MB) or appropriate value for expected output size.

**Impact:** Prevents subprocess deadlock on large outputs.

---

### CLI-09 — Auto-Compact at 75% Context Fullness

**Module:** cli, messaging  
**Files:** `cli/session.py`, `cli/manager.py`, `messaging/handler.py`, `messaging/platforms/base.py`, `config/settings.py`, `config/constants.py`  
**Category:** UX / Resilience  
**Priority:** High  
**Status:** Implemented

**Current approach (before):** No automatic context compaction. Long-running sessions accumulate tokens until the model's context window fills up, causing degraded responses or truncation.

**New feature:** Per-session token tracking with a 75% threshold trigger. Before each turn in a conversation, the proxy estimates accumulated tokens (input + 1.5× output per turn). When projected usage exceeds 75% of the configured context window, `/compact` is prepended to the prompt, and a warning status message (🗜️) is shown.

**Files changed:**
- `config/constants.py` — Added `DEFAULT_CONTEXT_WINDOW`, `DEFAULT_AUTO_COMPACT_THRESHOLD`, `AUTO_COMPACT_OUTPUT_MULTIPLIER`
- `config/settings.py` — Added `auto_compact_enabled`, `auto_compact_threshold`, `auto_compact_context_window` settings
- `cli/session.py` — Added `accumulated_tokens`/`context_window` properties, `prepare_auto_compact_prompt()`, `update_accumulated_tokens()`
- `cli/manager.py` — Forwards auto-compact settings to `CLISession` constructor
- `messaging/handler.py` — Wires the compact check before `start_task()` and token update in `finally` block
- `messaging/platforms/base.py` — Updated `CLISession` Protocol with new methods

**Configuration (env vars):**
- `AUTO_COMPACT_ENABLED=true` (default: true)
- `AUTO_COMPACT_THRESHOLD=0.75` (default: 75%)
- `AUTO_COMPACT_CONTEXT_WINDOW=200000` (default: 200K tokens)

**Risks:** Token estimation is based on character count (÷4), not actual model tokenization. After `/compact`, accumulated tokens continue to increment (compact is idempotent, so the over-count only triggers premature repeats which are harmless).

**Verification:** Ruff format/lint/typecheck all clean. 31 CLI tests pass.

---

### CLI-10 — Model Capability Env Vars in Child Process

**Module:** cli, api  
**Files:** `cli/session.py`, `cli/manager.py`, `api/runtime.py`  
**Category:** DX / Comprehensiveness  
**Priority:** Medium  
**Status:** Implemented

**Current approach (before):** Model capabilities (`max_output_tokens`, `supports_vision`, `supports_tools`) were resolved from the provider registry and stored on `CLISession`/`CLISessionManager` as read-only properties, but never forwarded to the Claude Code CLI child process.

**Implementation:**
- Added `max_output_tokens: int | None` to `CLISession.__init__()` with private `_max_output_tokens` storage and read-only property — follows the same pattern as `supports_vision`/`supports_tools`
- Added `max_output_tokens` parameter to `CLISessionManager.__init__()`, stored and forwarded to `CLISession` constructor
- `api/runtime.py` resolves `max_output_tokens` from `provider_registry.cached_model_info().max_output_tokens` alongside `supports_vision`/`supports_tools` and passes to `CLISessionManager`
- `CLISession._build_child_env()` exports the three capability values as `CLAUDE_CODE_MAX_OUTPUT_TOKENS`, `CLAUDE_CODE_SUPPORTS_VISION`, `CLAUDE_CODE_SUPPORTS_TOOLS` env vars — each only set when the value is not `None`, with bools formatted as lowercase `"true"`/`"false"`

**Env var naming:** Uses the existing `CLAUDE_CODE_` prefix convention established by `CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY`.

**Impact:** The Claude Code CLI child process can read these optional env vars to adapt behavior (e.g., adjust output token budget, enable/disable vision features) without waiting for the `/v1/models` response.

**Verification:** Ruff format/lint/typecheck all clean. All 60 CLI tests pass.

---

### MSG-01 — Telegram + Discord Markdown Renderers ~95% Duplicated

**Module:** messaging  
**Files:** `messaging/platforms/telegram/markdown.py`, `messaging/platforms/discord/markdown.py`  
**Category:** Architecture  
**Priority:** Critical  
**Status:** Proposed

**Current approach:** 645 lines of near-identical token-walking code duplicated across Telegram and Discord renderers. Both implement custom markdown-to-platform-format converters with identical logic.

**Superior approach:** Extract shared Markdown tokenizer/converter into `messaging/rendering/` with platform-specific formatting plugins (small adapter per platform).

**Sources:** DRY principle. Tokenizer/visitor pattern in compiler design.

**Impact:** 400+ lines removed. Single bugfix for both platforms. Faster addition of new platforms.

---

### MSG-02 — Transcript Re-parses Markdown from Scratch on Every Render Tick

**Module:** messaging  
**Files:** `messaging/rendering/` transcript rendering  
**Category:** Performance  
**Priority:** High  
**Status:** Proposed

**Current approach:** Full markdown re-parse on every render tick. O(n) per tick where n = growing transcript length.

**Superior approach:** Incremental parser: cache parse tree, update only new content since last render. Or use an accumulator pattern that appends pre-rendered fragments.

**Impact:** O(1) per tick for stable transcript, O(m) per tick for m new characters.

---

### MSG-03 — Zero Tests in Messaging Module

**Module:** messaging  
**Files:** `messaging/` entire module  
**Category:** Testing  
**Priority:** Critical  
**Status:** Proposed

**Current approach:** No test files exist for any messaging component.

**Superior approach:** Add tests for: markdown conversion (both platforms), rendering, tree operations, rate limiter, session store, platform detection.

**Impact:** Catches rendering bugs, prevents platform-specific regressions.

---

### MSG-04 — `_SnapshotQueue.remove_if_present()` O(n) Deque Removal

**Module:** messaging  
**Files:** `messaging/trees/data.py`  
**Category:** Performance  
**Priority:** High  
**Status:** Proposed

**Current approach:** Reconstructs full deque O(n) per removal: creates new deque filtering out matching items.

**Superior approach:** Use `OrderedDict` as ordered set — O(1) removal and membership check.

**Sources:** Python `collections.OrderedDict` — ordered, O(1) key lookup and deletion.

**Impact:** Snapshot queue operations go from O(n) to O(1).

---

### MSG-05 — `MessagingRateLimiter` Global Singleton Blocks Test Isolation

**Module:** messaging  
**Files:** `messaging/platforms/` rate limiter  
**Category:** Testing  
**Priority:** High  
**Status:** Proposed

**Current approach:** Module-level `MessagingRateLimiter(1, 1)` singleton. Tests can't isolate rate limits.

**Superior approach:** Use DI to pass rate limiter instances. Module-level fallback for production.

**Impact:** Enables parallel test execution with independent rate limit state.

---

### MSG-06 — `threading.Timer` in `SessionStore` Mixes Threading + Async

**Module:** messaging  
**Files:** `messaging/trees/data.py` `SessionStore`  
**Category:** Resilience  
**Priority:** High  
**Status:** Proposed

**Current approach:** Uses `threading.Timer` for session expiry while the rest of the codebase uses `asyncio`. Thread-safety concerns with shared state.

**Superior approach:** Use `asyncio.create_task` with `await asyncio.sleep(delay)` for session expiry debounce.

**Impact:** Eliminates thread-safety surface. Pure async implementation.

---

### MSG-07 — Voice Note Pipeline Duplicated Across Telegram and Discord

**Module:** messaging  
**Files:** `messaging/platforms/telegram/`, `messaging/platforms/discord/`  
**Category:** Architecture  
**Priority:** Medium  
**Status:** Proposed

**Current approach:** Voice note download → transcribe → respond flow duplicated in both platform handlers.

**Superior approach:** Extract `VoiceNotePipeline` in `messaging/` with platform-specific download adapter.

**Impact:** Single transcription pipeline, DRY.

---

### MSG-08 — `if/elif` Chains → `match/case`

**Module:** messaging  
**Files:** `messaging/platforms/` message handling  
**Category:** DX  
**Priority:** Medium  
**Status:** Proposed

**Current approach:** Long `if/elif` chains for message type dispatch.

**Superior approach:** Use Python 3.14 structural pattern matching (`match/case`) with sub-patterns for content type extraction.

**Impact:** Readability, exhaustiveness checking.

---

### MSG-09 — `apply()` Dispatch Megamethod in Platform Handler

**Module:** messaging  
**Files:** `messaging/platforms/` platform interface  
**Category:** Architecture  
**Priority:** Medium  
**Status:** Proposed

**Current approach:** Single `apply()` method with inline dispatch logic for all message types.

**Superior approach:** Visitor pattern: `MessageVisitor` with `visit_text()`, `visit_voice()`, `visit_image()` etc. Platform handler registers specific visitors.

**Impact:** Open/closed principle — new message types don't require modifying the dispatch method.

---

### MSG-10 — LRU Cache for Markdown Renderer

**Module:** messaging  
**Files:** `messaging/rendering/`  
**Category:** Performance  
**Priority:** Medium  
**Status:** Proposed

**Current approach:** Markdown conversion recomputed on every render tick for unchanged content.

**Superior approach:** Add `functools.lru_cache` keyed on `(text, platform_type)` for identical fragments.

**Impact:** Caches frequent rendering patterns (e.g., same system message shown repeatedly).

---

### PRV-01 — Missing `Retry-After` Header Parsing

**Module:** providers  
**Files:** `providers/rate_limit.py` lines 64–91  
**Category:** Architecture  
**Priority:** High  
**Status:** Implemented

**Current approach:** `set_blocked(seconds=60)` uses hardcoded 60s block regardless of upstream's `Retry-After` header.

**Superior approach:** Extract `Retry-After` from `response.headers` in `retryable_upstream_status()`.

**Sources:** OpenAI SDK, httpx-retries, Pydantic AI docs. AWS/GitHub/Stripe send meaningful `Retry-After`.

**Impact:** Adaptive backoff instead of fixed 60s.

**Implementation:** Connected `set_blocked_from_response()` to `execute_with_retry()` — extracts `response` from exception objects via `getattr(e, "response", None)` and passes it so `Retry-After` header is preferred over the exponential backoff delay.

**Verification:** 37 rate-limit tests pass. Ruff format/lint/typecheck all clean.

---

### PRV-02 — Custom Retry Loop → tenacity Declarative Retry

**Module:** providers  
**Files:** `providers/rate_limit.py`  
**Category:** Resilience  
**Priority:** High  
**Status:** Implemented

**Current approach (before):** Manual retry loop with exponential backoff and jitter using `random.uniform()`.

**New approach:** `execute_with_retry` uses `tenacity.AsyncRetrying` with:
- `stop=stop_after_attempt(max_attempts)` — configurable retry count
- `wait=wait_exponential(multiplier=base_delay, min=base_delay, max=max_delay) + wait_random(0, jitter)` — exponential backoff with jitter
- `retry=retry_if_exception(retryable_upstream_status)` — declarative predicate
- `before_sleep` callback — logs attempts, extracts `Retry-After` header via `set_blocked_from_response()`
- `reraise=True` — preserves original exception type after exhausting retries

Circuit breaker integration (`may_proceed`/`on_success`/`on_failure`) is preserved.

**Impact:** Fewer bugs, structured logging, well-tested retry logic.

**Dependencies:** `tenacity` added to `pyproject.toml`.

**Verification:** Ruff format/lint/typecheck all clean. All 37 rate-limit tests pass.

---

### PRV-03 — Token Bucket vs Sliding Window Log

**Module:** providers  
**Files:** `providers/rate_limit.py` lines 47–59  
**Category:** Architecture  
**Priority:** Medium  
**Status:** Proposed

**Current approach:** `StrictSlidingWindowLimiter` stores every request timestamp in `deque`. At 40 req/s, 2400 entries/minute/limiter.

**Superior approach:** Token Bucket algorithm: O(1) memory (two floats), burst-friendly, used by Stripe/GitHub/AWS.

**Sources:** Token bucket is recommended default for public API rate limiting. Sliding window log for low-volume precise rules only.

**Impact:** O(1) memory vs O(n). Friendlier to burst patterns.

---

### PRV-04 — No Distributed Rate Limiting State (Redis)

**Module:** providers  
**Files:** `providers/rate_limit.py` lines 295–296  
**Category:** Resilience  
**Priority:** Medium  
**Status:** Proposed

**Current approach:** Rate limiter state is purely in-process memory.

**Superior approach:** Abstract `RateLimitStore` interface with Redis backend. Fall back to in-memory when Redis unavailable.

**Sources:** production guides (FastAPI + Redis), rate-sync/python.

**Impact:** Enables multi-instance deployments with correct aggregate rate limiting.

---

### PRV-05 — HTTP Connection Pool Limits

**Module:** providers  
**Files:** `providers/base.py` (httpx.AsyncClient construction)  
**Category:** Performance  
**Priority:** Medium  
**Status:** Proposed

**Current approach:** `httpx.AsyncClient()` without explicit `Limits`. Default: 100 connections, 5 keepalive.

**Superior approach:** Pass `limits=httpx.Limits(max_connections=50, max_keepalive_connections=25)`.

**Sources:** httpx production guides recommend explicit limits.

**Impact:** Prevents file descriptor exhaustion under load.

---

### PRV-06 — Error Text String Matching

**Module:** providers  
**Files:** `providers/nvidia_nim/client.py` `_get_retry_request_body`  
**Category:** Resilience  
**Priority:** Medium  
**Status:** Proposed

**Current approach:** Retry decision based on substring matching in `error_text_lower`. Fragile across API versions and locales.

**Superior approach:** Parse `error.body` JSON for structured error fields (`error.code`, `error.type`) before string fallback.

**Sources:** OpenAI SDK provides `BadRequestError.body` as parsed JSON. NVIDIA NIM returns structured error bodies.

**Impact:** Deterministic retry decisions, locale-independent.

---

### PRV-07 — Error Mapping Tied to SDK Exceptions

**Module:** providers  
**Files:** `providers/error_mapping.py` lines 44–94  
**Category:** Architecture  
**Priority:** Medium  
**Status:** Proposed

**Current approach:** `isinstance` chains on `openai.*` and `httpx.*` exceptions. Adding new provider SDK requires modifying this function.

**Superior approach:** Registry of `ProviderErrorMapper` protocol implementations. Each provider registers its mapper.

**Impact:** Extensible error mapping without modifying core function.

---

### PRV-08 — NvidiaNimProvider Duplicates Parent Constructor

**Module:** providers  
**Files:** `providers/nvidia_nim/client.py`, `providers/openai_compat.py`  
**Category:** Developer Experience  
**Priority:** High  
**Status:** Implemented

**Current approach (before):** `NvidiaNimProvider.__init__()` called `super().__init__()` then immediately overrode `self._client` with a new `AsyncOpenAI`. Parent's client discarded without closing.

**Implementation:**
- Moved `_nim_settings` assignment to **before** `super().__init__()` so the parent constructor can read NIM-specific config
- Added `_build_client_kwargs()` method to `OpenAIChatTransport` that returns a `dict[str, Any]` of kwargs for the `AsyncOpenAI` constructor — the parent now calls `AsyncOpenAI(**self._build_client_kwargs())` instead of hardcoding defaults
- `NvidiaNimProvider` overrides `_build_client_kwargs()` to inject custom timeouts from `NimSettings` (`http_read_timeout`, `http_write_timeout`, `http_connect_timeout`), zero out `max_retries`, and attach a proxy `AsyncClient` when configured
- Parent's timeout values (from `ProviderConfig.http_*_timeout`) become the default — NIM overrides with more aggressive NIM-specific timeouts

**Impact:** Eliminates wasted client construction (no double allocation). Enables any `OpenAIChatTransport` subclass to customize the OpenAI client via a single method override.

**Verification:** Ruff format/lint/typecheck all clean. All NIM and provider tests pass.

---

### PRV-09 — Circuit Breaker for Fail-Fast Degradation

**Module:** providers  
**Files:** `providers/rate_limit.py`  
**Category:** Resilience  
**Priority:** High  
**Status:** Implemented

**Current approach (before):** No provider implements circuit breaker. Degraded upstream → every request retries 3 times (wasting ~60s).

**New feature:** `CircuitBreaker` class integrated into `GlobalRateLimiter`:
- **Three states:** `CLOSED` (normal) → `OPEN` (fail-fast) → `HALF_OPEN` (recovery probes)
- Configurable `failure_threshold` (5), `recovery_timeout` (30s), `half_open_max_requests` (3)
- Automatic OPEN → HALF_OPEN transition when recovery timeout elapses
- Full closure only when all half-open probes succeed; single failure re-opens
- `CircuitBreakerOpenError` exception carries `scope` and `retry_after` for upstream error handling
- State transitions logged via `trace_event` and `logger.warning`
- Each scoped limiter (per provider) gets its own circuit breaker

**Integration:** `execute_with_retry()` checks `circuit_breaker.may_proceed()` before every request — fail-fast when open. Reports `on_success()` after successful calls, `on_failure()` on retryable errors.

**Impact:** Fast-fail during upstream degradation instead of wasting time on retries.

**Verification:** Ruff format/lint/typecheck all clean. All 37 rate-limit tests pass.

---

### PRV-10 — Kimi Provider Zero Tests

**Module:** providers  
**Files:** `providers/kimi/client.py` (31 lines)  
**Category:** Testing  
**Priority:** High  
**Status:** Proposed

**Current approach:** 31-line provider class, no test file, no retry logic, no model list filtering.

**Superior approach:** Add `tests/providers/test_kimi.py` with request building, streaming, error mapping, thinking enable/disable tests.

---

### PRV-11 — Four Empty Provider Stubs

**Module:** providers  
**Files:** `providers/fireworks/`, `providers/google_ai_studio/`, `providers/opencode/`, `providers/zai/`  
**Category:** Comprehensiveness  
**Priority:** High  
**Status:** Proposed

**Current approach:** Empty directories with only `__pycache__/`. Not registered in `PROVIDER_FACTORIES`.

**Superior approach:** Implement or remove. Priority: Fireworks (OpenAI-compat), Google AI Studio (Gemini), then others.

---

### PRV-12 — Recursive Schema Walker Stack Overflow

**Module:** providers  
**Files:** `providers/nvidia_nim/request.py` lines 18–40  
**Category:** Security  
**Priority:** Medium  
**Status:** Proposed

**Current approach:** `_sanitize_nim_schema_node` walks JSON Schema recursively without cycle detection.

**Superior approach:** Add `max_depth: int = 100` and `visited: set[int]` tracking dict `id()` values.

---

### PRV-13 — Tool Call State Complexity

**Module:** providers  
**Files:** `providers/openai_compat.py` lines 243–290  
**Category:** Maintainability  
**Priority:** Medium  
**Status:** Proposed

**Current approach:** Tool call state tracking with `pre_start_args` buffers, three separate flush paths.

**Superior approach:** Consolidate into `ToolCallBuffer` class with `feed(delta) → list[event]` and `flush() → list[event]`.

---

### PRV-14 — Model Discovery Timeout Log Mismatch

**Module:** providers  
**Files:** `providers/registry.py` lines 354–375  
**Category:** Resilience  
**Priority:** Medium  
**Status:** Proposed

**Current approach:** `asyncio.wait_for(timeout=10.0)` but log says "timed out (30s)".

**Superior approach:** Fix log message. Make timeout configurable.

---

### PRV-15 — Keepalive for Long-Running Streams

**Module:** providers  
**Files:** `providers/anthropic_messages.py` lines 62–93  
**Category:** Resilience  
**Priority:** Medium  
**Status:** Proposed

**Current approach:** No SSE keepalive or ping mechanism. Connection may idle for minutes during thinking.

**Superior approach:** Emit SSE keepalive comments (`: keepalive\n\n`) every 15–30 seconds during idle periods.

---

### PRV-16 — Wafer Forced Thinking

**Module:** providers  
**Files:** `providers/wafer/client.py` lines 26–28  
**Category:** Resilience  
**Priority:** Medium  
**Status:** Implemented

**Current approach:** Unconditionally adds `{"thinking": {"type": "enabled"}}`.

**Superior approach:** Only force thinking when `enable_thinking` is True.

**Implementation:** Changed guard from `if "thinking" not in body:` to `if thinking_enabled is not False and "thinking" not in body:`. When `thinking_enabled=False` is explicitly passed, Wafer now respects the caller's intent.

**Verification:** All 9 Wafer tests pass. Updated the test that was asserting the old behavior (`test_build_request_body_keeps_upstream_thinking_enabled_when_client_disables_it` → `test_build_request_body_respects_thinking_disabled_when_client_passes_false`).

---

### PRV-17 — DeepSeek Block Filter Architecture

**Module:** providers  
**Files:** `providers/deepseek/request.py` lines 36–108  
**Category:** Architecture  
**Priority:** Medium  
**Status:** Proposed

**Current approach:** Manual if/elif chains for stripping unsupported blocks.

**Superior approach:** `BlockFilter` pipeline where each unsupported type is a registered filter.

---

### PRV-18 — `ProviderModelInfo` Metadata Cascade

**Module:** providers, api  
**Files:** `providers/model_listing.py`, `api/routes.py`, `api/models/responses.py`  
**Category:** Comprehensiveness  
**Priority:** Medium  
**Status:** Implemented

**Current approach (before):** Only `model_id` and `supports_thinking` in metadata.

**New fields added to `ProviderModelInfo`:**
- `context_window: int | None` — mapped from OpenRouter's `context_length`
- `max_output_tokens: int | None` — mapped from `top_provider.max_completion_tokens` (preferred) or `per_request_limits.completion_tokens` (fallback); also populated via `_enrich_model_infos()` for known model families (DeepSeek-v4: 384K, DeepSeek-chat: 8K)
- `supports_vision: bool | None` — resolved from `architecture.input_modalities` array (`"image"` check) with `modality` string fallback
- `supports_tools: bool | None` — reserved for future provider-specific tool metadata
- `supports_streaming: bool | None` — reserved for future use

**Exposed in `/v1/models` API response:**
- `ModelResponse` gained `context_window`, `max_output_tokens`, `supports_vision`, `supports_tools` fields
- `_resolve_model_info()` helper in `routes.py` fetches all fields via single `cached_model_info()` call
- Both configured-refs path and discovered-models path forward the new fields
- `SUPPORTED_CLAUDE_MODELS` entries have hardcoded capability data

**Provider coverage differences:**
- **OpenRouter** — Full dynamic extraction: `max_output_tokens` from `top_provider.max_completion_tokens`, `context_window` from `context_length`, `supports_vision` from `architecture.input_modalities`
- **DeepSeek, Wafer, and other AnthropicMessagesTransport providers** — Static enrichment via `model_infos_from_ids()` → `_enrich_model_infos()` which applies the `_KNOWN_MODEL_CAPABILITIES` table for well-known model IDs (DeepSeek-v4, DeepSeek-chat). All other model IDs remain at `None`
- **NVIDIA NIM and OpenAI-compatible providers** — No capability metadata from the `/v1/models` endpoint. Defaults to `None` for all fields

**Verification:** Format/lint/typecheck all clean. All model listing API tests pass. All OpenRouter metadata extraction tests pass. Live integration test validates extracted fields against real OpenRouter API.
---

### PRV-19 — Error Body Preview Reader Identity

**Module:** providers  
**Files:** `providers/anthropic_messages.py` lines 203–226  
**Category:** Resilience  
**Priority:** Low  
**Status:** Proposed

**Current approach:** `response.aiter_bytes()` consumed then `aclose()` called by caller.

**Superior approach:** Close response within error handler, signal closed state.

---

### PRV-20 — Ollama Client Per Call

**Module:** providers  
**Files:** `providers/ollama/client.py` lines 40–44  
**Category:** Performance  
**Priority:** Low  
**Status:** Proposed

**Current approach:** New `httpx.AsyncClient` per model list request.

**Superior approach:** Use existing `self._client`.

---

### PRV-21 — Riva ASR Synchronous Read

**Module:** providers  
**Files:** `providers/nvidia_nim/voice.py` lines 28–95  
**Category:** Performance  
**Priority:** Low  
**Status:** Proposed

**Current approach:** `f.read()` entire file, synchronous `offline_recognize`.

**Superior approach:** Add streaming ASR variant with chunked processing.

---

### PRV-22 — DeepSeek URL Construction

**Module:** providers  
**Files:** `providers/deepseek/client.py` lines 41–48  
**Category:** Performance  
**Priority:** Low  
**Status:** Proposed

**Current approach:** `httpx.URL(...).copy_with(path="/models")` on every call.

**Superior approach:** Compute `_model_list_url` once in `__init__`.

---

### PRV-23 — `proxy: str = ""` Default

**Module:** providers  
**Files:** `providers/base.py` line 29  
**Category:** DX  
**Priority:** Low  
**Status:** Proposed

**Current approach:** `proxy: str = ""` requiring `or None` guards.

**Superior approach:** `proxy: str | None = None`.

---

### PRV-24 — Model List Parser Registry

**Module:** providers  
**Files:** `providers/model_listing.py`  
**Category:** Architecture  
**Priority:** Low  
**Status:** Proposed

**Current approach:** Free functions for each provider's model list format.

**Superior approach:** `ModelListParser(Protocol)` registry.

---

### TST-01 — Property-Based Testing

**Module:** tests  
**Files:** `tests/`  
**Category:** Testing  
**Priority:** High  
**Status:** Proposed

**Current approach:** Example-based tests only.

**Superior approach:** Use `hypothesis` for property-based tests: message conversion round-trips, tool schema sanitization, rate limiter properties, SSE generation invariants.

**Sources:** Hypothesis docs. Property-based testing catches edge cases example-based tests miss.

**Impact:** Covers edge cases, symbolic regression.

---

### TST-02 — Full-Stack Integration Test Harness

**Module:** tests  
**Files:** `tests/`  
**Category:** Testing  
**Priority:** High  
**Status:** Proposed

**Current approach:** Unit and API-level tests with mocks. No full-stack integration test.

**Superior approach:** `TestClient` + mock provider that returns known SSE sequences. Test the complete request→response pipeline.

---

### TST-03 — SSRF Security Fuzzing

**Module:** tests  
**Files:** `tests/`  
**Category:** Security  
**Priority:** High  
**Status:** Proposed

**Current approach:** No SSRF/URL-injection-specific tests for `web_tools`.

**Superior approach:** Add fuzz tests for URL handlers: protocol injection, private IP ranges, DNS rebinding patterns.

---

### TST-04 — Slow Test Profiling

**Module:** tests  
**Files:** `tests/`  
**Category:** Performance  
**Priority:** Medium  
**Status:** Proposed

**Current approach:** No pytest duration reporting in CI.

**Superior approach:** Add `--durations=10` to pytest options. Profile and optimize tests over 500ms.

---

### TST-05 — Snapshot Testing

**Module:** tests  
**Files:** `tests/`  
**Category:** Testing  
**Priority:** Medium  
**Status:** Proposed

**Current approach:** Manual assertion comparisons for expected output.

**Superior approach:** Use `syrupy` for snapshot testing of SSE sequences, markdown output, error responses.

**Impact:** Catches unintended output changes, simplifies test writing.
