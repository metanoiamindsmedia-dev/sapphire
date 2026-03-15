# plugins/claude-code/tools/claude_code_tools.py
# Tools for dispatching Claude Code sessions from Sapphire
import logging
import os

logger = logging.getLogger(__name__)

ENABLED = True
EMOJI = '⚡'
AVAILABLE_FUNCTIONS = [
    'start_code_session', 'continue_code_session',
    'list_code_sessions', 'dispatch_code_scout'
]

TOOLS = [
    {
        "type": "function",
        "is_local": True,
        "function": {
            "name": "start_code_session",
            "description": "Start a BLOCKING Claude Code session — you will wait until it finishes. Only use for very small, quick tasks (single file, simple edit). For building apps or anything that takes more than a few seconds, use dispatch_code_scout instead.",
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
    },
    {
        "type": "function",
        "is_local": True,
        "function": {
            "name": "dispatch_code_scout",
            "description": "Dispatch a code scout — sends Claude Code to build something in the background. This is the preferred way to build apps, scripts, or do complex coding tasks. Does NOT block — returns immediately while the scout works. Results report back automatically when done. Use when the user says 'build', 'create an app', 'code scout', 'dispatch a scout to code', or any coding task that would take more than a few seconds.",
            "parameters": {
                "type": "object",
                "properties": {
                    "mission": {
                        "type": "string",
                        "description": "Detailed description of what to build. Be specific — the scout works fully autonomously."
                    },
                    "project_name": {
                        "type": "string",
                        "description": "Name for the workspace directory. Auto-generated from mission if not provided."
                    }
                },
                "required": ["mission"]
            }
        }
    }
]


def _get_settings():
    """Load plugin settings with defaults."""
    from core.plugin_loader import plugin_loader
    return plugin_loader.get_plugin_settings("claude-code") or {}


def _get_state():
    """Get persistent plugin state for session tracking."""
    from core.plugin_loader import plugin_loader
    return plugin_loader.get_plugin_state("claude-code")


def _get_active_chat():
    """Get the current active chat name."""
    from core.api_fastapi import get_system
    try:
        return get_system().llm_chat.get_active_chat() or ''
    except Exception:
        return ''


def _get_scout_manager():
    """Get ScoutManager from system singleton."""
    from core.api_fastapi import get_system
    system = get_system()
    if not hasattr(system, 'scout_manager'):
        return None
    return system.scout_manager


# --- Blocking tool implementations ---

def _start_code_session(arguments):
    from core.scouts import claude_runner

    mission = arguments.get('mission', '').strip()
    if not mission:
        return "Mission is required — describe what you want Claude Code to build.", False

    project_name = arguments.get('project_name', '').strip()
    if not project_name:
        project_name = claude_runner.slugify(mission)

    settings = _get_settings()

    workspace, err = claude_runner.resolve_workspace(settings, project_name)
    if err:
        return err, False

    safety_err = claude_runner.sanity_check(workspace)
    if safety_err:
        return safety_err, False

    # Write CLAUDE.md with coder instructions
    coder_instructions = settings.get('coder_instructions', '')
    claude_runner.write_claude_md(workspace, coder_instructions, project_name)

    args = claude_runner.build_claude_args(mission, settings)
    args.extend(['--name', project_name])

    data, err = claude_runner.run_claude(args, workspace)
    if err:
        return f"Claude Code error: {err}", False

    session_id = data.get('session_id', '')
    result_text = data.get('result', str(data))

    if session_id:
        import time
        state = _get_state()
        sessions = state.get('sessions', {})
        sessions[session_id] = {
            'project': project_name,
            'workspace': workspace,
            'mission': mission[:200],
            'created': time.strftime('%Y-%m-%dT%H:%M:%S'),
            'last_used': time.strftime('%Y-%m-%dT%H:%M:%S'),
            'turns': 1,
        }
        if len(sessions) > 20:
            sorted_ids = sorted(sessions, key=lambda k: sessions[k].get('last_used', ''))
            for old_id in sorted_ids[:-20]:
                del sessions[old_id]
        state.save('sessions', sessions)

    mode = settings.get('mode', 'standard')
    file_listing = claude_runner.list_workspace_files(workspace)
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
    from core.scouts import claude_runner

    session_id = arguments.get('session_id', '').strip()
    message = arguments.get('message', '').strip()

    if not session_id:
        return "session_id is required.", False
    if not message:
        return "message is required — what should Claude Code do next?", False

    settings = _get_settings()
    state = _get_state()
    sessions = state.get('sessions', {})

    session_info = sessions.get(session_id, {})
    workspace = session_info.get('workspace')

    if not workspace or not os.path.isdir(workspace):
        workspace = os.path.expanduser(settings.get('workspace_dir', '~/claude-workspaces'))
        if not os.path.isdir(workspace):
            return f"Workspace not found for session {session_id}.", False

    safety_err = claude_runner.sanity_check(workspace)
    if safety_err:
        return safety_err, False

    args = claude_runner.build_claude_args(message, settings, session_id=session_id)
    data, err = claude_runner.run_claude(args, workspace)
    if err:
        return f"Claude Code error: {err}", False

    import time
    new_session_id = data.get('session_id', session_id)
    if session_id in sessions:
        sessions[session_id]['last_used'] = time.strftime('%Y-%m-%dT%H:%M:%S')
        sessions[session_id]['turns'] = sessions[session_id].get('turns', 0) + 1
        state.save('sessions', sessions)

    result_text = data.get('result', str(data))
    project = session_info.get('project', 'unknown')
    file_listing = claude_runner.list_workspace_files(workspace)

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


def _dispatch_code_scout(arguments):
    from core.scouts import claude_runner

    mission = arguments.get('mission', '').strip()
    if not mission:
        return "Mission is required — describe what you want Claude Code to build.", False

    project_name = arguments.get('project_name', '').strip()
    if not project_name:
        project_name = claude_runner.slugify(mission)

    manager = _get_scout_manager()
    if not manager:
        return "Scout system is not available.", False

    settings = _get_settings()
    chat_name = _get_active_chat()

    result = manager.spawn_code(mission, project_name, settings, chat_name=chat_name)
    if 'error' in result:
        return result['error'], False

    return (f"Code scout {result['name']} dispatched (id: {result['id']}).\n"
            f"- Project: `{project_name}`\n"
            f"- Workspace: `~/claude-workspaces/{project_name}/`\n"
            f"Working in background — results will appear automatically when done."), True


# --- Main dispatch ---

def execute(function_name, arguments, config):
    try:
        if function_name == 'start_code_session':
            return _start_code_session(arguments)
        elif function_name == 'continue_code_session':
            return _continue_code_session(arguments)
        elif function_name == 'list_code_sessions':
            return _list_code_sessions(arguments)
        elif function_name == 'dispatch_code_scout':
            return _dispatch_code_scout(arguments)
        else:
            return f"Unknown function: {function_name}", False
    except Exception as e:
        logger.error(f"[claude-code] {function_name} failed: {e}", exc_info=True)
        return f"Claude Code error: {e}", False
