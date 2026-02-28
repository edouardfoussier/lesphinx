"""PersonaPlex real-time voice client via fal.ai WebSocket.

Connects to fal.ai's hosted PersonaPlex model for full-duplex
voice conversation.  Audio is PCM s16le 24kHz mono, transported
as base64 over JSON WebSocket frames.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from dataclasses import dataclass, field
from typing import AsyncIterator, Callable

import websockets
from websockets.asyncio.client import ClientConnection

from lesphinx.config.settings import settings

logger = logging.getLogger(__name__)

FAL_REALTIME_URL = "wss://fal.run/{model_id}/ws"
FAL_TOKEN_URL = "https://rest.alpha.fal.ai/tokens/"

AUDIO_SAMPLE_RATE = 24_000
AUDIO_CHANNELS = 1
AUDIO_FORMAT = "s16le"


@dataclass
class PersonaPlexResponse:
    audio: bytes
    text: str


@dataclass
class PersonaPlexSession:
    """Manages a real-time PersonaPlex WebSocket session."""

    persona_prompt: str
    voice: str = "NATM0"
    _ws: ClientConnection | None = field(default=None, repr=False)
    _connected: bool = False
    _response_queue: asyncio.Queue[PersonaPlexResponse | None] = field(
        default_factory=asyncio.Queue, repr=False
    )

    async def connect(self) -> None:
        model_id = settings.personaplex_model
        url = FAL_REALTIME_URL.format(model_id=model_id)

        headers = {}
        if settings.fal_api_key:
            headers["Authorization"] = f"Key {settings.fal_api_key}"

        try:
            self._ws = await websockets.connect(url, additional_headers=headers)
            self._connected = True
            asyncio.create_task(self._receive_loop())
            logger.info("PersonaPlex connected to %s", url)
        except Exception as exc:
            logger.error("PersonaPlex connection failed: %s", exc)
            raise

    async def send_audio(self, pcm_audio: bytes) -> None:
        """Send a PCM audio chunk (s16le, 24kHz, mono) to PersonaPlex."""
        if not self._ws or not self._connected:
            raise RuntimeError("Not connected")

        audio_b64 = base64.b64encode(pcm_audio).decode("ascii")
        message = {
            "audio": audio_b64,
            "prompt": self.persona_prompt,
            "voice": self.voice,
            "temperature_text": 0.3,
            "temperature_audio": 0.6,
            "top_k_text": 15,
        }
        await self._ws.send(json.dumps(message))

    async def receive_responses(self) -> AsyncIterator[PersonaPlexResponse]:
        """Yield PersonaPlex responses as they arrive."""
        while self._connected:
            response = await self._response_queue.get()
            if response is None:
                break
            yield response

    async def disconnect(self) -> None:
        self._connected = False
        if self._ws:
            await self._ws.close()
            self._ws = None
        await self._response_queue.put(None)
        logger.info("PersonaPlex disconnected")

    async def _receive_loop(self) -> None:
        try:
            async for raw_msg in self._ws:
                if not self._connected:
                    break
                try:
                    data = json.loads(raw_msg)
                    audio_b64 = data.get("audio", "")
                    text = data.get("text", "")
                    audio_bytes = base64.b64decode(audio_b64) if audio_b64 else b""
                    await self._response_queue.put(
                        PersonaPlexResponse(audio=audio_bytes, text=text)
                    )
                except (json.JSONDecodeError, Exception) as exc:
                    logger.warning("PersonaPlex parse error: %s", exc)
        except websockets.ConnectionClosed:
            logger.info("PersonaPlex WebSocket closed")
        except Exception as exc:
            logger.error("PersonaPlex receive error: %s", exc)
        finally:
            self._connected = False
            await self._response_queue.put(None)


def extract_answer_signal(text: str) -> str | None:
    """Parse PersonaPlex response text for a yes/no/unknown signal.

    Returns "yes", "no", "unknown", or None if undetectable.
    """
    lower = text.lower()

    no_indicators = [
        "non", "no", "ce n'est pas", "that is not", "pas cela",
        "fausse route", "shakes its head", "secoue la tete",
    ]
    yes_indicators = [
        "oui", "yes", "c'est exact", "that is correct", "en effet",
        "indeed", "confirme", "confirms", "acquiesce", "nods",
    ]
    unknown_indicators = [
        "je ne sais pas", "i don't know", "i do not know",
        "mystere", "mystery", "ignor", "cannot say", "ne peux dire",
        "silent on this", "muet sur ce",
    ]

    for indicator in unknown_indicators:
        if indicator in lower:
            return "unknown"
    for indicator in no_indicators:
        if indicator in lower:
            return "no"
    for indicator in yes_indicators:
        if indicator in lower:
            return "yes"

    return None
