from __future__ import annotations

import asyncio
import json
import logging

from mistralai import Mistral

from lesphinx.config.settings import settings
from lesphinx.game.models import GameSession
from lesphinx.llm.prompts import build_conversation_messages, build_system_prompt
from lesphinx.llm.schemas import SphinxAction

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
INITIAL_BACKOFF_S = 0.5


class MistralLLMClient:
    def __init__(self) -> None:
        self._client = Mistral(api_key=settings.mistral_api_key)

    async def get_action(self, session: GameSession, player_answer: str) -> SphinxAction:
        system_prompt = build_system_prompt(session)
        messages = build_conversation_messages(session, player_answer)

        full_messages = [{"role": "system", "content": system_prompt}] + messages

        last_exc: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                response = await self._client.chat.complete_async(
                    model=settings.mistral_model,
                    messages=full_messages,
                    response_format={"type": "json_object"},
                    timeout_ms=settings.llm_timeout * 1000,
                )

                content = response.choices[0].message.content
                data = json.loads(content)
                return SphinxAction(**data)
            except Exception as exc:
                last_exc = exc
                if attempt < MAX_RETRIES - 1:
                    wait = INITIAL_BACKOFF_S * (2 ** attempt)
                    logger.warning("LLM attempt %d failed (%s), retrying in %.1fs", attempt + 1, exc, wait)
                    await asyncio.sleep(wait)

        raise last_exc  # type: ignore[misc]
