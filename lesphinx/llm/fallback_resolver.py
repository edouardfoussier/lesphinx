"""LLM-based fallback when AnswerResolver returns 'unknown'.

Uses character attributes + facts + LLM general knowledge to answer questions
that aren't covered by the structured data. This effectively simulates
"internet search" using the LLM's training data.
"""

from __future__ import annotations

import json
import logging

from mistralai import Mistral

from lesphinx.config.settings import settings

logger = logging.getLogger(__name__)

FALLBACK_SYSTEM_PROMPT = """You are answering YES/NO questions about a famous person in a guessing game.
You are given structured attributes and facts about this person (name withheld).

IMPORTANT: Use ALL your knowledge about this person, not just the listed facts.
The facts are hints to help you identify who the person is -- once you figure it out,
use your full knowledge to answer the question accurately.

Rules:
- Answer "yes" if the answer is clearly yes based on your knowledge
- Answer "no" if the answer is clearly no based on your knowledge
- Answer "unknown" ONLY if you genuinely cannot determine the answer
- NEVER reveal the person's name in your response
- Respond with ONLY a JSON object: {"answer": "yes"|"no"|"unknown"}
"""


def _build_context(
    attributes: dict | None = None,
    facts: list[str] | None = None,
) -> str:
    """Build a rich context string from attributes and facts."""
    parts = []

    if attributes:
        attr_lines = []
        skip_keys = {"birth_year", "death_year"}
        for k, v in attributes.items():
            if k in skip_keys or v is None or v == "unknown":
                continue
            attr_lines.append(f"- {k}: {v}")
        if attr_lines:
            parts.append("Known attributes:\n" + "\n".join(attr_lines))

    if facts:
        facts_text = "\n".join(f"- {f}" for f in facts)
        parts.append(f"Known facts:\n{facts_text}")

    return "\n\n".join(parts) if parts else "No specific facts available."


class LLMFallbackResolver:
    """Uses Mistral + general knowledge to answer questions the data can't."""

    def __init__(self) -> None:
        self._client: Mistral | None = None

    def _get_client(self) -> Mistral:
        if self._client is None:
            self._client = Mistral(api_key=settings.mistral_api_key)
        return self._client

    async def resolve(
        self,
        question: str,
        facts: list[str] | None = None,
        attributes: dict | None = None,
    ) -> str:
        """Return 'yes', 'no', or 'unknown'."""
        try:
            client = self._get_client()
            context = _build_context(attributes, facts)
            user_msg = f"{context}\n\nPlayer's question: {question}"

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
