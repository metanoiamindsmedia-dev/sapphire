# core/scouts/manager.py — Scout lifecycle manager
import logging
import uuid
import threading

import config
from core.event_bus import publish, Events
from core.scouts.worker import ScoutWorker, SCOUT_NAMES

logger = logging.getLogger(__name__)


class ScoutManager:
    """Manages a pool of background scout workers."""

    def __init__(self, function_manager, tool_engine, max_concurrent=3):
        self._fm = function_manager
        self._tool_engine = tool_engine
        self.max_concurrent = max_concurrent
        self._scouts = {}  # id -> ScoutWorker
        self._lock = threading.Lock()
        self._name_counter = 0

    def _next_name(self):
        name = SCOUT_NAMES[self._name_counter % len(SCOUT_NAMES)]
        self._name_counter += 1
        return name

    def _active_count(self):
        return sum(1 for s in self._scouts.values() if s.status == 'running')

    def spawn(self, mission, model='', toolset='default', prompt='sapphire',
              persist_history=False) -> dict:
        """Spawn a new scout. Returns {id, name} or {error}."""
        with self._lock:
            if self._active_count() >= self.max_concurrent:
                return {'error': f'Scout limit reached ({self.max_concurrent}). Dismiss or wait for a scout to finish.'}

            scout_id = uuid.uuid4().hex[:8]
            name = self._next_name()

        # Build task_settings matching ExecutionContext's expected format
        task_settings = {
            'prompt': prompt,
            'toolset': toolset,
            'provider': 'auto',
            'model': model,
            'max_tool_rounds': 10,
            'max_parallel_tools': 3,
            'inject_datetime': True,
            # Scopes: all defaults (none/default) — scouts are lean
            'memory_scope': 'default',
            'knowledge_scope': 'default',
            'goal_scope': 'none',
            'email_scope': 'none',
            'bitcoin_scope': 'none',
            'gcal_scope': 'none',
            'telegram_scope': 'none',
            'discord_scope': 'none',
        }

        # If a specific provider is implied by model string (e.g. "claude-opus-4-6")
        # let ExecutionContext auto-resolve it
        if model:
            task_settings['model'] = model

        worker = ScoutWorker(scout_id, name, mission, task_settings, self._fm, self._tool_engine)

        with self._lock:
            self._scouts[scout_id] = worker

        worker.start()

        publish(Events.SCOUT_SPAWNED, {
            'id': scout_id,
            'name': name,
            'mission': mission,
        })

        logger.info(f"Scout {name} ({scout_id}) dispatched: {mission[:80]}")
        return {'id': scout_id, 'name': name}

    def check_all(self) -> list:
        """Return status of all scouts (active and completed)."""
        with self._lock:
            return [s.to_dict() for s in self._scouts.values()]

    def recall(self, scout_id) -> dict:
        """Get a scout's report. Returns {name, status, result} or {error}."""
        with self._lock:
            scout = self._scouts.get(scout_id)
        if not scout:
            return {'error': f'Scout {scout_id} not found.'}
        if scout.status == 'running':
            return {'name': scout.name, 'status': 'running', 'result': 'Scout is still running.'}
        return {
            'name': scout.name,
            'status': scout.status,
            'result': scout.result or scout.error or 'No result.',
            'elapsed': scout.elapsed,
        }

    def dismiss(self, scout_id) -> dict:
        """Cancel/cleanup a scout. Returns {name, status} or {error}."""
        with self._lock:
            scout = self._scouts.get(scout_id)
            if not scout:
                return {'error': f'Scout {scout_id} not found.'}

        if scout.status == 'running':
            scout.cancel()

        with self._lock:
            self._scouts.pop(scout_id, None)

        publish(Events.SCOUT_DISMISSED, {'id': scout_id, 'name': scout.name})
        logger.info(f"Scout {scout.name} ({scout_id}) dismissed")
        return {'name': scout.name, 'status': 'dismissed', 'last_result': scout.result}

    def get_options(self) -> dict:
        """Return available models, toolsets, and prompts for spawning scouts."""
        # Models
        providers_config = getattr(config, 'LLM_PROVIDERS', {})
        models = []
        for key, pconf in providers_config.items():
            if pconf.get('enabled'):
                models.append({
                    'key': key,
                    'name': pconf.get('display_name', key),
                    'model': pconf.get('model', ''),
                })

        # Toolsets
        from core.toolsets import toolset_manager
        toolset_names = toolset_manager.get_toolset_names()
        # Also include built-in function module names
        builtin = list(self._fm.function_modules.keys())
        all_toolsets = sorted(set(toolset_names + builtin))

        # Prompts
        from core import prompts
        prompt_list = prompts.list_prompts()

        return {
            'models': models,
            'toolsets': all_toolsets,
            'prompts': prompt_list,
        }
