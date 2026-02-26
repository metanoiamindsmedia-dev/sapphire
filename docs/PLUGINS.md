# Plugin Author Guide

Sapphire's plugin system is manifest-driven, priority-ordered, and error-isolated. Plugins can hook into the chat pipeline, register tools, declare voice commands, schedule cron tasks, and serve web settings — all without touching core code.

## Quick Start

Minimal plugin in 2 files:

```
plugins/my_plugin/
  plugin.json         # Manifest (required)
  hooks/greet.py      # Handler
```

**plugin.json**:
```json
{
  "name": "my_plugin",
  "version": "1.0.0",
  "description": "Logs every chat response",
  "author": "you",
  "priority": 50,
  "capabilities": {
    "hooks": {
      "post_chat": "hooks/greet.py"
    }
  }
}
```

**hooks/greet.py**:
```python
import logging
logger = logging.getLogger(__name__)

def post_chat(event):
    logger.info(f"User said: {event.input}")
    logger.info(f"AI replied: {event.response}")
```

Enable in Settings > Plugins. No restart needed.

---

## Manifest Reference

Every plugin must have a `plugin.json` in its root directory.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Unique plugin identifier |
| `version` | string | No | Semver version |
| `description` | string | No | One-line summary |
| `author` | string | No | Author name |
| `priority` | int | No | Execution order within band (default: 50) |
| `capabilities` | object | No | What the plugin provides (see below) |

### Priority Bands

| Band | Range | Source |
|------|-------|--------|
| System | 0-99 | `plugins/` directory |
| User | 100-199 | `user/plugins/` directory (auto-offset) |

Within each band:
- **0-19**: Critical intercepts (stop, security)
- **20-49**: Input modification (translation, formatting)
- **50-79**: Context enrichment (prompt injection, state)
- **80-99**: Observation (logging, analytics)

Lower priority fires first.

---

## Capabilities

### hooks

Map hook names to handler file paths:

```json
{
  "capabilities": {
    "hooks": {
      "pre_chat": "hooks/filter.py",
      "prompt_inject": "hooks/context.py",
      "post_chat": "hooks/log.py",
      "pre_execute": "hooks/guard.py",
      "post_execute": "hooks/audit.py",
      "pre_tts": "hooks/tts_filter.py"
    }
  }
}
```

Each handler file must export a function matching the hook name (e.g., `def pre_chat(event):`), or a generic `def handle(event):` as fallback.

### voice_commands

Voice commands are auto-wired `pre_chat` hooks with trigger pattern matching:

```json
{
  "capabilities": {
    "voice_commands": [
      {
        "triggers": ["stop", "halt", "be quiet"],
        "match": "exact",
        "bypass_llm": true,
        "handler": "hooks/stop.py",
        "description": "Stop TTS and cancel generation"
      }
    ]
  }
}
```

| Field | Description |
|-------|-------------|
| `triggers` | Array of trigger phrases (case-insensitive) |
| `match` | `exact`, `starts_with`, `contains`, or `regex` |
| `bypass_llm` | If true, gets highest priority in band |
| `handler` | Path to handler file (same contract as hooks) |

### tools

Array of Python tool files to register with the function manager:

```json
{
  "capabilities": {
    "tools": ["tools/my_tool.py"]
  }
}
```

Tool files follow the same format as `functions/*.py` — define tool schemas and executors.

### schedule

Cron-scheduled tasks that run a Python handler:

```json
{
  "capabilities": {
    "schedule": [
      {
        "name": "Daily Digest",
        "cron": "0 9 * * *",
        "handler": "schedule/digest.py",
        "description": "Morning email summary",
        "enabled": true,
        "chance": 100
      }
    ]
  }
}
```

See [Schedule Tasks](#schedule-tasks) section below for the handler contract.

### web

Declares that the plugin has a web settings interface:

```json
{
  "capabilities": {
    "web": {
      "settingsUI": "plugin"
    }
  }
}
```

Web assets are served from `web/` subdirectory via `/plugin-web/{name}/`.

---

## Hook Points

All hooks receive a mutable `HookEvent` object. Changes persist across handlers in priority order.

| Hook | When | Key Fields | Mutable |
|------|------|-----------|---------|
| `pre_chat` | Before LLM call | `input`, `skip_llm`, `response` | Yes — modify input, bypass LLM |
| `prompt_inject` | During system prompt build | `context_parts` | Yes — append context strings |
| `post_chat` | After final response saved | `input`, `response` | Read-only by convention |
| `pre_execute` | Before tool execution | `function_name`, `arguments`, `skip_llm` | Yes — modify args, skip execution |
| `post_execute` | After tool execution | `function_name`, `arguments`, `result` | Read-only by convention |
| `pre_tts` | Before text-to-speech | `tts_text`, `skip_tts` | Yes — modify text, cancel TTS |

### HookEvent Fields

```python
@dataclass
class HookEvent:
    input: str = ""                          # User message
    skip_llm: bool = False                   # Bypass LLM / skip tool execution
    response: Optional[str] = None           # Direct response / final response
    context_parts: List[str] = []            # System prompt injections
    stop_propagation: bool = False           # Stop lower-priority hooks
    config: Any = None                       # System config (read-only)
    metadata: Dict[str, Any] = {}            # Arbitrary plugin data
    function_name: Optional[str] = None      # Tool name (execute hooks)
    arguments: Optional[dict] = None         # Tool args (pre_execute, mutable)
    result: Optional[str] = None             # Tool result (post_execute)
    tts_text: Optional[str] = None           # TTS text (pre_tts, mutable)
    skip_tts: bool = False                   # Cancel TTS (pre_tts)
```

### Hook Handler Examples

**pre_chat** — input filter:
```python
def pre_chat(event):
    if "password" in event.input.lower():
        event.skip_llm = True
        event.response = "I can't help with that."
        event.stop_propagation = True
```

**prompt_inject** — add context:
```python
def prompt_inject(event):
    event.context_parts.append("The user's timezone is UTC+3.")
```

**pre_execute** — block a tool:
```python
def pre_execute(event):
    if event.function_name == "delete_memory" and not is_confirmed():
        event.skip_llm = True
        event.result = "Deletion requires confirmation."
```

**pre_tts** — text replacement:
```python
def pre_tts(event):
    event.tts_text = event.tts_text.replace("API", "A.P.I.")
```

---

## Plugin State

Each plugin gets a persistent JSON key-value store at `user/plugin_state/{name}.json`.

Access via handler:
```python
def post_chat(event):
    # Get state from plugin loader
    from core.plugin_loader import plugin_loader
    state = plugin_loader.get_plugin_state("my_plugin")

    count = state.get("chat_count", 0)
    state.save("chat_count", count + 1)
```

**PluginState API**:
- `state.get(key, default=None)` — read a value
- `state.save(key, value)` — write a value (auto-persists)
- `state.delete(key)` — remove a key
- `state.all()` — get all data as dict
- `state.clear()` — wipe all data

---

## Schedule Tasks

Plugins can register cron tasks that run Python handlers on a schedule.

### Handler Contract

Handler file must export a `run(event)` function:

```python
# schedule/digest.py

def run(event):
    """Called by continuity scheduler on cron match.

    event dict keys:
        system: VoiceChatSystem instance
        config: System config module
        task: The task definition dict
        plugin_state: PluginState instance for this plugin
    """
    system = event["system"]
    state = event["plugin_state"]

    # Do work...
    result = "Digest sent"

    state.save("last_run", str(datetime.now()))
    return result  # Optional — logged to activity
```

### Cron Syntax

Standard 5-field cron: `minute hour day month weekday`

| Expression | Meaning |
|-----------|---------|
| `0 9 * * *` | Every day at 9:00 AM |
| `*/15 * * * *` | Every 15 minutes |
| `0 0 * * 1` | Every Monday at midnight |
| `0 9,18 * * *` | 9 AM and 6 PM daily |

### Schedule Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | string | Required | Display name for the task |
| `cron` | string | `0 9 * * *` | Cron expression |
| `handler` | string | Required | Path to handler file (relative to plugin dir) |
| `description` | string | `""` | What the task does |
| `enabled` | bool | `true` | Whether task runs on schedule |
| `chance` | int | `100` | Percent chance to fire on each match (1-100) |

Plugin schedule tasks appear in the Schedule UI with their plugin name. They are automatically removed when the plugin is disabled or unloaded.

---

## Web Settings

Plugins can provide a settings tab in the Settings view.

1. Set `"web": {"settingsUI": "plugin"}` in manifest
2. Create `web/settings.html` in your plugin directory
3. Assets served at `/plugin-web/{name}/`

For core infrastructure plugins (setup-wizard, backup, etc.), use `"settingsUI": "core"` — these load from `interfaces/web/static/core-ui/`.

---

## Lifecycle

### Discovery & Loading

1. **Scan**: `plugin_loader.scan()` reads `plugins/` and `user/plugins/`
2. **Validate**: Each `plugin.json` must have a `name` field
3. **Enable check**: Compared against `user/webui/plugins.json` enabled list
4. **Load**: Enabled plugins get hooks, voice commands, tools, and schedules registered

### Live Toggle

Enabling/disabling via Settings > Plugins calls `PUT /api/webui/plugins/toggle/{name}`:
- **Enable**: `_load_plugin()` — registers all capabilities immediately
- **Disable**: `unload_plugin()` — deregisters hooks, tools, schedule tasks

No restart needed for backend plugins.

### Hot Reload

For development, use `POST /api/plugins/{name}/reload` to unload and reload a plugin.

Set `SAPPHIRE_DEV=1` environment variable to enable automatic file watching — plugins reload when any `.py` or `.json` file changes (2-second polling).

If reload fails, the plugin stays unloaded (no half-loaded state). A `plugin_reloaded` event is published on success.

---

## Examples

### Stop Plugin (Voice Command)

Intercepts "stop" / "halt" / "shut up" to immediately halt TTS and cancel generation:

```
plugins/stop/
  plugin.json
  hooks/stop.py
```

```python
# hooks/stop.py
def pre_chat(event):
    system = event.metadata.get("system")
    if system:
        if hasattr(system, "tts") and system.tts:
            system.tts.stop()
        if hasattr(system, "llm_chat") and system.llm_chat:
            streaming = getattr(system.llm_chat, "streaming_chat", None)
            if streaming:
                streaming.cancel_flag = True
    event.skip_llm = True
    event.response = "Stopped."
    event.stop_propagation = True
```

### Home Assistant (Tools)

Registers tools for light/switch/scene control:

```json
{
  "name": "homeassistant",
  "version": "1.0.0",
  "description": "Home Assistant integration",
  "priority": 50,
  "capabilities": {
    "tools": ["tools/homeassistant.py"]
  }
}
```

### Scheduled Digest (Schedule)

Plugin that sends a daily summary:

```json
{
  "name": "daily_digest",
  "version": "1.0.0",
  "description": "Morning digest via email",
  "capabilities": {
    "schedule": [
      {
        "name": "Morning Digest",
        "cron": "0 8 * * 1-5",
        "handler": "schedule/digest.py",
        "description": "Weekday morning summary"
      }
    ]
  }
}
```

### Multi-Capability Plugin

A plugin can combine hooks, tools, voice commands, schedule, and web:

```json
{
  "name": "smart_home",
  "version": "2.0.0",
  "description": "Full smart home integration",
  "priority": 50,
  "capabilities": {
    "hooks": {
      "prompt_inject": "hooks/context.py"
    },
    "voice_commands": [
      {
        "triggers": ["lights on", "lights off"],
        "match": "exact",
        "bypass_llm": true,
        "handler": "hooks/quick_lights.py"
      }
    ],
    "tools": ["tools/devices.py"],
    "schedule": [
      {
        "name": "Nightly Lock Check",
        "cron": "0 23 * * *",
        "handler": "schedule/lock_check.py"
      }
    ],
    "web": {
      "settingsUI": "plugin"
    }
  }
}
```

---

## Plugin Locations

| Path | Band | Git Tracked |
|------|------|-------------|
| `plugins/` | System (0-99) | Yes |
| `user/plugins/` | User (100-199) | No |

## Error Isolation

A buggy plugin never crashes the pipeline. If a hook handler throws an exception, it's logged and skipped — the next handler in priority order fires normally.

## System Access

Handlers can access the `VoiceChatSystem` via `event.metadata.get("system")` (available in `pre_chat` and `post_chat`). This gives access to TTS, STT, LLM, function manager, and all other system components.

## For AI Assistants

When creating plugins for Sapphire:
- Plugin = manifest-driven extension in `plugins/{name}/`
- Must have `plugin.json` with `name` field
- Hooks = Python functions receiving `HookEvent` object
- Tools = same format as `functions/*.py`
- Voice commands = `pre_chat` hooks with trigger matching
- Schedule = cron tasks calling `run(event)` handlers
- Enable via Settings > Plugins (no restart)
- All 6 hook points: `pre_chat`, `prompt_inject`, `post_chat`, `pre_execute`, `post_execute`, `pre_tts`
