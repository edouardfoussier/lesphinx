from __future__ import annotations

import hashlib
import logging

import httpx

from lesphinx.config.settings import settings

logger = logging.getLogger(__name__)


class ElevenLabsTTSClient:
    BASE_URL = "https://api.elevenlabs.io/v1"

    def __init__(self) -> None:
        self._api_key = settings.elevenlabs_api_key
        self._voice_id = settings.elevenlabs_voice_id
        self._model = settings.elevenlabs_model
        self._cache: dict[str, bytes] = {}

    def _cache_key(self, text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()[:16]

    async def synthesize(self, text: str) -> bytes:
        """Convert text to speech. Returns MP3 audio bytes."""
        key = self._cache_key(text)
        if key in self._cache:
            logger.debug("TTS cache hit for %s", text[:30])
            return self._cache[key]

        audio = await self._stream_synthesize(text)
        self._cache[key] = audio
        return audio

    async def _stream_synthesize(self, text: str) -> bytes:
        """Use the streaming endpoint for lower time-to-first-byte."""
        url = f"{self.BASE_URL}/text-to-speech/{self._voice_id}/stream"
        headers = {
            "xi-api-key": self._api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }
        payload = {
            "text": text,
            "model_id": self._model,
            "voice_settings": {
                "stability": 0.6,
                "similarity_boost": 0.8,
                "style": 0.3,
            },
        }

        chunks = []
        async with httpx.AsyncClient(timeout=settings.tts_timeout) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as response:
                response.raise_for_status()
                async for chunk in response.aiter_bytes(chunk_size=4096):
                    chunks.append(chunk)
        return b"".join(chunks)

    def warm_cache(self, texts: list[str]) -> None:
        """Pre-populate cache keys without actual API calls.
        Used by template TTS pre-generation."""
        pass

    def put_cache(self, text: str, audio: bytes) -> None:
        """Directly insert pre-generated audio into cache."""
        key = self._cache_key(text)
        self._cache[key] = audio
