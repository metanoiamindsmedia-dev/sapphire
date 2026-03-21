# GitHub Copilot Workspace Instructions (Sapphire)

## Purpose
This file is the workspace-specific Copilot directive for Sapphire (https://github.com/ddxfish/sapphire).
It helps Copilot-style AI assistants quickly understand project intent, architecture, development workflow, and quality expectations.

## Project Summary
- Sapphire is a self-hosted AI persona framework (voice, memory, agents, tools, plugins).
- Core is in `sapphire/sapphire` and `sapphire/core`, with a browser UI, plugin + tool ecosystems.
- Focus: safe autonomous actions with user-configured guardrails.

## Key paths
- `sapphire/sapphire` - main app modules (api, tools, prompts, continuity, etc.)
- `sapphire/docs` - user and developer docs (AGENTS.md, PROMPTS.md, PLUGINS.md, etc.)
- `tests` - unit/integration tests
- `sapphire/config.py`, `sapphire/main.py`, `sapphire.py` - entry points and config management

## Build & test commands
- `pip install -r requirements.txt`
- `python main.py` -> run locally
- `pytest -q` -> run tests
- `python -m pytest tests/` -> focused test runs

## Copilot workflow
1. Start by reading README and `docs/TECHNICAL.md` where architecture is described.
2. Find existing module patterns and keep new code style consistent (single-file, no global state, core hooks).
3. For new features, prefer plugin-based extension unless patching core behavior is required.
4. When editing user-facing behavior, update docs in `docs/` and add regression tests in `tests/`.

## Style and conventions
- Python 3.11, Black formatting, minimal external dependencies.
- Prefer clear function names + small helpers over huge monolith methods.
- Use existing utility modules (`core/prompt_manager.py`, `core/tool_context.py`, etc.) wherever possible.
- Respect destructive operations: require explicit opt-in in settings/human confirmation.

## Agent-customization-specific guidance
- For REPO scope, keep instructions in `.github/copilot-instructions.md`.
- Maintain the "link, don’t embed" principle: reference existing docs in `docs/` rather than duplicating large sections.
- If adding an agent component, put new material in `docs/AGENTS.md`, update plugin registration in `core/plugin_loader.py`.

## Troubleshooting
- If endpoints fail, inspect logs under `sapphire/logs` and settings in `user/settings.json`.
- If tests fail due to environment, raise `SAFETY` flags and replicate via isolated `venv`.

## Example prompts for Copilot interaction
- "Add a new API endpoint in Sapphire for [feature], include tests and docs."
- "Refactor the agent lifecycle in `core/agents` to avoid deadlocks when many agents run."
- "Document startup config for speech models in `docs/INSTALLATION.md`."

## Suggested next customizations
- `/create-hook agent-start` to add a plugin hook triggered at agent spawn.
- `/create-agent` to scaffold a new background assistant type (e.g., `web-scraper` agent).
- `/create-instruction` to add a second-level alias for safe task authoring in chats.
- `/create-prompt` to supply a ready-to-use mission statement template for new agents.
- `/create-skill` to integrate Foundry/agent-framework workflows (especially from `docs/AGENTS.md`).
