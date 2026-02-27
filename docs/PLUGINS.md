# Plugins

Sapphire plugins are self-contained extensions that add capabilities without touching core code. A plugin is a folder with a `plugin.json` manifest and optional Python/JavaScript files.

Plugins can:
- **Hook** into the chat pipeline (filter input, inject context, log responses)
- **Register tools** the AI can call (same format as built-in tools)
- **Declare voice commands** for instant actions ("stop", "reset")
- **Schedule cron tasks** that run on a timer
- **Provide a web settings UI** in the browser

Everything loads and unloads live — no restart needed.

---

## Quick Start

Minimal plugin in 2 files:

```
plugins/my-plugin/
  plugin.json
  hooks/greet.py
```

**plugin.json**:
```json
{
  "name": "my-plugin",
  "version": "1.0.0",
  "description": "Logs every chat",
  "author": "you",
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
    logger.info(f"User: {event.input}")
    logger.info(f"AI: {event.response}")
```

Enable in Settings > Plugins. It loads immediately.

---

## Where Plugins Live

| Path | Band | Priority Range | Tracked |
|------|------|----------------|---------|
| `plugins/` | System | 0-99 | Yes |
| `user/plugins/` | User | 100-199 | No (gitignored) |

User plugin priorities are automatically offset into the 100-199 range.

---

## Manifest Reference

Every plugin needs a `plugin.json` in its root.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | string | Yes | — | Unique identifier (folder name) |
| `version` | string | No | — | Semver (`1.0.0`) |
| `description` | string | No | — | One-line summary |
| `author` | string | No | — | Author name |
| `url` | string | No | — | Project URL (shown in Settings) |
| `priority` | int | No | 50 | Execution order within band (lower = first) |
| `default_enabled` | bool | No | false | Auto-enable on fresh install |
| `capabilities` | object | No | — | What the plugin provides |

### Priority Bands

Lower fires first. Within each band:

| Range | Purpose |
|-------|---------|
| 0-19 | Critical intercepts (stop, security) |
| 20-49 | Input modification (translation, formatting) |
| 50-79 | Context enrichment (prompt injection, state) |
| 80-99 | Observation (logging, analytics) |

User plugins use the same ranges but shifted to 100-199.

---

## Capabilities

### hooks

Map hook names to handler files:

```json
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
```

Each handler exports a function matching the hook name (e.g. `def pre_chat(event):`), or `def handle(event):` as fallback.

### voice_commands

Voice commands are pre_chat hooks with trigger pattern matching:

```json
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
```

| Field | Description |
|-------|-------------|
| `triggers` | Phrases to match (case-insensitive) |
| `match` | `exact`, `starts_with`, `contains`, or `regex` |
| `bypass_llm` | If true, gets highest priority (0-19) |
| `handler` | Path to handler file |

Multiple voice commands per plugin is fine — they're an array.

### tools

Python tool files registered with the function manager:

```json
"capabilities": {
  "tools": ["tools/my_tool.py"]
}
```

Tool files use the same format as `functions/*.py`. See [Tool File Format](#tool-file-format) below.

### schedule

Cron tasks that run a Python handler:

```json
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
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | string | Required | Display name |
| `cron` | string | `0 9 * * *` | Standard 5-field cron |
| `handler` | string | Required | Path to handler file |
| `description` | string | — | What the task does |
| `enabled` | bool | true | Whether it runs |
| `chance` | int | 100 | Percent chance to fire (1-100) |

Tasks appear in the Schedule UI and are removed when the plugin is disabled.

### web (Settings UI)

Plugins with a `web/` subdirectory can provide a settings tab:

```json
"capabilities": {
  "web": {
    "settingsUI": "plugin"
  }
}
```

Assets are served at `/plugin-web/{name}/`. See [Web Settings UI](#web-settings-ui) below.

---

## Hook Points

All hooks receive a mutable `HookEvent`. Changes persist across handlers in priority order.

| Hook | When | Key Fields | Use |
|------|------|-----------|-----|
| `pre_chat` | Before LLM | `input`, `skip_llm`, `response` | Filter input, bypass LLM |
| `prompt_inject` | System prompt build | `context_parts` | Append context strings |
| `post_chat` | After response saved | `input`, `response` | Logging, analytics |
| `pre_execute` | Before tool call | `function_name`, `arguments` | Modify args, block tools |
| `post_execute` | After tool call | `function_name`, `result` | Audit, react to results |
| `pre_tts` | Before speech | `tts_text`, `skip_tts` | Modify text, cancel TTS |

### HookEvent Fields

```python
@dataclass
class HookEvent:
    input: str = ""                          # User message
    skip_llm: bool = False                   # Bypass LLM / skip execution
    response: Optional[str] = None           # Direct response (with skip_llm)
    ephemeral: bool = False                  # Don't save to history (with skip_llm)
    context_parts: List[str] = []            # System prompt injections
    stop_propagation: bool = False           # Halt lower-priority hooks
    config: Any = None                       # System config (read-only)
    metadata: Dict[str, Any] = {}            # Free-form data (system, etc.)
    function_name: Optional[str] = None      # Tool name (execute hooks)
    arguments: Optional[dict] = None         # Tool args (mutable in pre_execute)
    result: Optional[str] = None             # Tool result (post_execute)
    tts_text: Optional[str] = None           # TTS text (mutable in pre_tts)
    skip_tts: bool = False                   # Cancel TTS
```

### System Access

Handlers get the `VoiceChatSystem` instance via `event.metadata.get("system")`. This gives access to TTS, STT, LLM, function manager, session manager, and all core components.

### Hook Examples

**pre_chat — block input:**
```python
def pre_chat(event):
    if "password" in event.input.lower():
        event.skip_llm = True
        event.response = "I can't help with that."
        event.stop_propagation = True
```

**prompt_inject — add context:**
```python
def prompt_inject(event):
    event.context_parts.append("The user's timezone is UTC+3.")
```

**pre_execute — block a tool:**
```python
def pre_execute(event):
    if event.function_name == "delete_memory":
        event.skip_llm = True
        event.result = "Deletion blocked by plugin."
```

**pre_tts — fix pronunciation:**
```python
def pre_tts(event):
    event.tts_text = event.tts_text.replace("API", "A.P.I.")
```

**voice command handler:**
```python
def pre_chat(event):
    system = event.metadata.get("system")
    if system and hasattr(system, "tts") and system.tts:
        system.tts.stop()
    event.skip_llm = True
    event.ephemeral = True
    event.response = "Stopped."
    event.stop_propagation = True
```

---

## Tool File Format

Plugin tools use the same format as `functions/*.py`:

```python
ENABLED = True
EMOJI = '🔧'
AVAILABLE_FUNCTIONS = ['my_tool_do_thing']

TOOLS = [
    {
        "type": "function",
        "is_local": True,
        "function": {
            "name": "my_tool_do_thing",
            "description": "Does the thing",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "description": "What to do it to"
                    }
                },
                "required": ["target"]
            }
        }
    }
]

def execute(function_name, arguments, config):
    """Called by function manager.

    Args:
        function_name: Which function was called
        arguments: Dict of parameters
        config: System config

    Returns:
        (message: str, success: bool) tuple
    """
    if function_name == "my_tool_do_thing":
        target = arguments.get("target", "")
        return f"Did the thing to {target}", True
    return "Unknown function", False
```

| Export | Type | Description |
|--------|------|-------------|
| `ENABLED` | bool | Whether tool is active |
| `EMOJI` | str | Display icon |
| `AVAILABLE_FUNCTIONS` | list | Function names this file provides |
| `TOOLS` | list | OpenAI-compatible function schemas |
| `execute()` | function | Dispatcher — returns `(message, success)` |

Tools are added to toolsets and the AI calls them contextually. See [TOOLS.md](TOOLS.md) for the full tools guide.

### Reading Plugin Settings from Tools

Tools can load their own settings:

```python
import json
from pathlib import Path

def _load_settings():
    path = Path("user/webui/plugins/my-plugin.json")
    if path.exists():
        return json.loads(path.read_text())
    return {}  # defaults
```

---

## Plugin State

Each plugin gets a persistent JSON key-value store at `user/plugin_state/{name}.json`:

```python
from core.plugin_loader import plugin_loader

state = plugin_loader.get_plugin_state("my-plugin")
state.get("counter", 0)        # read
state.save("counter", 42)      # write (auto-persists)
state.delete("counter")        # remove key
state.all()                    # entire dict
state.clear()                  # wipe everything
```

For heavier storage, plugins can create their own SQLite database.

---

## Schedule Handler Contract

```python
def run(event):
    """Called by continuity scheduler on cron match.

    event dict:
        system:       VoiceChatSystem instance
        config:       System config module
        task:         Task definition dict
        plugin_state: PluginState instance
    """
    system = event["system"]
    state = event["plugin_state"]

    # Do work...
    state.save("last_run", "2025-01-01")
    return "Done"  # Optional — logged to activity
```

---

## Web Settings UI

Plugins can provide a settings tab in Settings > Plugins.

### Structure

```
plugins/my-plugin/
  plugin.json              # "web": {"settingsUI": "plugin"}
  web/
    index.js               # Entry point (required)
    style.css              # Optional
```

Assets served at `/plugin-web/my-plugin/index.js`.

### index.js Contract

```javascript
import { registerPluginSettings } from '/static/shared/plugin-registry.js';
import pluginsAPI from '/static/shared/plugins-api.js';

export default {
  name: 'my-plugin',

  init(container) {
    registerPluginSettings({
      id: 'my-plugin',
      name: 'My Plugin',
      icon: '⚙️',
      helpText: 'Configure my plugin',

      render(container, settings) {
        // Build form HTML
        container.innerHTML = `
          <input type="text" id="mp-url" value="${settings.url || ''}">
        `;
      },

      load: () => pluginsAPI.getSettings('my-plugin'),
      save: (settings) => pluginsAPI.saveSettings('my-plugin', settings),

      getSettings(container) {
        // Extract form values
        return { url: container.querySelector('#mp-url').value };
      }
    });
  },

  destroy() { }
};
```

### Settings API

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/webui/plugins/{name}/settings` | Read settings |
| PUT | `/api/webui/plugins/{name}/settings` | Save settings |
| DELETE | `/api/webui/plugins/{name}/settings` | Reset to defaults |

Settings are stored at `user/webui/plugins/{name}.json`.

### Available Imports

```javascript
import { showToast } from '/static/shared/toast.js';
import { showHelpModal } from '/static/shared/modal.js';
import { registerPluginSettings } from '/static/shared/plugin-registry.js';
import pluginsAPI from '/static/shared/plugins-api.js';
```

Use CSS variables for theme compatibility: `var(--bg-secondary)`, `var(--text)`, `var(--border)`, `var(--bg-hover)`.

---

## Plugin Signing & Verification

Sapphire uses ed25519 signatures to verify plugin integrity.

### Verification States

| State | Badge | Behavior |
|-------|-------|----------|
| **Signed** | Green "Signed" | Always loads |
| **Unsigned** | Yellow "Unsigned" | Blocked unless "Allow Unsigned Plugins" is on |
| **Tampered** | Red "Tampered" | Always blocked — no override |

### How It Works

Each signed plugin has a `plugin.sig` file containing:
- SHA256 hashes of every signable file (`.py`, `.json`, `.js`, `.css`, `.html`, `.md`)
- An ed25519 signature over the hash manifest

On scan, the loader verifies:
1. Signature matches the baked-in public key
2. Every file's hash matches the manifest
3. No unrecognized files were added after signing

### Sideloading (Unsigned Plugins)

`ALLOW_UNSIGNED_PLUGINS` defaults to **off**. Enable it in Settings > Plugins with the toggle. A danger dialog warns about the risks.

When enabled, unsigned plugins load with a warning. Tampered plugins are always blocked regardless of this setting.

### Signing Your Own Plugins

For plugin developers distributing through channels other than the official store:

1. Generate an ed25519 keypair
2. Hash all signable files in your plugin
3. Sign the hash manifest with your private key
4. Ship the `plugin.sig` alongside your plugin

Users install your public key to verify. The official Sapphire public key is baked into `core/plugin_verify.py`.

---

## Lifecycle

### Startup

1. `plugin_loader.scan()` reads `plugins/` and `user/plugins/`
2. Each `plugin.json` is validated and signature-checked
3. Enabled plugins get hooks, tools, voice commands, and schedules registered
4. Scheduler tasks are deferred if the scheduler hasn't initialized yet

### Live Toggle

Settings > Plugins calls `PUT /api/webui/plugins/toggle/{name}`:
- **Enable**: Loads immediately — all capabilities register
- **Disable**: Unloads immediately — hooks, tools, schedules removed

Unsigned/tampered plugins return 403 and the toggle reverts.

### Hot Reload (Dev)

`POST /api/plugins/{name}/reload` unloads and reloads a single plugin.

Set `SAPPHIRE_DEV=1` to enable file watching — plugins auto-reload when `.py` or `.json` files change (2s polling).

If reload fails, the plugin stays unloaded. No half-loaded state.

### Rescan

`POST /api/plugins/rescan` discovers new or removed plugin folders without restart. Returns `{"added": [...], "removed": [...]}`.

---

## Error Isolation

A buggy plugin never crashes the system. If a hook handler throws an exception, it's logged and skipped — the next handler fires normally. Tool execution errors are caught and returned as error messages to the AI.

---

## Complete Example

A plugin that combines multiple capabilities:

```
plugins/smart-home/
  plugin.json
  hooks/context.py
  hooks/quick_lights.py
  tools/devices.py
  schedule/lock_check.py
  web/
    index.js
```

```json
{
  "name": "smart-home",
  "version": "2.0.0",
  "description": "Full smart home integration",
  "author": "you",
  "url": "https://example.com",
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
    "web": { "settingsUI": "plugin" }
  }
}
```

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/webui/plugins` | List all plugins with metadata |
| PUT | `/api/webui/plugins/toggle/{name}` | Enable/disable (live) |
| POST | `/api/plugins/rescan` | Discover new/removed plugins |
| POST | `/api/plugins/{name}/reload` | Hot-reload (dev) |
| GET | `/api/webui/plugins/{name}/settings` | Read plugin settings |
| PUT | `/api/webui/plugins/{name}/settings` | Save plugin settings |
| DELETE | `/api/webui/plugins/{name}/settings` | Reset plugin settings |
| GET | `/plugin-web/{name}/{path}` | Serve plugin web assets |

### Plugin List Response

```json
{
  "plugins": [
    {
      "name": "ssh",
      "enabled": true,
      "locked": false,
      "title": "SSH",
      "settingsUI": "plugin",
      "verified": true,
      "verify_msg": "verified",
      "version": "1.0.0",
      "author": "sapphire",
      "url": "https://sapphireblue.dev"
    }
  ],
  "locked": ["setup-wizard", "backup", "continuity"]
}
```

---

## Directory Structure

```
plugins/                          # System plugins (0-99)
  voice-commands/
    plugin.json
    plugin.sig
    hooks/stop.py
    hooks/reset.py
  ssh/
    plugin.json
    plugin.sig
    tools/ssh_tool.py
    web/index.js
  email/
  bitcoin/
  homeassistant/
  image-gen/
  toolmaker/

user/
  plugins/                        # User plugins (100-199)
    my-plugin/
      plugin.json
      hooks/handler.py
  plugin_state/                   # Per-plugin JSON state
    ssh.json
  webui/
    plugins.json                  # Enabled list: {"enabled": [...]}
    plugins/                      # Per-plugin settings
      ssh.json
      image-gen.json
```

---

## For Sapphire (AI Self-Reference)

When creating or modifying plugins:

- Plugin = folder in `plugins/{name}/` with `plugin.json` manifest
- `plugin.json` requires `name` field, everything else optional
- Hooks = Python functions receiving mutable `HookEvent` object
- Tools = `TOOLS` list + `execute(function_name, arguments, config)` returning `(str, bool)`
- Voice commands = pre_chat hooks with trigger matching, `bypass_llm: true` for instant response
- Schedule = cron tasks calling `run(event)` handler, event has `system`, `config`, `task`, `plugin_state`
- Web settings = `web/index.js` using `registerPluginSettings()`, served at `/plugin-web/{name}/`
- State = `plugin_loader.get_plugin_state(name)` for persistent key-value storage
- System access = `event.metadata.get("system")` in hooks
- Enable/disable live via `PUT /api/webui/plugins/toggle/{name}`
- All 6 hooks: `pre_chat`, `prompt_inject`, `post_chat`, `pre_execute`, `post_execute`, `pre_tts`
- Error isolation: exceptions logged and skipped, never crash pipeline
- Signing: ed25519 signatures in `plugin.sig`, tampered = always blocked, unsigned = blocked unless sideloading enabled
- Settings stored at `user/webui/plugins/{name}.json`, read via `GET /api/webui/plugins/{name}/settings`
