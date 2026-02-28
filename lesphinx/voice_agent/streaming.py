"""ElevenLabs WebSocket streaming TTS.

Connects to ElevenLabs' input-streaming endpoint to send text and
receive audio chunks in real-time.  This dramatically reduces
time-to-first-audio compared to the batch REST API.

Protocol:
  Client sends JSON text chunks -> Server responds with base64 MP3 chunks.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from typing import AsyncIterator

import websockets

from lesphinx.config.settings import settings

logger = logging.getLogger(__name__)

ELEVENLABS_STREAM_URL = (
    "wss://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream-input"
    "?model_id={model_id}"
)


async def stream_tts(text: str) -> AsyncIterator[bytes]:
    """Stream TTS audio for the given text via ElevenLabs WebSocket.

    Yields MP3 audio chunks as they are generated.  Falls back to
    an empty iterator if the connection fails.
    """
    url = ELEVENLABS_STREAM_URL.format(
        voice_id=settings.elevenlabs_voice_id,
        model_id=settings.elevenlabs_model,
    )

    try:
        async with websockets.connect(url) as ws:
            init_msg = {
                "text": " ",
                "voice_settings": {
                    "stability": 0.6,
                    "similarity_boost": 0.8,
                    "style": 0.3,
                },
                "xi_api_key": settings.elevenlabs_api_key,
            }
            await ws.send(json.dumps(init_msg))

            text_msg = {
                "text": text,
                "try_trigger_generation": True,
            }
            await ws.send(json.dumps(text_msg))

            flush_msg = {"text": ""}
            await ws.send(json.dumps(flush_msg))

            async for raw_msg in ws:
                try:
                    data = json.loads(raw_msg)
                    audio_b64 = data.get("audio")
                    if audio_b64:
                        yield base64.b64decode(audio_b64)
                    if data.get("isFinal"):
                        break
                except json.JSONDecodeError:
                    if isinstance(raw_msg, bytes):
                        yield raw_msg
    except Exception as exc:
        logger.error("ElevenLabs streaming TTS failed: %s", exc)


async def stream_tts_full(text: str) -> bytes:
    """Like stream_tts but collects all chunks into a single bytes object.

    Useful when the caller needs the complete audio (e.g., for storing
    in the audio blob store).
    """
    chunks: list[bytes] = []
    async for chunk in stream_tts(text):
        chunks.append(chunk)
    return b"".join(chunks)
