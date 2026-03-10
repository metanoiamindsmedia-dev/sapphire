# Google Calendar OAuth2 routes
# Handles the authorization flow and token management.

import json
import logging
import secrets
import time
import urllib.parse

import requests
from fastapi.responses import RedirectResponse

logger = logging.getLogger(__name__)

GOOGLE_AUTH_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
GOOGLE_TOKEN_URL = 'https://oauth2.googleapis.com/token'
SCOPES = 'https://www.googleapis.com/auth/calendar'
CALLBACK_PATH = '/api/plugin/google-calendar/callback'


def _get_state_path():
    from pathlib import Path
    state_dir = Path(__file__).parent.parent.parent.parent / 'user' / 'plugin_state'
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir / 'google-calendar.json'


def _load_state():
    path = _get_state_path()
    if path.exists():
        return json.loads(path.read_text(encoding='utf-8'))
    return {}


def _save_state(state):
    path = _get_state_path()
    path.write_text(json.dumps(state, indent=2), encoding='utf-8')


def _get_redirect_uri(request):
    """Build absolute callback URL from the current request's origin."""
    base = str(request.base_url).rstrip('/')
    return f"{base}{CALLBACK_PATH}"


def start_auth(request=None, settings=None, **_):
    """GET /api/plugin/google-calendar/auth — redirect to Google consent screen."""
    s = settings or {}
    client_id = s.get('GCAL_CLIENT_ID', '').strip()
    if not client_id:
        return {"error": "Set Google Client ID in Settings > Google Calendar first"}

    # Generate CSRF state token
    state_token = secrets.token_urlsafe(32)
    state = _load_state()
    state['oauth_state'] = state_token
    _save_state(state)

    params = {
        'client_id': client_id,
        'redirect_uri': _get_redirect_uri(request),
        'response_type': 'code',
        'scope': SCOPES,
        'access_type': 'offline',
        'prompt': 'consent',
        'state': state_token,
    }
    url = f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"
    return RedirectResponse(url=url, status_code=302)


def handle_callback(request=None, query=None, settings=None, **_):
    """GET /api/plugin/google-calendar/callback — exchange code for tokens."""
    q = query or {}
    code = q.get('code', '')
    state_token = q.get('state', '')
    error = q.get('error', '')

    if error:
        return RedirectResponse(url=f"/#settings?gcal_error={error}", status_code=302)

    if not code:
        return {"error": "No authorization code received"}

    # Verify CSRF state
    state = _load_state()
    if state_token != state.get('oauth_state'):
        return {"error": "State mismatch — possible CSRF attack"}
    state.pop('oauth_state', None)

    s = settings or {}
    client_id = s.get('GCAL_CLIENT_ID', '').strip()
    client_secret = s.get('GCAL_CLIENT_SECRET', '').strip()

    if not client_id or not client_secret:
        return {"error": "Missing client ID or secret in settings"}

    # Exchange code for tokens
    resp = requests.post(GOOGLE_TOKEN_URL, data={
        'code': code,
        'client_id': client_id,
        'client_secret': client_secret,
        'redirect_uri': _get_redirect_uri(request),
        'grant_type': 'authorization_code',
    }, timeout=15)

    if resp.status_code != 200:
        logger.error(f"[GCAL] Token exchange failed: {resp.text}")
        return {"error": f"Token exchange failed: {resp.status_code}"}

    tokens = resp.json()
    state['access_token'] = tokens['access_token']
    state['refresh_token'] = tokens.get('refresh_token', state.get('refresh_token', ''))
    state['expires_at'] = time.time() + tokens.get('expires_in', 3600)
    _save_state(state)

    logger.info("[GCAL] OAuth2 authorization successful")
    return RedirectResponse(url="/#settings", status_code=302)


def get_status(settings=None, **_):
    """GET /api/plugin/google-calendar/status — check if connected."""
    state = _load_state()
    return {"connected": bool(state.get('refresh_token'))}


def disconnect(settings=None, **_):
    """POST /api/plugin/google-calendar/disconnect — remove stored tokens."""
    state = _load_state()
    for key in ('access_token', 'refresh_token', 'expires_at', 'oauth_state'):
        state.pop(key, None)
    _save_state(state)
    return {"status": "disconnected"}
