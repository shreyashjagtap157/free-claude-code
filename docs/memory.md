# 🧠 Project Memory & Development Record

This document serves as the persistent memory for the development of `free-claude-code`, tracking audits, architectural improvements, fixes, and verification logs.

---

## 📅 Log: May 29, 2026

### 1. Codebase Audit & Latency Analysis
- **Goal**: Analyze codebase for slow response times (4-6 minutes) during daytime and evening rate-limit (HTTP 429) blockages.
- **Actions Taken**:
  - Conducted a comprehensive AST analysis of the API service layer (`api/services.py`).
  - Audited the provider transports (`providers/openai_compat.py` and `providers/deepseek/request.py`).
  - Reviewed the architectural guidelines and boundaries in `PLAN.md` and `tests/contracts/test_import_boundaries.py`.
- **Key Discovery**:
  - `_OPENAI_CHAT_UPSTREAM_IDS` in `api/services.py` was hardcoded to `frozenset({"nvidia_nim"})`.
  - As a result, context trimming was **disabled** for 11 out of 12 providers.
  - Runaway conversation histories were sent raw, causing extremely high tokens per minute (TPM) consumption (triggering HTTP 429 lockouts) and high latency due to re-processing untrimmed histories.
- **State-of-the-Art Fix Proposed**:
  - Dynamically define `_OPENAI_CHAT_UPSTREAM_IDS` by querying `PROVIDER_CATALOG` for all providers with `transport_type == "openai_chat"`.
  - Ensure zero import boundary violations.

---

## 🛠️ Task Status Checklist

- [x] Conduct comprehensive architectural and performance audit
- [x] Document audit results in [docs/audit.md](file:///d:/Project/free-claude-code/docs/audit.md)
- [x] Create project memory file [docs/memory.md](file:///d:/Project/free-claude-code/docs/memory.md)
- [/] Run baseline pytest suite (Currently Running)
- [ ] Create implementation plan to dynamically resolve `_OPENAI_CHAT_UPSTREAM_IDS`
- [ ] Implement the state-of-the-art fix in `api/services.py`
- [ ] Run linting, type checks, and pytest to verify the fix
- [ ] Create walkthrough documenting accomplishment

---

## 📈 Next Steps
1. Wait for baseline `pytest` execution to confirm the starting health of the codebase.
2. Formulate the official `implementation_plan.md` for user approval.
3. Apply the dynamic `_OPENAI_CHAT_UPSTREAM_IDS` change and execute validation.
