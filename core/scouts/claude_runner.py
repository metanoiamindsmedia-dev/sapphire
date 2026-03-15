# core/scouts/claude_runner.py — Shared Claude Code execution logic
# Used by both the claude-code plugin (blocking tools) and CodeScoutWorker (background)
import json
import logging
import os
import re
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

# Sapphire's project root — never let Claude Code work inside it
SAPPHIRE_ROOT = str(Path(__file__).resolve().parent.parent.parent)

# Default CLAUDE.md template
_CLAUDE_MD_TEMPLATE = """# Project: {project_name}

## Instructions
{coder_instructions}

## Constraints
- Work only within this directory
- Do not access files outside the workspace
- Do not install system-wide packages
- Test your code before reporting done
- Keep dependencies minimal

## Context
Dispatched by Sapphire AI on behalf of the user.
"""

_DEFAULT_CODER_INSTRUCTIONS = """You are a code builder. Write clean, working code.
- Test your work by running it before reporting done
- Include a README.md with usage instructions
- Keep it simple and minimal — no over-engineering
- If you hit a problem you can't solve, describe it clearly in your final response"""


def clean_env():
    """Build a clean env dict with conda/venv/uv stripped out."""
    env = os.environ.copy()

    for key in ['CONDA_PREFIX', 'CONDA_DEFAULT_ENV', 'CONDA_PROMPT_MODIFIER',
                'CONDA_SHLVL', 'CONDA_PYTHON_EXE', 'CONDA_EXE']:
        env.pop(key, None)

    env.pop('VIRTUAL_ENV', None)
    env.pop('UV_VIRTUALENV', None)

    path_dirs = env.get('PATH', '').split(':')
    clean_path = [d for d in path_dirs
                  if '/envs/' not in d
                  and '/conda' not in d.lower()
                  and '/.venv/' not in d
                  and '/virtualenvs/' not in d]
    env['PATH'] = ':'.join(clean_path)

    return env


def sanity_check(workspace_path):
    """Run safety checks before launching Claude Code. Returns error string or None."""
    ws = str(Path(workspace_path).resolve())

    if ws.startswith(SAPPHIRE_ROOT):
        return (f"SAFETY: Workspace '{ws}' is inside Sapphire's project directory ({SAPPHIRE_ROOT}). "
                "Claude Code must work in an external directory to avoid conflicts.")

    for marker in ['/envs/', '/conda', '/.venv/', '/virtualenvs/']:
        if marker in ws.lower():
            return f"SAFETY: Workspace '{ws}' appears to be inside a Python environment. Use a neutral directory."

    clean = clean_env()
    result = subprocess.run(['which', 'claude'], env=clean, capture_output=True, text=True)
    if result.returncode != 0:
        return ("Claude Code command not found outside the conda/venv environment. "
                "Install it globally: npm install -g @anthropic-ai/claude-code")

    if clean.get('CONDA_PREFIX'):
        return "SAFETY: Conda environment was not properly stripped. This is a bug."

    return None


def slugify(text, max_len=40):
    """Generate a filesystem-safe name from text."""
    words = re.sub(r'[^a-zA-Z0-9\s]', '', text).split()[:6]
    slug = '-'.join(w.lower() for w in words)
    return slug[:max_len] or 'project'


def resolve_workspace(settings, project_name):
    """Resolve and create the workspace directory. Returns (path, error)."""
    base = settings.get('workspace_dir', '~/claude-workspaces')
    base = os.path.expanduser(base)
    workspace = os.path.join(base, project_name)

    try:
        os.makedirs(workspace, exist_ok=True)
    except OSError as e:
        return None, f"Cannot create workspace '{workspace}': {e}"

    return workspace, None


def write_claude_md(workspace, coder_instructions=None, project_name='project'):
    """Write CLAUDE.md into workspace if it doesn't already exist."""
    claude_md_path = os.path.join(workspace, 'CLAUDE.md')
    if os.path.exists(claude_md_path):
        return  # Don't overwrite — might be a resumed project with user edits

    instructions = coder_instructions or _DEFAULT_CODER_INSTRUCTIONS
    content = _CLAUDE_MD_TEMPLATE.format(
        project_name=project_name,
        coder_instructions=instructions.strip()
    )

    try:
        with open(claude_md_path, 'w', encoding='utf-8') as f:
            f.write(content)
        logger.info(f"[claude-runner] Wrote CLAUDE.md to {workspace}")
    except OSError as e:
        logger.warning(f"[claude-runner] Could not write CLAUDE.md: {e}")


def build_claude_args(mission, settings, session_id=None):
    """Build the claude CLI argument list based on mode and settings."""
    mode = settings.get('mode', 'standard')
    max_turns = int(settings.get('max_turns', 50))

    args = ['claude', '-p', mission, '--output-format', 'json']

    if session_id:
        args.extend(['--resume', session_id])

    args.extend(['--max-turns', str(max_turns)])

    # --allowedTools is what actually grants permission in -p mode
    if mode == 'strict':
        args.extend(['--allowedTools', 'Read,Edit,Write,Glob,Grep'])
    elif mode == 'system_killer':
        args.extend(['--allowedTools', 'Read,Edit,Write,Glob,Grep,Bash,NotebookEdit,WebFetch,WebSearch'])
    else:  # standard
        args.extend(['--allowedTools', 'Read,Edit,Write,Glob,Grep,Bash,NotebookEdit'])

    return args


def run_claude(args, workspace, timeout_minutes=30):
    """Execute claude CLI and parse JSON output. Returns (parsed_dict, error_str)."""
    env = clean_env()
    timeout_sec = timeout_minutes * 60

    logger.info(f"[claude-runner] Running: {' '.join(args[:6])}... in {workspace}")

    try:
        # Use process group so we can kill claude AND all its child processes on timeout
        proc = subprocess.Popen(
            args,
            cwd=workspace,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            text=True,
            start_new_session=True  # creates new process group
        )
        try:
            logger.info(f"[claude-runner] Subprocess started (pid {proc.pid}), waiting up to {timeout_minutes}min...")
            stdout, stderr = proc.communicate(timeout=timeout_sec)
            logger.info(f"[claude-runner] Subprocess finished (rc={proc.returncode}, stdout={len(stdout or '')} chars)")
            if stderr:
                logger.info(f"[claude-runner] Stderr: {stderr[:300]}")
        except subprocess.TimeoutExpired:
            # Kill entire process group (claude + all children)
            import os, signal
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            proc.wait(timeout=5)
            return None, f"Claude Code session timed out after {timeout_minutes} minutes."

        result = subprocess.CompletedProcess(args, proc.returncode, stdout, stderr)

    except FileNotFoundError:
        return None, "Claude Code command not found. Install globally: npm install -g @anthropic-ai/claude-code"
    except Exception as e:
        return None, f"Failed to run Claude Code: {e}"

    if result.returncode != 0 and not result.stdout.strip():
        stderr_tail = (result.stderr or '')[-500:]
        return None, f"Claude Code exited with error (code {result.returncode}): {stderr_tail}"

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        for line in result.stdout.strip().split('\n'):
            line = line.strip()
            if line.startswith('{'):
                try:
                    data = json.loads(line)
                    break
                except json.JSONDecodeError:
                    continue
        else:
            return {'result': result.stdout.strip(), 'session_id': None}, None

    return data, None


def list_workspace_files(workspace, max_files=20):
    """List files in workspace for reporting."""
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
