# SAPPHIRE MCP INTEGRATION - QUICK START GUIDE

Follow these steps to set up Sapphire with MCP Docker Server tools and multi-model LLM access.

## Prerequisites

- Sapphire installed and running
- MCP Docker Server available on `localhost:5000` (or configure the host/port in .env)
- At least one LLM API key (Claude, OpenAI, etc.)

## Step 1: Configure Environment Variables

Copy the template and fill in your API keys:

```bash
# Copy template
cp .env.example .env

# Edit .env with your favorite editor
# Add your API keys:
#   ANTHROPIC_API_KEY=sk-ant-...
#   OPENAI_API_KEY=sk-...
#   etc.

# Verify .env is in .gitignore to prevent accidental secrets commit
echo ".env" >> .gitignore
```

### Which LLM API Key to Use?

Pick one or more:

| Provider | Key Env Var | Free Tier | Performance | Good For |
|----------|------------|-----------|-------------|----------|
| Claude (Anthropic) | `ANTHROPIC_API_KEY` | No, $5/month min | Excellent | General, code, reasoning |
| OpenAI | `OPENAI_API_KEY` | No, $5/month min | Very Good | Code, web, general |
| Google Gemini | `GOOGLE_API_KEY` | Yes, 2M free tokens | Very Good | Extended thinking, research |
| Local (LM Studio) | None needed | Free, local | Varies | Privacy, no costs |

**Recommendation for Testing:** Start with 1-2 providers, add more later.

## Step 2: Verify MCP Server Connection

Check that MCP server is reachable:

```bash
# Test connection in Python
python3 -c "
import asyncio
from core.mcp_integration import mcp_client

async def test():
    is_available = mcp_client.is_available()
    print(f'MCP Server available: {is_available}')
    await mcp_client.initialize()
    tools = await mcp_client.get_available_tools()
    print(f'Found {len(tools)} tools')
    for tool in tools[:5]:
        print(f'  - {tool.name}')

asyncio.run(test())
"
```

Expected output:
```
MCP Server available: True
Found 184 tools
  - github_list_pull_requests
  - github_list_issues
  - azure_list_resources
  - fetch_url
  - memory_save
```

## Step 3: Choose and Configure a Persona

Option A: Use a pre-configured persona

```bash
# In Web UI:
# 1. Open Settings
# 2. Select "developer-assistant" persona
# 3. It has tools pre-enabled

# Or in settings.json:
# "DEFAULT_PERSONA": "developer-assistant"
```

Option B: Create a custom persona

Copy from `user/personas/personas.example.json` to `user/personas/personas.json`, then edit:

```json
{
  "my-assistant": {
    "name": "my-assistant",
    "tagline": "My custom AI assistant",
    "settings": {
      "llm_primary": "claude",
      "llm_model": "claude-sonnet-4-5",
      "toolset": "dev-tools"
    }
  }
}
```

## Step 4: Configure Toolsets

Copy example toolsets:

```bash
cp user/toolsets/toolsets.example.json user/toolsets/toolsets.json
```

Edit to enable tools you need:

```json
{
  "my-toolset": {
    "description": "GitHub + web tools",
    "tools": [
      "github_list_pull_requests",
      "github_list_issues",
      "fetch_url"
    ]
  }
}
```

## Step 5: Configure LLM Providers

In Web UI or settings.json, enable the providers you have API keys for:

```json
{
  "llm": {
    "LLM_PRIMARY": "claude",
    "LLM_PROVIDERS": {
      "claude": {
        "enabled": true,
        "api_key_env": "ANTHROPIC_API_KEY"
      },
      "gemini": {
        "enabled": true,
        "api_key_env": "GOOGLE_API_KEY"
      }
    }
  }
}
```

## Step 6: Test Chat with Tools

In Sapphire Web UI:

1. **Start a chat**
2. **Ask a question that requires tools:**
   - "Search the web for 'Sapphire AI framework' and tell me what you find"
   - "What are the top open PRs in the sapphire GitHub repo?"
   - "Show me the structure of the sapphire project"

Watch the tool calls in the chat to verify everything works.

## Step 7: Spawn an Agent with Tools

In chat, try:

```
Spawn a dev-researcher agent to analyze the sapphire codebase architecture
```

The agent will use GitHub tools to explore the repository.

## Troubleshooting

### "API Key missing" error

**Problem:** LLM provider can't find API key

**Solution:**
```bash
# 1. Check .env has the key
grep ANTHROPIC_API_KEY .env

# 2. If missing, add it
echo "ANTHROPIC_API_KEY=sk-ant-your-key-here" >> .env

# 3. Restart Sapphire
python main.py
```

### "No tools available" in chat

**Problem:** Tools not enabled or MCP server not running

**Solution:**
```bash
# 1. Check MCP server is running
# (Should see logs like "MCP server initialized" at startup)

# 2. Check toolset is not "none"
# Web UI: Settings > Look for "Toolset" setting

# 3. Verify MCP categories enabled in .env
grep MCP_ENABLE .env

# All should be "true" or enable specific ones you need
```

### Tools call but return errors

**Problem:** Tool succeeded but LLM got an error result

**Solution:** Check the tool result in chat. Common issues:
- GitHub: Private token needed for private repos → Set `GITHUB_PERSONAL_ACCESS_TOKEN` in .env
- Azure: Credentials missing → Set `AZURE_SUBSCRIPTION_ID` in .env
- File access: Permissions denied → Check file exists and readable

### Agent starts but doesn't use tools

**Problem:** Agent runs but doesn't call tools

**Solution:**
```json
{
  "toolset": "dev-tools",
  "max_tool_rounds": 7
}
```

Check in agent config that:
1. `toolset` is not "none"
2. `max_tool_rounds` > 0 (at least 3)

## Next Steps

1. **For Developers:** Read [docs/MCP-AGENTS.md](docs/MCP-AGENTS.md) for agent customization
2. **For Operations:** Read [docs/MCP-INTEGRATION.md](docs/MCP-INTEGRATION.md) for tool details
3. **For Customization:** Edit `user/personas/personas.json` and `user/toolsets/toolsets.json`

## Common Use Cases

### Use Case 1: Developer Assistant

Persona: `developer-assistant`
Toolset: `dev-tools`
Model: `claude-sonnet-4-5`
Agent: `dev-researcher`

Spawn agents to:
- Review code and PRs
- Analyze GitHub issues
- Help with debugging

### Use Case 2: Data Analysis

Persona: `data-analyst`
Toolset: `data-tools`
Model: `claude-sonnet-4-5`
Agent: `data-explorer`

Spawn agents to:
- Analyze CSV/JSON files
- Run Python code
- Create summaries

### Use Case 3: Infrastructure Management

Persona: `devops-engineer`
Toolset: `ops-tools`
Model: `claude-opus-4-5`
Agent: `infra-engineer`

Spawn agents to:
- Check Azure resources
- Monitor AWS instances
- Audit infrastructure

### Use Case 4: Research

Persona: `research-agent`
Toolset: `research-tools`
Model: `gemini-2.5-pro`
Agent: `research-specialist`

Spawn agents to:
- Deep research topics
- Access Hugging Face models
- Chain-of-thought reasoning

## See Also

- [docs/MCP-INTEGRATION.md](docs/MCP-INTEGRATION.md) - Full MCP setup guide
- [docs/MCP-AGENTS.md](docs/MCP-AGENTS.md) - Agent configuration details
- [docs/AGENTS.md](docs/AGENTS.md) - Agent framework reference
- [docs/PERSONAS.md](docs/PERSONAS.md) - Persona customization
- [docs/TECHNICAL.md](docs/TECHNICAL.md) - Architecture reference
