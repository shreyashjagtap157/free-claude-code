# 🛡️ Codebase Performance, Caching & Context Trimming Audit

## 📋 Executive Summary
This audit reviews the architecture, latency bottlenecks, and prompt caching capabilities of the `free-claude-code` proxy. The proxy acts as a translation layer routing Anthropic-compatible requests (e.g. from Claude Code CLI) to various upstream AI providers.

During this deep-dive audit, we investigated why **context trimming** was originally introduced, how it interacts with **prompt caching**, and how to safely enable prompt caching for connected models to minimize Time-to-First-Token (TTFT) latency, rate-limit consumption, and cost.

---

## 🔍 Context Trimming vs. Prompt Caching: The Conflict

### 1. What is Context Trimming?
Context trimming is a server-side optimization that reduces message token counts by:
- Stripping thinking blocks (`<thinking>` and `<redacted_thinking>`) from prior assistant responses (as non-Anthropic models cannot reuse or parse them).
- Truncating oversized tool results (e.g., file reads or shell outputs) to fit within `max_tool_result_tokens` (default: 2,000).
- Dropping oldest message turns (history pruning) in pairs to keep total prompt tokens within a budget of `max_context_tokens` (default: 15,000).

### 2. Why does Context Trimming occur at all?
For upstreams that do **not** support prompt caching (like `nvidia_nim`, local runners LM Studio, Ollama, llama.cpp, and Kimi), the upstream model re-processes the entire prompt from scratch on every turn. Without trimming:
- Prompts grow indefinitely (often exceeding 60k–100k tokens in long agent loops).
- Upstream models experience severe TTFT delays (up to 4–6 minutes).
- Requests consume vast amounts of Tokens-Per-Minute (TPM), triggering frequent rate-limit lockouts (HTTP 429).
- Context trimming protects these providers by enforcing strict token budgets.

### 3. Why does Context Trimming break Prompt Caching?
Prompt caching (supported by Anthropic, DeepSeek, and Google AI Studio) works by matching the prompt prefix against previously processed prompts.
- **Prefix Matching Rule**: If even one character at the start of the prompt changes or is dropped, the entire prompt cache is invalidated.
- **Destructive Interaction**: When context trimming drops the oldest messages, the prompt prefix shifts. The entire cached prompt history is invalidated, forcing the provider to re-evaluate the remaining context from scratch.
- **Conclusion**: Applying context trimming to prompt-caching-capable models completely defeats caching benefits, leading to unnecessary delays and high token fees.

---

## 🏁 Comprehensive Caching & Trimming Provider Matrix

Below is the exhaustive audit of all 13 supported providers, their transport types, their native prompt caching capabilities, and how context trimming should be applied:

| Provider ID | Transport Type | Cache Support | Trimming Policy | Reason / Strategy |
| :--- | :--- | :--- | :--- | :--- |
| **`open_router`** | `anthropic_messages` | **Yes** (Model-Dep) | ❌ **Disabled** | Native Anthropic passthrough. Let client specify cache boundaries. |
| **`deepseek`** | `anthropic_messages` | **Yes** (Native >=1k tok) | ❌ **Disabled** | Automatically caches prompts >= 1,024 tokens. Pruning ruins cache. |
| **`wafer`** | `anthropic_messages` | **Yes** (Native) | ❌ **Disabled** | Anthropic-compatible routing; preserves `cache_control` blocks. |
| **`google_ai_studio`** | `openai_chat` | **Yes** (Native >=32k tok) | ❌ **Disabled (NEW)** | Gemini automatically caches prompts >= 32,768 tokens. Bypassing trimming lets cache scale. |
| **`nvidia_nim`** | `openai_chat` | ❌ No | ✅ **Enabled** | OpenAI Chat upstream. High TTFT; requires strict context trimming. |
| **`lmstudio`** | `openai_chat` | ❌ No | ✅ **Enabled** | Local runner. No native prompt caching; requires context trimming. |
| **`llamacpp`** | `openai_chat` | ❌ No | ✅ **Enabled** | Local runner. No native prompt caching; requires context trimming. |
| **`ollama`** | `openai_chat` | ❌ No | ✅ **Enabled** | Local runner. No native prompt caching; requires context trimming. |
| **`kimi`** | `openai_chat` | ❌ No | ✅ **Enabled** | OpenAI Chat upstream. No prompt caching; requires context trimming. |
| **`opencode`** | `openai_chat` | ❌ No | ✅ **Enabled** | OpenAI Chat upstream. No prompt caching; requires context trimming. |
| **`opencode_go`** | `openai_chat` | ❌ No | ✅ **Enabled** | OpenAI Chat upstream. No prompt caching; requires context trimming. |
| **`zai`** | `openai_chat` | ❌ No | ✅ **Enabled** | OpenAI Chat upstream. No prompt caching; requires context trimming. |
| **`fireworks`** | `openai_chat` | ❌ No | ✅ **Enabled** | OpenAI Chat upstream. No prompt caching; requires context trimming. |

---

## 🛠️ Recommended Design Solution

To let `claude-code` work seamlessly with prompt caching, we must modify the proxy request flow to bypass context trimming for all providers with `"prompt_caching"` capability.

1. **Declare Capability**: Add `"prompt_caching"` to capabilities in `PROVIDER_CATALOG` for `open_router`, `deepseek`, `wafer`, and `google_ai_studio`.
2. **Inspect & Bypass**: In `api/services.py`, check the resolved provider's capabilities. If the provider supports `"prompt_caching"`, do not apply `_apply_context_trimming`.
3. **Budget Safety**: If prompt caching is disabled or unsupported, apply trimming normally to prevent rate limits and high TTFT.
