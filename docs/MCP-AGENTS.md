# docs/MCP-AGENTS.md

# MCP-Enabled Agents Configuration Guide

Agents in Sapphire can be configured to use MCP tools for powerful background operations. This guide shows how to set up and use agents with MCP tool access.

## Agent Roster Configuration

Define reusable agent profiles in `user/settings.json`:

```json
{
  "plugins": {
    "agents": {
      "max_concurrent": 5,
      "default_toolset": "none",
      "roster": [
        {
          "name": "dev-researcher",
          "label": "Dev Researcher",
          "provider": "llm",
          "model": "claude-sonnet-4-5",
          "toolset": "dev-tools",
          "prompt": "lovelace",
          "max_tool_rounds": 7
        },
        {
          "name": "github-monitor",
          "label": "GitHub Monitor",
          "provider": "llm",
          "model": "claude-sonnet-4-5",
          "toolset": "github-azure",
          "prompt": "generic",
          "max_tool_rounds": 5
        },
        {
          "name": "data-explorer",
          "label": "Data Explorer",
          "provider": "llm",
          "model": "claude-sonnet-4-5",
          "toolset": "data-tools",
          "prompt": "lovelace",
          "max_tool_rounds": 10
        },
        {
          "name": "infra-engineer",
          "label": "Infrastructure Engineer",
          "provider": "llm",
          "model": "claude-opus-4-5",
          "toolset": "ops-tools",
          "prompt": "alfred",
          "max_tool_rounds": 10
        },
        {
          "name": "research-specialist",
          "label": "Research Specialist",
          "provider": "llm",
          "model": "gemini-2.5-pro",
          "toolset": "research-tools",
          "prompt": "einstein",
          "max_tool_rounds": 8
        },
        {
          "name": "code-assistant",
          "label": "Code Assistant (Claude Code)",
          "provider": "claude-code",
          "model": "claude-opus-4-5",
          "toolset": "advanced",
          "execution_mode": "standard",
          "workspace": "./workspace"
        }
      ]
    }
  }
}
```

## Using Agents with MCP Tools

### Example 1: GitHub Repository Monitor

Spawn an agent to monitor GitHub repositories:

```
"Spawn a github-monitor agent to:
1. Check the sapphire repository for any new issues marked 'urgent'
2. List open PRs with pending reviews
3. Report back with actionable items"
```

The agent will:
- Use GitHub MCP tools to list issues and PRs
- Have 5 tool rounds to execute queries
- Report findings back to the chat

### Example 2: Data Analysis Agent

For analyzing datasets:

```
"Send a data-explorer agent to:
1. Read the sales_data.csv from /data/
2. Analyze trends by quarter
3. Create a summary report with key metrics"
```

With `data-tools` toolset, the agent has access to:
- Filesystem reading/writing
- Code execution (Python/Node)
- Desktop Commander for system operations

### Example 3: Infrastructure Auditing

For cloud infrastructure:

```
"Dispatch an infra-engineer agent to:
1. List all Azure resources in production subscription
2. Check for unencrypted storage accounts
3. Report security findings"
```

The `ops-tools` toolset provides:
- Azure resource management
- AWS instance operations
- Kubernetes cluster access
- GitHub Actions workflow queries

## Agent Toolset Integration

### How Toolsets Map to Agent Capabilities

Each agent's `toolset` setting determines which MCP tools it can use:

```json
{
  "name": "research-specialist",
  "toolset": "research-tools"
}
```

The `research-tools` toolset includes:
- `fetch_url` — Web scraping and data retrieval
- `sequentialthinking_plan` — Chain-of-thought reasoning
- `hf_hub_query` — Hugging Face model access
- `memory` — Persistent notes across sessions

### Tool Availability During Agent Execution

When an agent starts, it:

1. **Loads its toolset** from `user/toolsets/toolsets.json`
2. **Filters enabled tools** based on MCP settings
3. **Registers them** with the LLM
4. **Executes** up to `max_tool_rounds` iterations
5. **Reports back** results to the originating chat

### Forbidden Tools for Agents

For security, agents cannot:
- Use voice I/O tools (TTS/STT)
- Access chat history before their spawn time
- Modify settings or personas
- Spawn other agents (prevent infinite loops)
- Access credentials or API keys directly

## Model Selection for Agents

### Recommended Models by Task

| Task | Model | Why |
|------|-------|-----|
| Code review | `claude-opus-4-5` | Best reasoning for complex code |
| Data analysis | `claude-sonnet-4-5` | Fast, accurate calculations |
| Research | `gemini-2.5-pro` | Extended thinking capability |
| Infrastructure | `claude-opus-4-5` | Handles complex IaC |
| General tasks | `claude-sonnet-4-5` | Best price-to-performance |

### API Key Configuration

Agents use the same API keys configured in `.env`:

```bash
# .env
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=AIza...
OPENAI_API_KEY=sk-...
```

When an agent with `"model": "claude-opus-4-5"` runs, it automatically uses `ANTHROPIC_API_KEY`.

## Advanced: Custom Agent Behaviors

### Persistent Agent State

Agents can maintain state across multiple spawns using the Memory tool:

```python
# In agent implementation
from core.mcp_integration import mcp_client

async def save_agent_context(agent_name: str, context: dict):
    """Save agent context for future spawns."""
    await mcp_client.call_tool('memory_save', {
        'key': f'agent:{agent_name}:context',
        'value': json.dumps(context)
    })

async def load_agent_context(agent_name: str) -> dict:
    """Load preserved agent context."""
    result = await mcp_client.call_tool('memory_load', {
        'key': f'agent:{agent_name}:context'
    })
    return json.loads(result['value']) if result['success'] else {}
```

### Agent-to-Agent Coordination

Multiple agents can coordinate through shared memory:

```
You: "Spawn two agents:
1. 'data-explorer' to analyze last month's sales
2. 'infra-engineer' to audit costs

Have them share findings via memory so they can report together"
```

### Conditional Tool Enablement

Enable tools based on agent mission:

```python
# core/agents/adaptive_toolset.py

def get_tools_for_mission(mission: str) -> list:
    """Select tools based on mission keywords."""
    if 'github' in mission.lower():
        return load_toolset('github-azure')
    elif 'data' in mission.lower():
        return load_toolset('data-tools')
    elif 'infra' in mission.lower() or 'deploy' in mission.lower():
        return load_toolset('ops-tools')
    else:
        return load_toolset('research-tools')  # default
```

## Monitoring Agents

### Check Agent Status

```
Agent Status Command Output:

Active Agents (2):
┌────────────────────────────────────────┐
│ dev-researcher        [▓▓▓░░░░░░] 30% │
│ Time: 12.5s                            │
│ Tools used: 3/7                        │
│ Last action: Fetching GitHub issues    │
└────────────────────────────────────────┘

┌────────────────────────────────────────┐
│ data-explorer         [▓▓▓▓▓▓▓▓░░] 80%│
│ Time: 34.2s                            │
│ Tools used: 6/10                       │
│ Last action: Processing CSV data       │
└────────────────────────────────────────┘
```

### Agent Logs

View detailed agent execution in web UI: Agents tab → Click agent → View logs

```
dev-researcher:0001 - Tool #1: github_list_pull_requests
  Input: {"repo": "sapphire", "state": "open"}
  Output: Found 5 open PRs
  
dev-researcher:0002 - Tool #2: github_list_issues
  Input: {"repo": "sapphire", "labels": ["urgent"]}
  Output: Found 3 urgent issues
```

## Troubleshooting Agents with MCP Tools

### "Tool not found" Error

**Cause:** Tool not in agent's toolset or MCP category disabled

**Fix:**
1. Check `user/toolsets/toolsets.json` includes the tool
2. Verify MCP category enabled in `.env`: `MCP_ENABLE_GITHUB=true`
3. Restart Sapphire

### "API key missing" Error

**Cause:** Required environment variable not set

**Fix:**
```bash
# Check .env has the key
grep ANTHROPIC_API_KEY .env

# If missing, add it
echo "ANTHROPIC_API_KEY=sk-ant-YOUR_KEY_HERE" >> .env

# Restart Sapphire
python main.py
```

### Agent Takes Too Long

**Cause:** `max_tool_rounds` too low, or tools are slow

**Fix:**
```json
{
  "roster": [{
    "name": "slow-agent",
    "max_tool_rounds": 15,
    "model": "claude-opus-4-5"
  }]
}
```

### Agent Runs Out of Tools

"Tool limit reached" = agent used all `max_tool_rounds`

**Fix:** 
1. Increase `max_tool_rounds` in roster
2. Or simplify the task (give agent fewer sub-goals)

## See Also

- [MCP-INTEGRATION.md](MCP-INTEGRATION.md) - MCP Server setup
- [AGENTS.md](AGENTS.md) - Agent framework basics
- [TECHNICAL.md](TECHNICAL.md) - Architecture deep dive
