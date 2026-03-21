# docs/MCP-INTEGRATION.md

# MCP Docker Server Integration Guide

This guide covers setting up and configuring Sapphire to access MCP (Model Context Protocol) tools from your Docker container environment.

## Overview

Sapphire can be extended with powerful tools from the MCP Docker Server, including:

- **GitHub Tools** - Auto-create issues, read PRs, search repos
- **Azure Tools** - Manage Azure resources and deployments  
- **AWS Tools** - Access AWS services
- **Desktop Commander** - File system, process, and system operations
- **Playwright** - Browser automation
- **Git** - Clone repos, browse commits, manage branches
- **HuggingFace** - Model inference and dataset access
- **Fetch** - Web scraping and data retrieval
- **Memory** - Persistent memory for agents
- **Sequential Thinking** - Chain-of-thought reasoning

## Quick Setup

### 1. Enable .env Configuration

Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

Edit `.env` and configure:
- LLM API keys (at least one required: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, etc.)
- MCP Server connection: `MCP_SERVER_HOST`, `MCP_SERVER_PORT`
- Which tool categories to enable: `MCP_ENABLE_GITHUB=true`, etc.

### 2. Start Sapphire

With proper `.env` configuration:
```bash
python main.py
```

The system will:
1. Load all .env variables
2. Connect to MCP server
3. Discover available tools
4. Register them in personas and agents

## Configuration Best Practices

### API Key Management

**Never commit secrets to version control.**

Store API keys in `.env`:
```
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
GITHUB_PERSONAL_ACCESS_TOKEN=ghp_...
```

Sapphire loads these automatically. To pass to agents/personas, reference them by name:

```json
{
  "name": "assistant",
  "model": "claude-sonnet-4-5",
  "api_key_env": "ANTHROPIC_API_KEY"
}
```

### LLM Provider Selection

Configure which LLM provider to use in `user/settings.json`:

```json
{
  "llm": {
    "LLM_PRIMARY": "claude",
    "LLM_MODEL": "claude-sonnet-4-5",
    "MODEL_GENERATION_PROFILES": {
      "claude-sonnet-4-5": {
        "temperature": 0.7,
        "max_tokens": 16000
      }
    }
  }
}
```

### Model Selection for Personas

Personas can override the default model:

```json
{
  "name": "research-agent",
  "description": "Deep research assistant",
  "settings": {
    "llm_primary": "claude",
    "llm_model": "claude-sonnet-4-5"
  }
}
```

### Toolset Configuration

Specify which MCP tools an agent should use:

```json
{
  "name": "dev-assistant",
  "description": "Developer support agent",
  "settings": {
    "toolset": "github-azure",
    "max_tool_iterations": 5
  }
}
```

Create custom toolsets in `user/toolsets/toolsets.json`:

```json
{
  "github-azure": {
    "enabled_tools": [
      "github_create_issue",
      "github_list_pull_requests",
      "azure_list_resources",
      "azure_get_resource"
    ],
    "max_parallel": 3
  }
}
```

## Agent Integration Pattern

### Basic MCP-Enabled Agent

In `core/agents/`, create or modify agent definitions:

```python
# core/agents/mcp_agent.py
"""
MCP-enabled agent pattern - shows how to integrate MCP tools
"""

from core.mcp_integration import get_mcp_tools_for_agent
from core.agents import BaseAgent


class MCPAgent(BaseAgent):
    """
    Example agent that uses MCP tools.
    
    This demonstrates the pattern for agents that need external tools
    like GitHub, Azure, filesystem access, etc.
    """
    
    def __init__(self, name: str, config: dict):
        super().__init__(name, config)
        self.tools = {}
        self._setup_mcp_tools()
    
    def _setup_mcp_tools(self):
        """Register MCP tools based on agent's toolset."""
        toolset = self.config.get('toolset', 'default')
        
        # Get MCP tools filtered by this agent's toolset
        mcp_tools = get_mcp_tools_for_agent(toolset)
        
        # Merge with local tools
        self.tools.update(mcp_tools)
    
    async def execute(self, task: dict) -> dict:
        """Execute a task using available tools."""
        prompt = task.get('prompt', '')
        
        # Call LLM with available tools
        result = await self.llm_chat.call(
            messages=[{'role': 'user', 'content': prompt}],
            tools=self.tools,
            model=task.get('model') or self.config.get('model')
        )
        
        return {
            'success': True,
            'response': result
        }
```

### Continuity Task with MCP Tools

For scheduled/background tasks that need MCP tools:

```json
{
  "id": "github-monitor",
  "name": "GitHub Repository Monitor",
  "description": "Check GitHub repos every hour",
  "source": "system",
  "schedule": "0 * * * *",
  "enabled": true,
  "initial_message": "Check the following repositories for new PRs and issues:",
  "llm_model": "claude-sonnet-4-5",
  "toolset": "github",
  "max_tool_rounds": 3
}
```

## Environment Variables Reference

### LLM Providers

| Variable | Provider | Example |
|----------|----------|---------|
| `ANTHROPIC_API_KEY` | Claude | `sk-ant-...` |
| `OPENAI_API_KEY` | GPT-4, GPT-4o | `sk-...` |
| `GOOGLE_API_KEY` | Gemini | `AIza...` |
| `FIREWORKS_API_KEY` | Fireworks | `fw_...` |
| `XAI_API_KEY` | Grok | `xai_...` |
| `FEATHERLESS_API_KEY` | Featherless | `fl_...` |

### MCP Server

| Variable | Purpose | Default |
|----------|---------|---------|
| `MCP_SERVER_HOST` | MCP server hostname | `localhost` |
| `MCP_SERVER_PORT` | MCP server port | `5000` |
| `MCP_ENABLE_*` | Enable tool category | `true` |

### MCP Tool OAuth

| Variable | Purpose |
|----------|---------|
| `GITHUB_PERSONAL_ACCESS_TOKEN` | GitHub API access |
| `AZURE_SUBSCRIPTION_ID` | Azure resource access |
| `AWS_ACCESS_KEY_ID` | AWS API access |
| `HUGGINGFACE_TOKEN` | Model/dataset access |

## Troubleshooting

### MCP Tools Not Available

**Check enablement:**
```bash
# In settings or .env
MCP_ENABLE_GITHUB=true
MCP_ENABLE_FILESYSTEM=true
```

**Verify server connection:**
```python
from core.mcp_integration import mcp_client
print(mcp_client.is_available())  # Should return True
```

### Tool Execution Timeouts

Increase timeout in settings:
```json
{
  "tools": {
    "LLM_REQUEST_TIMEOUT": 300.0
  }
}
```

### Missing API Keys

Check .env file is loaded:
```bash
# Unix/Linux/Mac
export ANTHROPIC_API_KEY=sk-ant-...

# Windows PowerShell
$env:ANTHROPIC_API_KEY="sk-ant-..."
```

Verify in Web UI: Settings > LLM > Check which providers are "enabled"

## Advanced: Custom MCP Tools

If you want to add custom tools to the MCP server, see:
- MCP Docker Server configuration: `docker-mcp.yaml`
- Tool registry: `registry.yaml`
- Tool definitions: `tools.yaml`

These are typically managed by the Docker container orchestration system.

## Security Considerations

1. **Never expose API keys** - keep `.env` in `.gitignore`
2. **Use environment variables** - don't hardcode secrets in code
3. **Restrict tool permissions** - disable unused MCP categories
4. **Monitor tool usage** - check logs for suspicious activity
5. **Rotate credentials** - regularly update API keys

```
# .gitignore
.env
.env.local
user/settings.json
sapphire-data/
cache/
```

## See Also

- [AGENTS.md](AGENTS.md) - Agent framework documentation
- [PERSONAS.md](PERSONAS.md) - Persona customization
- [TECHNICAL.md](TECHNICAL.md) - Architecture reference
- [TOOLSETS.md](TOOLSETS.md) - Toolset configuration
