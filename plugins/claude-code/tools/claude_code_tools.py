# plugins/claude-code/tools/claude_code_tools.py
# Tools for dispatching Claude Code sessions from Sapphire
import json
import logging
import os
import re
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

ENABLED = True
EMOJI = '⚡'
AVAILABLE_FUNCTIONS = ['start_code_session', 'continue_code_session', 'list_code_sessions']

TOOLS = [
    {
        "type": "function",
        "is_local": True,
        "function": {
            "name": "start_code_session",
            "description": "Start a new Claude Code session to build, analyze, or modify code. Creates an isolated workspace and dispatches Claude Code with a mission. Returns session_id for follow-ups. Can take several minutes for complex tasks.",
            "parameters": {
                "type": "object",
                "properties": {
                    "mission": {
                        "type": "string",
                        "description": "Detailed description of what to build or do. Be specific — Claude Code works autonomously from this prompt."
                    },
                    "project_name": {
                        "type": "string",
                        "description": "Name for the workspace directory. Auto-generated from mission if not provided."
                    }
                },
                "required": ["mission"]
            }
        }
    },
    {
        "type": "function",
        "is_local": True,
        "function": {
            "name": "continue_code_session",
            "description": "Send a follow-up message to an existing Claude Code session. Resumes the previous conversation with full context preserved.",
            "parameters": {
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "Session ID from a previous start_code_session or continue_code_session call"
                    },
                    "message": {
                        "type": "string",
                        "description": "Follow-up instruction, refinement, or question for the existing session"
                    }
                },
                "required": ["session_id", "message"]
            }
        }
    },
    {
        "type": "function",
        "is_local": True,
        "function": {
            "name": "list_code_sessions",
            "description": "List recent Claude Code sessions with their status, workspace, and session IDs for resuming.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    }
]

# --- Safety & environment ---

# Sapphire's project root (used for safety checks)
_SAPPHIRE_ROOT = str(Path(__file__).resolve().parent.parent.parent.parent)


def _clean_env():
    """Build a clean env dict with conda/venv/uv stripped out."""
    env = os.environ.copy()

    # Strip conda
    for key in ['CONDA_PREFIX', 'CONDA_DEFAULT_ENV', 'CONDA_PROMPT_MODIFIER',
                'CONDA_SHLVL', 'CONDA_PYTHON_EXE', 'CONDA_EXE']:
        env.pop(key, None)

    # Strip venv/uv
    env.pop('VIRTUAL_ENV', None)
    env.pop('UV_VIRTUALENV', None)

    # Clean PATH — remove env bin dirs
    path_dirs = env.get('PATH', '').split(':')
    clean_path = [d for d in path_dirs
                  if '/envs/' not in d
                  and '/conda' not in d.lower()
                  and '/.venv/' not in d
                  and '/virtualenvs/' not in d]
    env['PATH'] = ':'.join(clean_path)

    return env


def _sanity_check(workspace_path):
    """Run safety checks before launching Claude Code. Returns error string or None."""
    ws = str(Path(workspace_path).resolve())

    # Check 1: workspace must NOT be inside Sapphire's project
    if ws.startswith(_SAPPHIRE_ROOT):
        return (f"SAFETY: Workspace '{ws}' is inside Sapphire's project directory ({_SAPPHIRE_ROOT}). "
                "Claude Code must work in an external directory to avoid conflicts.")

    # Check 2: workspace must NOT be in a conda/venv env
    for marker in ['/envs/', '/conda', '/.venv/', '/virtualenvs/']:
        if marker in ws.lower():
            return f"SAFETY: Workspace '{ws}' appears to be inside a Python environment. Use a neutral directory."

    # Check 3: verify claude command exists on clean PATH
    clean = _clean_env()
    result = subprocess.run(['which', 'claude'], env=clean, capture_output=True, text=True)
    if result.returncode != 0:
        return ("Claude Code command not found outside the conda/venv environment. "
                "Install it globally: npm install -g @anthropic-ai/claude-code")

    # Check 4: verify we're not leaking Sapphire's env
    if clean.get('CONDA_PREFIX'):
        return "SAFETY: Conda environment was not properly stripped. This is a bug — report to Krem."

    return None


def _get_settings():
    """Load plugin settings with defaults."""
    from core.plugin_loader import plugin_loader
    return plugin_loader.get_plugin_settings("claude-code") or {}


def _get_state():
    """Get persistent plugin state for session tracking."""
    from core.plugin_loader import plugin_loader
    return plugin_loader.get_plugin_state("claude-code")


def _list_workspace_files(workspace, max_files=20):
    """List files in workspace for the tool result."""
    try:
        files = []
        ws = Path(workspace)
        for f in sorted(ws.rglob('*')):
            if f.is_file() and '.git' not in f.parts and '__pycache__' not in f.parts:
                rel = f.relative_to(ws)
                size = f.stat().st_size
                if size > 1024 * 1024:
                    size_str = f"{size / (1024*1024):.1f}MB"
                elif size > 1024:
                    size_str = f"{size / 1024:.1f}KB"
                else:
                    size_str = f"{size}B"
                files.append(f"  {rel} ({size_str})")
                if len(files) >= max_files:
                    files.append(f"  ... and more")
                    break
        return '\n'.join(files) if files else '  (empty)'
    except Exception:
        return '  (could not list files)'


def _slugify(text, max_len=40):
    """Generate a filesystem-safe name from text."""
    words = re.sub(r'[^a-zA-Z0-9\s]', '', text).split()[:6]
    slug = '-'.join(w.lower() for w in words)
    return slug[:max_len] or 'project'


def _resolve_workspace(settings, project_name):
    """Resolve and create the workspace directory. Returns (path, error)."""
    base = settings.get('workspace_dir', '~/claude-workspaces')
    base = os.path.expanduser(base)
    workspace = os.path.join(base, project_name)

    try:
        os.makedirs(workspace, exist_ok=True)
    except OSError as e:
        return None, f"Cannot create workspace '{workspace}': {e}"

    return workspace, None


def _build_claude_args(mission, settings, session_id=None):
    """Build the claude CLI argument list based on mode and settings."""
    mode = settings.get('mode', 'standard')
    max_turns = int(settings.get('max_turns', 50))

    args = ['claude', '-p', mission, '--output-format', 'json']

    if session_id:
        args.extend(['--resume', session_id])

    args.extend(['--max-turns', str(max_turns)])

    # Mode-specific tool/permission config
    # NOTE: --permission-mode auto does NOT auto-approve in -p mode.
    # --allowedTools is what actually grants permission to use tools.
    if mode == 'strict':
        # File ops only, no shell — restrict available tools entirely
        args.extend(['--allowedTools', 'Read,Edit,Write,Glob,Grep'])
    elif mode == 'system_killer':
        # Unrestricted — approve everything including Bash with any args
        args.extend(['--allowedTools', 'Read,Edit,Write,Glob,Grep,Bash,NotebookEdit,WebFetch,WebSearch'])
    else:  # standard
        # Common dev workflow — code, run, test
        args.extend(['--allowedTools', 'Read,Edit,Write,Glob,Grep,Bash,NotebookEdit'])

    return args


def _run_claude(args, workspace, timeout_minutes=10):
    """Execute claude CLI and parse JSON output. Returns (parsed_dict, error_str)."""
    clean = _clean_env()
    timeout_sec = timeout_minutes * 60

    logger.info(f"[claude-code] Running: {' '.join(args[:6])}... in {workspace}")

    try:
        result = subprocess.run(
            args,
            cwd=workspace,
            env=clean,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            stdin=subprocess.DEVNULL
        )
    except subprocess.TimeoutExpired:
        return None, f"Claude Code session timed out after {timeout_minutes} minutes."
    except FileNotFoundError:
        return None, "Claude Code command not found. Install globally: npm install -g @anthropic-ai/claude-code"
    except Exception as e:
        return None, f"Failed to run Claude Code: {e}"

    # Claude -p with --output-format json writes JSON to stdout
    if result.returncode != 0 and not result.stdout.strip():
        stderr_tail = (result.stderr or '')[-500:]
        return None, f"Claude Code exited with error (code {result.returncode}): {stderr_tail}"

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        # Might have non-JSON output mixed in — try to find JSON
        for line in result.stdout.strip().split('\n'):
            line = line.strip()
            if line.startswith('{'):
                try:
                    data = json.loads(line)
                    break
                except json.JSONDecodeError:
                    continue
        else:
            # Fall back to raw text
            return {'result': result.stdout.strip(), 'session_id': None}, None

    return data, None


def _save_session(state, session_id, project_name, workspace, mission):
    """Track a session in plugin state."""
    import time
    sessions = state.get('sessions', {})
    sessions[session_id] = {
        'project': project_name,
        'workspace': workspace,
        'mission': mission[:200],
        'created': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'last_used': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'turns': 1,
    }
    # Keep only last 20 sessions
    if len(sessions) > 20:
        sorted_ids = sorted(sessions, key=lambda k: sessions[k].get('last_used', ''))
        for old_id in sorted_ids[:-20]:
            del sessions[old_id]
    state.save('sessions', sessions)


def _update_session(state, session_id):
    """Update last_used and turn count for a session."""
    import time
    sessions = state.get('sessions', {})
    if session_id in sessions:
        sessions[session_id]['last_used'] = time.strftime('%Y-%m-%dT%H:%M:%S')
        sessions[session_id]['turns'] = sessions[session_id].get('turns', 0) + 1
        state.save('sessions', sessions)


# --- Tool implementations ---

def _start_code_session(arguments):
    mission = arguments.get('mission', '').strip()
    if not mission:
        return "Mission is required — describe what you want Claude Code to build.", False

    project_name = arguments.get('project_name', '').strip()
    if not project_name:
        project_name = _slugify(mission)

    settings = _get_settings()

    # Resolve workspace
    workspace, err = _resolve_workspace(settings, project_name)
    if err:
        return err, False

    # Safety checks
    safety_err = _sanity_check(workspace)
    if safety_err:
        return safety_err, False

    # Build and run
    args = _build_claude_args(mission, settings)
    args.extend(['--name', project_name])

    data, err = _run_claude(args, workspace)
    if err:
        return f"Claude Code error: {err}", False

    session_id = data.get('session_id', '')
    result_text = data.get('result', str(data))

    # Track session
    if session_id:
        state = _get_state()
        _save_session(state, session_id, project_name, workspace, mission)

    # Build response with file listing
    mode = settings.get('mode', 'standard')
    file_listing = _list_workspace_files(workspace)
    lines = [
        f"**Claude Code Session Complete**",
        f"- Project: `{project_name}`",
        f"- Workspace: `{workspace}`",
        f"- Mode: {mode}",
    ]
    if session_id:
        lines.append(f"- Session ID: `{session_id}` (use with continue_code_session)")
    lines.append(f"\n**Files in workspace:**\n{file_listing}")
    lines.append(f"\n**Result:**\n{result_text}")

    return '\n'.join(lines), True


def _continue_code_session(arguments):
    session_id = arguments.get('session_id', '').strip()
    message = arguments.get('message', '').strip()

    if not session_id:
        return "session_id is required.", False
    if not message:
        return "message is required — what should Claude Code do next?", False

    settings = _get_settings()
    state = _get_state()
    sessions = state.get('sessions', {})

    # Find workspace from tracked session
    session_info = sessions.get(session_id, {})
    workspace = session_info.get('workspace')

    if not workspace or not os.path.isdir(workspace):
        # Fall back to default workspace
        workspace = os.path.expanduser(settings.get('workspace_dir', '~/claude-workspaces'))
        if not os.path.isdir(workspace):
            return f"Workspace not found for session {session_id}.", False

    # Safety check on workspace
    safety_err = _sanity_check(workspace)
    if safety_err:
        return safety_err, False

    args = _build_claude_args(message, settings, session_id=session_id)
    data, err = _run_claude(args, workspace)
    if err:
        return f"Claude Code error: {err}", False

    # Update tracking
    new_session_id = data.get('session_id', session_id)
    _update_session(state, session_id)

    result_text = data.get('result', str(data))
    project = session_info.get('project', 'unknown')
    file_listing = _list_workspace_files(workspace)

    lines = [
        f"**Claude Code Follow-up Complete**",
        f"- Project: `{project}`",
        f"- Session: `{new_session_id}`",
        f"\n**Files in workspace:**\n{file_listing}",
        f"\n**Result:**\n{result_text}",
    ]

    return '\n'.join(lines), True


def _list_code_sessions(arguments):
    state = _get_state()
    sessions = state.get('sessions', {})

    if not sessions:
        return "No Claude Code sessions tracked yet. Use start_code_session to begin.", True

    lines = ["**Recent Claude Code Sessions:**\n"]
    # Sort by last_used descending
    sorted_sessions = sorted(sessions.items(), key=lambda x: x[1].get('last_used', ''), reverse=True)

    for sid, info in sorted_sessions[:10]:
        workspace_exists = os.path.isdir(info.get('workspace', ''))
        status = '✓' if workspace_exists else '✗ (workspace gone)'
        lines.append(
            f"- **{info.get('project', '?')}** {status}\n"
            f"  ID: `{sid}` | Turns: {info.get('turns', 0)} | "
            f"Last: {info.get('last_used', '?')}\n"
            f"  Mission: {info.get('mission', '?')[:100]}"
        )

    return '\n'.join(lines), True


# --- Main dispatch ---

def execute(function_name, arguments, config):
    try:
        if function_name == 'start_code_session':
            return _start_code_session(arguments)
        elif function_name == 'continue_code_session':
            return _continue_code_session(arguments)
        elif function_name == 'list_code_sessions':
            return _list_code_sessions(arguments)
        else:
            return f"Unknown function: {function_name}", False
    except Exception as e:
        logger.error(f"[claude-code] {function_name} failed: {e}", exc_info=True)
        return f"Claude Code error: {e}", False
