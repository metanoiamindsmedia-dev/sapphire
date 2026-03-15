# core/routes/scouts.py — Scout status API for frontend
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from core.auth import require_login
from core.api_fastapi import get_system

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/scouts/status")
async def scout_status(chat: str = Query('', description="Filter by chat name"), _=Depends(require_login)):
    """Get scout statuses for the UI pill bar, optionally filtered by chat."""
    system = get_system()
    if not hasattr(system, 'scout_manager'):
        return {"scouts": []}
    return {"scouts": system.scout_manager.check_all(chat_name=chat)}


@router.get("/api/scouts/providers")
async def scout_providers(_=Depends(require_login)):
    """Get enabled providers + their model options for the roster UI."""
    import config as cfg
    from core.chat.llm_providers import PROVIDER_METADATA
    providers = []
    for key, pconf in getattr(cfg, 'LLM_PROVIDERS', {}).items():
        if not pconf.get('enabled'):
            continue
        meta = PROVIDER_METADATA.get(key, {})
        models = meta.get('model_options') or {}
        current = pconf.get('model', '')
        providers.append({
            'key': key,
            'name': pconf.get('display_name', meta.get('display_name', key)),
            'current_model': current,
            'models': models,  # {model_id: display_name}
        })
    return {"providers": providers}


@router.post("/api/scouts/{scout_id}/dismiss")
async def dismiss_scout(scout_id: str, _=Depends(require_login)):
    """Dismiss/cancel a scout from the UI."""
    system = get_system()
    if not hasattr(system, 'scout_manager'):
        raise HTTPException(404, "Scout system not available")
    result = system.scout_manager.dismiss(scout_id)
    if 'error' in result:
        raise HTTPException(404, result['error'])
    return result
