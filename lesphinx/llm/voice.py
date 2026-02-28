"""SphinxVoice: theatrical reformulation of yes/no/unknown answers."""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time

from mistralai import Mistral

from lesphinx.config.settings import settings

logger = logging.getLogger(__name__)

# --- Template pool (Layer 1: instant, always available) ---

TEMPLATES = {
    "yes": {
        "fr": [
            "Oui, mortel... c'est exact.",
            "En effet... tu vois juste.",
            "Le Sphinx confirme... oui.",
            "C'est bien le cas, mortel.",
            "Oui... tu t'approches de la verite.",
            "Exactement... continue ainsi.",
            "Le Sphinx acquiesce... oui.",
            "Tu ne te trompes pas, mortel.",
        ],
        "en": [
            "Yes, mortal... that is correct.",
            "Indeed... you see truly.",
            "The Sphinx confirms... yes.",
            "That is the case, mortal.",
            "Yes... you draw closer to the truth.",
            "Exactly... continue thus.",
            "The Sphinx nods... yes.",
            "You are not mistaken, mortal.",
        ],
    },
    "no": {
        "fr": [
            "Non, mortel... ce n'est pas le cas.",
            "Le Sphinx nie... non.",
            "Tu fais fausse route, mortel.",
            "Non... cherche ailleurs.",
            "Ce n'est pas cela... non.",
            "Le Sphinx secoue la tete... non.",
            "Tu te trompes, mortel.",
            "Non... la verite est ailleurs.",
        ],
        "en": [
            "No, mortal... that is not the case.",
            "The Sphinx denies... no.",
            "You are on the wrong path, mortal.",
            "No... look elsewhere.",
            "That is not it... no.",
            "The Sphinx shakes its head... no.",
            "You are mistaken, mortal.",
            "No... the truth lies elsewhere.",
        ],
    },
    "unknown": {
        "fr": [
            "Le Sphinx ne sait pas tout, mortel...",
            "Cette information m'est inconnue...",
            "Hmm... je ne peux repondre a cela.",
            "Le Sphinx garde le silence sur ce point...",
            "Peut-etre... peut-etre pas. Je ne sais pas.",
            "Les mysteres du Sphinx ont leurs limites...",
            "Je ne peux ni confirmer ni nier cela.",
        ],
        "en": [
            "The Sphinx does not know everything, mortal...",
            "That information is unknown to me...",
            "Hmm... I cannot answer that.",
            "The Sphinx remains silent on this matter...",
            "Perhaps... perhaps not. I do not know.",
            "The mysteries of the Sphinx have their limits...",
            "I can neither confirm nor deny that.",
        ],
    },
}

# --- LLM voice prompt (Layer 2: rich contextual responses) ---

VOICE_SYSTEM_PROMPT = """You are the Sphinx, a mythical and enigmatic creature.
Reformulate the given answer in your mysterious, theatrical style.

Rules:
- Keep it to 1-2 short sentences maximum
- Be grave, mysterious, ancient
- You may reference the topic of the question to make the response contextual
- NEVER reveal any name or identity
- NEVER add information beyond the given answer
- The utterance MUST be in {language}
- The answer is: {answer}
{fact_context}

Return ONLY a JSON object: {{"text": "Your theatrical response here"}}"""


class SphinxVoice:
    """Generates theatrical Sphinx responses. Template-first, optional LLM enrichment."""

    def __init__(self) -> None:
        self._client = Mistral(api_key=settings.mistral_api_key)
        self._used_templates: dict[str, set[int]] = {"yes": set(), "no": set(), "unknown": set()}

    async def speak(
        self,
        answer: str,
        language: str,
        question: str = "",
        matched_fact: str | None = None,
    ) -> str:
        """Generate a Sphinx-style response."""
        mode = settings.sphinx_voice_mode

        if mode == "template":
            return self._template_response(answer, language)

        if mode == "llm":
            return await self._llm_response(answer, language, question, matched_fact)

        # "auto" mode: try LLM with timeout, fallback to template
        template = self._template_response(answer, language)
        try:
            result = await asyncio.wait_for(
                self._llm_response(answer, language, question, matched_fact),
                timeout=settings.sphinx_voice_llm_timeout,
            )
            return result
        except (asyncio.TimeoutError, Exception) as exc:
            logger.info("SphinxVoice LLM timeout/error, using template: %s", exc)
            return template

    def _template_response(self, answer: str, language: str) -> str:
        pool = TEMPLATES.get(answer, TEMPLATES["unknown"])
        templates = pool.get(language, pool["en"])

        used = self._used_templates.get(answer, set())
        available = [i for i in range(len(templates)) if i not in used]
        if not available:
            self._used_templates[answer] = set()
            available = list(range(len(templates)))

        idx = random.choice(available)
        self._used_templates.setdefault(answer, set()).add(idx)
        return templates[idx]

    async def _llm_response(
        self,
        answer: str,
        language: str,
        question: str,
        matched_fact: str | None,
    ) -> str:
        lang_name = "French" if language == "fr" else "English"
        fact_ctx = f"Related fact: {matched_fact}" if matched_fact else ""

        prompt = VOICE_SYSTEM_PROMPT.format(
            language=lang_name,
            answer=answer,
            fact_context=fact_ctx,
        )

        response = await self._client.chat.complete_async(
            model=settings.mistral_model,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": question or "..."},
            ],
            response_format={"type": "json_object"},
            timeout_ms=int(settings.sphinx_voice_llm_timeout * 1000) + 500,
        )

        content = response.choices[0].message.content
        data = json.loads(content)
        text = data.get("text", "")
        if text and len(text) > 5:
            return text

        return self._template_response(answer, language)
