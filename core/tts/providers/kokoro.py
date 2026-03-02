"""Kokoro TTS provider — local HTTP server on port 5012."""
import logging
from typing import Optional

import requests
import config

from .base import BaseTTSProvider

logger = logging.getLogger(__name__)


class KokoroTTSProvider(BaseTTSProvider):
    """Generates audio via the local Kokoro TTS server subprocess."""

    audio_content_type = 'audio/ogg'

    def __init__(self):
        self.primary_server = config.TTS_PRIMARY_SERVER
        self.fallback_server = config.TTS_FALLBACK_SERVER
        self.fallback_timeout = config.TTS_FALLBACK_TIMEOUT
        logger.info(f"Kokoro TTS provider: {self.primary_server}")

    def generate(self, text: str, voice: str, speed: float, **kwargs) -> Optional[bytes]:
        """POST to Kokoro server, return OGG bytes."""
        try:
            server_url = self._get_server_url()
            response = requests.post(f"{server_url}/tts", json={
                'text': text.replace("*", ""),
                'voice': voice,
                'speed': speed,
            })
            if response.status_code != 200:
                logger.error(f"Kokoro server error: {response.status_code}")
                return None
            return response.content
        except Exception as e:
            logger.error(f"Kokoro generate failed: {e}")
            return None

    def is_available(self) -> bool:
        """Check if Kokoro server is reachable."""
        return self._check_health(self.primary_server, timeout=self.fallback_timeout) or \
               self._check_health(self.fallback_server, timeout=1.0)

    def _get_server_url(self) -> str:
        """Get available server URL with fallback."""
        if self._check_health(self.primary_server, timeout=self.fallback_timeout):
            return self.primary_server
        logger.info(f"Kokoro primary unavailable, using fallback: {self.fallback_server}")
        return self.fallback_server

    def list_voices(self) -> list:
        """Return the built-in Kokoro voice list."""
        return KOKORO_VOICES

    def _check_health(self, server_url: str, timeout: float = None) -> bool:
        try:
            response = requests.get(f"{server_url}/health", timeout=timeout)
            return response.status_code == 200
        except Exception:
            return False


KOKORO_VOICES = [
    {'voice_id': 'am_adam', 'name': 'Adam', 'category': 'American Male'},
    {'voice_id': 'am_eric', 'name': 'Eric', 'category': 'American Male'},
    {'voice_id': 'am_liam', 'name': 'Liam', 'category': 'American Male'},
    {'voice_id': 'am_michael', 'name': 'Michael', 'category': 'American Male'},
    {'voice_id': 'am_onyx', 'name': 'Onyx', 'category': 'American Male'},
    {'voice_id': 'am_puck', 'name': 'Puck', 'category': 'American Male'},
    {'voice_id': 'af_bella', 'name': 'Bella', 'category': 'American Female'},
    {'voice_id': 'af_nicole', 'name': 'Nicole', 'category': 'American Female'},
    {'voice_id': 'af_heart', 'name': 'Heart', 'category': 'American Female'},
    {'voice_id': 'af_jessica', 'name': 'Jessica', 'category': 'American Female'},
    {'voice_id': 'af_sarah', 'name': 'Sarah', 'category': 'American Female'},
    {'voice_id': 'af_river', 'name': 'River', 'category': 'American Female'},
    {'voice_id': 'af_sky', 'name': 'Sky', 'category': 'American Female'},
    {'voice_id': 'bf_emma', 'name': 'Emma', 'category': 'British Female'},
    {'voice_id': 'bf_isabella', 'name': 'Isabella', 'category': 'British Female'},
    {'voice_id': 'bf_alice', 'name': 'Alice', 'category': 'British Female'},
    {'voice_id': 'bf_lily', 'name': 'Lily', 'category': 'British Female'},
    {'voice_id': 'bm_george', 'name': 'George', 'category': 'British Male'},
    {'voice_id': 'bm_daniel', 'name': 'Daniel', 'category': 'British Male'},
    {'voice_id': 'bm_lewis', 'name': 'Lewis', 'category': 'British Male'},
    {'voice_id': 'bm_fable', 'name': 'Fable', 'category': 'British Male'},
]
