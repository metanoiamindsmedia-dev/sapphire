# core/scouts/code_worker.py — Claude Code scout worker thread
import logging
import threading
import time

from core.event_bus import publish, Events
from core.scouts.worker import SCOUT_NAMES
from core.scouts import claude_runner

logger = logging.getLogger(__name__)


class CodeScoutWorker:
    """Runs a Claude Code session in a background thread."""

    def __init__(self, scout_id, name, mission, project_name, settings,
                 chat_name='', on_complete=None):
        self.id = scout_id
        self.name = name
        self.mission = mission
        self.project_name = project_name
        self.chat_name = chat_name
        self.status = 'pending'
        self.result = None
        self.error = None
        self.tool_log = ['claude-code']
        self.session_id = None
        self.workspace = None
        self._start_time = None
        self._end_time = None
        self._cancelled = threading.Event()
        self._thread = None
        self._settings = settings
        self._on_complete = on_complete

    @property
    def elapsed(self):
        if self._start_time is None:
            return 0
        end = self._end_time or time.time()
        return round(end - self._start_time, 1)

    def start(self):
        self.status = 'running'
        self._start_time = time.time()
        self._thread = threading.Thread(
            target=self._run, daemon=True, name=f'code-scout-{self.name}'
        )
        self._thread.start()

    def cancel(self):
        self._cancelled.set()
        if self.status == 'running':
            self.status = 'cancelled'
            self._end_time = time.time()

    def _run(self):
        try:
            # Resolve workspace
            workspace, err = claude_runner.resolve_workspace(self._settings, self.project_name)
            if err:
                self.error = err
                self.status = 'failed'
                return
            self.workspace = workspace

            # Safety checks
            safety_err = claude_runner.sanity_check(workspace)
            if safety_err:
                self.error = safety_err
                self.status = 'failed'
                return

            # Write CLAUDE.md with coder instructions
            coder_instructions = self._settings.get('coder_instructions', '')
            claude_runner.write_claude_md(workspace, coder_instructions, self.project_name)

            if self._cancelled.is_set():
                self.status = 'cancelled'
                return

            # Build args and run
            args = claude_runner.build_claude_args(self.mission, self._settings)
            args.extend(['--name', self.project_name])

            data, err = claude_runner.run_claude(args, workspace)
            if err:
                self.error = err
                self.status = 'failed' if not self._cancelled.is_set() else 'cancelled'
                return

            self.session_id = data.get('session_id', '')
            result_text = data.get('result', str(data))
            file_listing = claude_runner.list_workspace_files(workspace)

            # Track session in plugin state
            if self.session_id:
                try:
                    from core.plugin_loader import plugin_loader
                    state = plugin_loader.get_plugin_state("claude-code")
                    sessions = state.get('sessions', {})
                    sessions[self.session_id] = {
                        'project': self.project_name,
                        'workspace': workspace,
                        'mission': self.mission[:200],
                        'created': time.strftime('%Y-%m-%dT%H:%M:%S'),
                        'last_used': time.strftime('%Y-%m-%dT%H:%M:%S'),
                        'turns': 1,
                    }
                    if len(sessions) > 20:
                        sorted_ids = sorted(sessions, key=lambda k: sessions[k].get('last_used', ''))
                        for old_id in sorted_ids[:-20]:
                            del sessions[old_id]
                    state.save('sessions', sessions)
                except Exception as e:
                    logger.warning(f"[code-scout] Could not save session: {e}")

            # Compile report
            lines = [
                f"**Code Scout {self.name} — Complete**",
                f"- Project: `{self.project_name}`",
                f"- Workspace: `{workspace}`",
            ]
            if self.session_id:
                lines.append(f"- Session ID: `{self.session_id}` (resumable)")
            lines.append(f"\n**Files:**\n{file_listing}")
            lines.append(f"\n**Result:**\n{result_text}")

            self.result = '\n'.join(lines)

            if self._cancelled.is_set():
                self.status = 'cancelled'
            else:
                self.status = 'done'

        except Exception as e:
            logger.error(f"Code scout {self.name} failed: {e}", exc_info=True)
            self.status = 'failed'
            self.error = str(e)
        finally:
            self._end_time = time.time()
            publish(Events.SCOUT_COMPLETED, {
                'id': self.id,
                'name': self.name,
                'status': self.status,
                'elapsed': self.elapsed,
            })
            logger.info(f"Code scout {self.name} finished: {self.status} ({self.elapsed}s)")
            if self._on_complete:
                try:
                    self._on_complete(self.id, self.chat_name)
                except Exception as e:
                    logger.error(f"Code scout {self.name} on_complete callback failed: {e}")

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'status': self.status,
            'mission': self.mission,
            'elapsed': self.elapsed,
            'has_result': self.result is not None,
            'error': self.error,
            'tool_log': self.tool_log,
            'chat_name': self.chat_name,
        }
