from __future__ import annotations

import httpx

from lesphinx.config.settings import settings


class ElevenLabsTTSClient:
    BASE_URL = "https://api.elevenlabs.io/v1"

    def __init__(self) -> None:
        self._api_key = settings.elevenlabs_api_key
        self._voice_id = settings.elevenlabs_voice_id
        self._model = settings.elevenlabs_model

    async def synthesize(self, text: str) -> bytes:
        """Convert text to speech. Returns MP3 audio bytes."""
        url = f"{self.BASE_URL}/text-to-speech/{self._voice_id}"
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

        async with httpx.AsyncClient(timeout=settings.tts_timeout) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.content
