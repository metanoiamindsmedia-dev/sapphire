# Sapphire MCP Integration Setup - Summary

This directory now contains a complete setup for integrating Sapphire with MCP Docker Server tools and multi-model LLM access.

## What Has Been Created

### 1. Environment Configuration
- **`.env.example`** - Template environment variables with all LLM API keys and MCP settings
- **`validate_mcp_setup.py`** - Validation script to check your configuration

### 2. Configuration Examples
- **`user/personas/personas.example.json`** - Pre-configured personas with MCP tools
- **`user/toolsets/toolsets.example.json`** - Toolsets mapping to MCP tool categories
- **`user/settings.example.json`** - Full settings with agents, LLM providers, and tools

### 3. Integration Code
- **`core/mcp_integration.py`** - MCP client library for tool access and configuration
  - Connects to MCP Docker Server
  - Filters tools by category
  - Provides async tool calling interface
  - Integrates with persona/agent systems

### 4. Documentation
- **`MCP-QUICKSTART.md`** - Fast setup guide (start here!)
- **`docs/MCP-INTEGRATION.md`** - Complete MCP setup and configuration
- **`docs/MCP-AGENTS.md`** - Using MCP tools with agents

## Quick Start (2 Minutes)

1. **Copy and configure .env:**
   ```bash
   cp .env.example .env
   # Edit .env and add your API key (e.g., ANTHROPIC_API_KEY=sk-ant-...)
   ```

2. **Validate your setup:**
   ```bash
   python validate_mcp_setup.py
   ```

3. **Run Sapphire:**
   ```bash
   python main.py
   ```

4. **Try it in chat:**
   - Open Web UI: http://localhost:8073
   - Ask: "What are the top GitHub issues in the sapphire repo?"
   - Or spawn an agent: "Send a dev-researcher agent to analyze that codebase"

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Sapphire Web UI                         │
└──────────────────────┬──────────────────────────────────────┘
                       │
     ┌─────────────────┼─────────────────┐
     │                 │                 │
┌────▼────┐   ┌────────▼────────┐  ┌────▼─────┐
│ Personas │   │   Agents       │  │   Chat   │
│  with    │   │  with MCP      │  │ with MCP │
│ Toolsets │   │  Tools         │  │  Tools   │
└────┬────┘   └────────┬────────┘  └────┬─────┘
     │                 │                 │
     └─────────────────┼─────────────────┘
                       │
            ┌──────────▼──────────┐
            │  Function Manager   │ (handles tool calls)
            │  + MCP Integration  │
            └──────────┬──────────┘
                       │
            ┌──────────▼──────────┐
            │  MCP Client         │ (core/mcp_integration.py)
            │  - Lists tools      │
            │  - Filters by cat   │
            │  - Calls tools      │
            └──────────┬──────────┘
                       │
            ┌──────────▼──────────┐
            │ MCP Docker Server   │ (external)
            │ - GitHub tools      │
            │ - Azure tools       │
            │ - AWS tools         │
            │ - Filesystem, etc.  │
            └─────────────────────┘
```

## File Structure

```
sapphire/
├── .env.example                          # Template: copy to .env
├── .env                                  # Your local config (in .gitignore)
├── MCP-QUICKSTART.md                    # Start here!
├── validate_mcp_setup.py                # Validation tool
├── core/
│   └── mcp_integration.py                # MCP client library (NEW)
├── user/
│   ├── personas/
│   │   ├── personas.json                 # Your custom personas
│   │   └── personas.example.json         # Examples with MCP (NEW)
│   ├── toolsets/
│   │   ├── toolsets.json                 # Your custom toolsets
│   │   └── toolsets.example.json         # Examples (NEW)
│   └── settings.json                     # Your configuration
├── docs/
│   ├── MCP-INTEGRATION.md                # Complete setup guide (NEW)
│   ├── MCP-AGENTS.md                     # Agent customization (NEW)
│   ├── AGENTS.md                         # Agent framework
│   ├── PERSONAS.md                       # Persona docs
│   └── ...
└── sapphire-data/
    └── settings.example.json             # Defaults (reference)
```

## Key Concepts

### 1. Personas
Reusable AI companions with pre-configured:
- Personality/voice (sapphire, cobalt, etc.)
- Available tools/toolset (dev-tools, ops-tools, etc.)
- LLM model selection (claude-sonnet-4-5, gemini-2.5-pro, etc.)
- Spice/relation settings

**Example:** `developer-assistant` persona comes with `dev-tools` toolset and uses Claude Sonnet.

### 2. Toolsets
Collections of MCP tools grouped by purpose:
- `dev-tools` - GitHub, Git, filesystem (code review)
- `ops-tools` - Azure, AWS, Kubernetes (infrastructure)
- `data-tools` - File access, Python/Node execution (analysis)
- `research-tools` - Web fetch, sequential thinking (research)
- `github-azure` - Custom combo for cloud dev

### 3. MCP Tools (from Docker Server)
Available via configuration categories:

| Category | Tools |
|----------|-------|
| `github` | Create/list/search issues, PRs, code |
| `azure` | List/create/delete resources |
| `aws` | Manage EC2, S3, etc. |
| `filesystem` | Read/write files |
| `fetch` | Web scraping and search |
| `git` | Clone, branches, commits |
| `playwright` | Browser automation |
| `desktop-commander` | System operations |
| `memory` | Persistent notes |
| `huggingface` | Model access |

### 4. LLM Providers
Multiple models available via API keys:

| Provider | Model | When to Use |
|----------|-------|------------|
| Claude | claude-sonnet-4-5 | Default: fast, accurate |
| Claude | claude-opus-4-5 | Complex decisions (agent) |
| Gemini | gemini-2.5-pro | Extended thinking |
| OpenAI | gpt-4o | Alternative |

### 5. Agents
Background workers with:
- Custom model selection
- Dedicated toolset
- Tool round limits
- Task isolation

**Example:** `dev-researcher` agent spawns with:
- Model: `claude-sonnet-4-5`
- Toolset: `dev-tools` (GitHub, Git, fetch)
- Max rounds: 7
- Scopes: isolated (none)

## Configuration Workflows

### Workflow 1: Add a New Persona
1. Copy persona config from `personas.example.json`
2. Add to `user/personas/personas.json`
3. Set its `toolset` and `llm_model`
4. Select it in Web UI → Settings → Persona

### Workflow 2: Create a Custom Toolset
1. Copy toolset from `toolsets.example.json`
2. Add to `user/toolsets/toolsets.json`
3. List tools it should include
4. Assign to persona or agent

### Workflow 3: Enable a New MCP Category
1. Edit `.env`
2. Set `MCP_ENABLE_GITHUB=true` (for example)
3. Restart Sapphire
4. Tools in that category now available

### Workflow 4: Spawn an Agent with Tools
In chat:
```
"Spawn a dev-researcher agent to analyze the sapphire codebase"
```

The agent will:
1. Load `dev-tools` toolset
2. Use Claude Sonnet model
3. Have GitHub, Git, filesystem access
4. Execute up to 7 tool rounds
5. Report findings back

## Security Best Practices

1. **Keep .env secret**
   ```bash
   echo ".env" >> .gitignore
   ```

2. **Use environment variables for APIs**
   - Never hardcode API keys in code
   - Reference via `api_key_env` in configs

3. **Limit tool access**
   - Use restrictive toolsets for untrusted agents
   - Test tools manually before automation

4. **Monitor tool usage**
   - Check logs for suspicious activities
   - Review agent reports before acting

## Troubleshooting

### "MCP tools not available"
1. Check `.env` has correct `MCP_SERVER_HOST:PORT`
2. Verify MCP Docker server is running
3. Run `python validate_mcp_setup.py`

### "API key missing"
1. Check `.env` has the key
2. Verify spelling matches config (`api_key_env`)
3. Restart Sapphire after editing `.env`

### "Agent doesn't use tools"
1. Check agent's `toolset` is not "none"
2. Verify `max_tool_rounds` > 0
3. Look at agent logs for errors

### "Tool returns error"
1. Check tool result in chat (not agent failure)
2. Verify credentials if tool needs auth (GitHub, Azure)
3. Check file paths if filesystem tool

## Next Steps

1. **Read:** [MCP-QUICKSTART.md](MCP-QUICKSTART.md) (5 min)
2. **Configure:** Copy `.env.example` → `.env` and add API key
3. **Validate:** Run `python validate_mcp_setup.py`
4. **Run:** `python main.py`
5. **Explore:** Try chat and spawning agents
6. **Customize:** Edit personas/toolsets as needed

## Support & Resources

- **Quick Setup:** [MCP-QUICKSTART.md](MCP-QUICKSTART.md)
- **Full Guide:** [docs/MCP-INTEGRATION.md](docs/MCP-INTEGRATION.md)
- **Agent Guide:** [docs/MCP-AGENTS.md](docs/MCP-AGENTS.md)
- **Examples:** `personas.example.json`, `toolsets.example.json`
- **Validation:** `validate_mcp_setup.py`

## API Reference

### Using MCP in Custom Code

```python
from core.mcp_integration import mcp_client

# Get available tools
tools = await mcp_client.get_available_tools()

# Call a tool
result = await mcp_client.call_tool(
    tool_name='fetch_url',
    args={'url': 'https://example.com'}
)
```

### Environment Variables

See `.env.example` for:
- LLM API keys (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, etc.)
- MCP Server config (`MCP_SERVER_HOST`, `MCP_SERVER_PORT`)
- Tool enablement (`MCP_ENABLE_GITHUB`, `MCP_ENABLE_AZURE`, etc.)
- OAuth tokens (`GITHUB_PERSONAL_ACCESS_TOKEN`, etc.)

---

**Version:** 1.0
**Last Updated:** 2026-03-21
**Created for:** Sapphire AI Framework
