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
            "Les sables du Nil murmurent en ta faveur... oui.",
            "Les hieroglyphes ne mentent pas... c'est exact.",
            "Par les pyramides d'Egypte, tu vois juste !",
            "Le Sphinx acquiesce... les etoiles confirment.",
            "Oui, mortel... tu t'approches de la verite.",
            "Les dieux de l'Olympe approuvent... oui.",
            "Le vent du desert porte ta sagesse... en effet.",
            "L'oeil d'Horus confirme... tu es sur la bonne voie.",
            "Les anciens te guident bien, mortel... oui.",
            "Par Osiris, c'est exact !",
        ],
        "en": [
            "The sands of the Nile whisper in your favor... yes.",
            "The hieroglyphs do not lie... that is correct.",
            "By the pyramids of Egypt, you see truly!",
            "The Sphinx nods... the stars confirm.",
            "Yes, mortal... you draw closer to the truth.",
            "The gods of Olympus approve... yes.",
            "The desert wind carries your wisdom... indeed.",
            "The Eye of Horus confirms... you are on the right path.",
            "The ancients guide you well, mortal... yes.",
            "By Osiris, that is correct!",
        ],
    },
    "no": {
        "fr": [
            "Les hieroglyphes tracent un autre chemin... non.",
            "Tu fais fausse route, mortel... le Nil coule ailleurs.",
            "Non... les sables du temps disent autrement.",
            "Le Sphinx secoue la tete... les pyramides restent muettes.",
            "Par Anubis, ce n'est pas cela...",
            "Non, mortel... le desert garde ses secrets.",
            "Les etoiles du pharaon ne s'alignent pas ainsi...",
            "Tu t'egares dans le labyrinthe, mortel... non.",
            "Le scarabee sacre tourne le dos a cette piste...",
            "Non... cherche au-dela des dunes.",
        ],
        "en": [
            "The hieroglyphs trace a different path... no.",
            "You are lost, mortal... the Nile flows elsewhere.",
            "No... the sands of time say otherwise.",
            "The Sphinx shakes its head... the pyramids remain silent.",
            "By Anubis, that is not it...",
            "No, mortal... the desert keeps its secrets.",
            "The pharaoh's stars do not align that way...",
            "You wander the labyrinth, mortal... no.",
            "The sacred scarab turns away from this trail...",
            "No... seek beyond the dunes.",
        ],
    },
    "unknown": {
        "fr": [
            "Meme les dieux de l'Olympe ignorent la reponse...",
            "Le papyrus est muet sur ce point, mortel...",
            "Les sables du temps n'ont pas conserve cette verite...",
            "Hmm... meme le Sphinx a ses mysteres.",
            "Peut-etre... peut-etre pas. Le Nil garde ses secrets.",
            "Cette enigme echappe meme au Sphinx...",
            "L'oracle d'Amon se tait sur ce sujet...",
            "Tu donnes ta langue au Sphinx ? Moi-meme, je l'ignore...",
        ],
        "en": [
            "Even the gods of Olympus do not know the answer...",
            "The papyrus is silent on this matter, mortal...",
            "The sands of time have not preserved this truth...",
            "Hmm... even the Sphinx has its mysteries.",
            "Perhaps... perhaps not. The Nile keeps its secrets.",
            "This riddle escapes even the Sphinx...",
            "The oracle of Amun falls silent on this...",
            "Cat got your tongue? Even I do not know...",
        ],
    },
}

# --- LLM voice prompt (Layer 2: rich contextual responses) ---

VOICE_SYSTEM_PROMPT = """You are the Sphinx, an ancient Egyptian mythical creature guarding the secrets of the pyramids.
Reformulate the given answer in your mysterious, theatrical style.

Rules:
- Keep it to 1-2 short sentences maximum
- Be grave, mysterious, ancient — like a guardian of the pharaohs
- Use Egyptian and mythological metaphors: the Nile, the sands, hieroglyphs, Osiris, Anubis, the Eye of Horus, pyramids, obelisks, papyrus, the desert wind
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
