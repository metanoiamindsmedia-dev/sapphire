"""Fireworks AI Whisper STT provider."""
import os
import logging
from typing import Optional

import config
from core.stt.providers.base import BaseSTTProvider

logger = logging.getLogger(__name__)

# Endpoint varies by model
FIREWORKS_ENDPOINTS = {
    'whisper-v3': 'https://audio-prod.api.fireworks.ai/v1/audio/transcriptions',
    'whisper-v3-turbo': 'https://audio-turbo.api.fireworks.ai/v1/audio/transcriptions',
}


class FireworksWhisperProvider(BaseSTTProvider):
    """Fireworks AI cloud Whisper — OpenAI-compatible transcription API."""

    def __init__(self):
        self._api_key = self._resolve_api_key()
        self._model = getattr(config, 'STT_FIREWORKS_MODEL', 'whisper-v3-turbo')
        if self._api_key:
            logger.info(f"Fireworks Whisper ready (model: {self._model})")
        else:
            logger.warning("Fireworks Whisper: no API key — check STT_FIREWORKS_API_KEY or FIREWORKS_API_KEY env")

    def _resolve_api_key(self) -> str:
        """Resolve API key: direct setting > env var."""
        key = getattr(config, 'STT_FIREWORKS_API_KEY', '')
        if key:
            return key
        return os.environ.get('FIREWORKS_API_KEY', '')

    def transcribe_file(self, audio_path: str) -> Optional[str]:
        """Transcribe via Fireworks API (multipart POST)."""
        if not self._api_key:
            logger.error("Fireworks Whisper: no API key configured")
            return None

        try:
            import httpx
        except ImportError:
            logger.error("httpx not installed — pip install httpx")
            return None

        endpoint = FIREWORKS_ENDPOINTS.get(self._model, FIREWORKS_ENDPOINTS['whisper-v3-turbo'])
        language = getattr(config, 'STT_LANGUAGE', 'en')

        try:
            with open(audio_path, 'rb') as f:
                response = httpx.post(
                    endpoint,
                    headers={'Authorization': self._api_key},
                    files={'file': ('audio.wav', f, 'audio/wav')},
                    data={
                        'model': self._model,
                        'language': language,
                        'response_format': 'json',
                    },
                    timeout=30.0,
                )
            response.raise_for_status()
            text = response.json().get('text', '').strip()
            if text:
                logger.debug(f"Fireworks transcription ({len(text)} chars)")
            return text

        except Exception as e:
            logger.error(f"Fireworks transcription failed: {e}")
            return None

    def is_available(self) -> bool:
        return bool(self._api_key)
