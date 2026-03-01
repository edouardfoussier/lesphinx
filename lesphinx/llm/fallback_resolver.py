"""LLM-based fallback when AnswerResolver returns 'unknown'."""

from __future__ import annotations

import json
import logging

from mistralai import Mistral

from lesphinx.config.settings import settings

logger = logging.getLogger(__name__)

FALLBACK_SYSTEM_PROMPT = """You are a fact-checker assistant. Given a list of facts about a person (whose name is NOT provided) and a question, determine if the answer is "yes", "no", or "unknown".

Rules:
- Only answer "yes" or "no" if the facts clearly support or contradict the question.
- Answer "unknown" if the facts don't provide enough information.
- Never guess or speculate beyond what the facts state.
- Respond with ONLY a JSON object: {"answer": "yes"|"no"|"unknown"}
"""


class LLMFallbackResolver:
    """Uses Mistral to deduce yes/no/unknown from character facts."""

    def __init__(self) -> None:
        self._client: Mistral | None = None

    def _get_client(self) -> Mistral:
        if self._client is None:
            self._client = Mistral(api_key=settings.mistral_api_key)
        return self._client

    async def resolve(self, question: str, facts: list[str]) -> str:
        """Return 'yes', 'no', or 'unknown'."""
        try:
            client = self._get_client()
            facts_text = "\n".join(f"- {f}" for f in facts)
            user_msg = f"Facts about this person:\n{facts_text}\n\nQuestion: {question}"

            response = await client.chat.complete_async(
                model=settings.mistral_model,
                messages=[
                    {"role": "system", "content": FALLBACK_SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=50,
            )

            raw = response.choices[0].message.content.strip()
            data = json.loads(raw)
            answer = data.get("answer", "unknown").lower()
            if answer in ("yes", "no", "unknown"):
                return answer
            return "unknown"

        except Exception as exc:
            logger.warning("LLM fallback failed: %s", exc)
            return "unknown"
