# Contributing to Free Claude Code

Thank you for your interest in contributing! This document covers the setup, coding standards, and workflow.

## Getting Started

1. **Clone the repository**:
   ```bash
   git clone https://github.com/Alishahryar1/free-claude-code.git
   cd free-claude-code
   ```

2. **Install uv** (if not already installed):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

3. **Install Python 3.14**:
   ```bash
   uv python install 3.14
   ```

4. **Install dependencies**:
   ```bash
   uv sync
   ```

5. **Install pre-commit hooks**:
   ```bash
   uv run pre-commit install
   ```

## Coding Standards

- **Python version**: Target Python 3.14 (`requires-python = ">=3.14"`).
- **Formatting**: Use `uv run ruff format` (line length 88, double quotes, spaces).
- **Linting**: Use `uv run ruff check` (rules: E, W, F, I, UP, B, C4, SIM, PERF, RUF).
- **Type checking**: Use `uv run ty check` (strict mode, no `# type: ignore` or `# ty: ignore`).
- **Testing**: Use `uv run pytest` (runs with `-n auto` for parallel execution).

### Pre-Commit Check Sequence

Run all checks before opening a pull request:

```bash
uv run ruff format
uv run ruff check
uv run ty check
uv run pytest
```

All four must pass. CI enforces these on every push/merge.

## Project Structure

- `api/` — FastAPI server, routes, middleware, web tools
- `cli/` — CLI entry points (`fcc-server`, `fcc-init`, `fcc-claude`)
- `config/` — Pydantic settings, provider catalog, constants
- `core/` — Shared utilities: Anthropic protocol helpers, rate limiting, tracing
- `messaging/` — Telegram/Discord platform adapters, session store, rendering
- `providers/` — Provider adapters (NVIDIA NIM, OpenRouter, DeepSeek, etc.)
- `smoke/` — End-to-end smoke tests
- `tests/` — Unit and integration tests

## Pull Request Guidelines

- Keep changes small and focused on a single concern.
- Write tests for new functionality and edge cases.
- Update documentation (README, docstrings) when changing public interfaces.
- Do not add `# type: ignore` or `# ty: ignore` — fix the underlying type issue.
- Do not open Docker integration PRs (they will be closed).
- Do not open README-only change PRs — file an issue instead.

## Provider Integration

1. Add the provider module in `providers/<name>/`.
2. Register provider metadata in `config/provider_catalog.py`.
3. Add factory wiring in `providers/registry.py`.
4. Add tests for request building, response parsing, and error mapping.

## Messaging Platform Integration

1. Implement the `MessagingPlatform` interface in `messaging/platforms/`.
2. Add platform-specific markdown rendering in `messaging/rendering/`.
3. Wire up the platform in `messaging/platforms/factory.py`.

## Questions?

Open an issue on GitHub for questions, bug reports, or feature requests.
