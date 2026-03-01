"""SphinxVoice: theatrical reformulation of yes/no/unknown answers with mood system."""

from __future__ import annotations

import asyncio
import json
import logging
import random

from mistralai import Mistral

from lesphinx.config.settings import settings
from lesphinx.game.models import GameSession

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
#  Mood system
# ---------------------------------------------------------------------------
MOODS = ("confident", "intrigued", "nervous", "condescending")


def get_mood(session: GameSession) -> str:
    """Determine Sphinx mood based on game progress."""
    yes_count = sum(1 for t in session.turns if t.raw_answer == "yes")
    total_q = session.question_count

    if session.guess_count >= 2 and session.result is None:
        return "condescending"
    if total_q <= 5:
        return "confident"
    if total_q > 12 or (total_q > 8 and yes_count > total_q * 0.5):
        return "nervous"
    if yes_count > 3:
        return "intrigued"
    return "confident"


# ---------------------------------------------------------------------------
#  Mood-aware templates
# ---------------------------------------------------------------------------
TEMPLATES: dict[str, dict[str, dict[str, list[str]]]] = {
    "yes": {
        "confident": {
            "fr": [
                "Les sables du Nil murmurent en ta faveur... oui.",
                "Les hieroglyphes ne mentent pas... c'est exact.",
                "Par les pyramides d'Egypte, tu vois juste !",
                "Oui, mortel... mais ne te rejouis pas trop vite.",
                "Le Sphinx acquiesce... les etoiles confirment.",
                "L'oeil d'Horus confirme... mais le chemin est encore long.",
            ],
            "en": [
                "The sands of the Nile whisper in your favor... yes.",
                "The hieroglyphs do not lie... that is correct.",
                "By the pyramids of Egypt, you see truly!",
                "Yes, mortal... but do not rejoice too soon.",
                "The Sphinx nods... the stars confirm.",
                "The Eye of Horus confirms... but the path is still long.",
            ],
        },
        "intrigued": {
            "fr": [
                "Hmm... oui. Tu commences a m'intriguer, mortel.",
                "En effet... tu poses les bonnes questions.",
                "Oui... le vent tourne en ta faveur. Interessant.",
                "Les dieux de l'Olympe approuvent... tu progresses.",
                "Exact... tu t'approches. Le Sphinx commence a douter...",
            ],
            "en": [
                "Hmm... yes. You are beginning to intrigue me, mortal.",
                "Indeed... you ask the right questions.",
                "Yes... the wind turns in your favor. Interesting.",
                "The gods of Olympus approve... you are progressing.",
                "Correct... you draw closer. The Sphinx begins to wonder...",
            ],
        },
        "nervous": {
            "fr": [
                "O-Oui... tu... tu approches de la verite !",
                "Exact... par Anubis, tu me fais trembler !",
                "Oui ! Les murs de mon temple en fremissent...",
                "C'est... c'est exact. Le Sphinx n'aime pas ca...",
                "Les sables tremblent... oui, mortel, tu as raison.",
            ],
            "en": [
                "Y-Yes... you... you approach the truth!",
                "Correct... by Anubis, you make me tremble!",
                "Yes! The walls of my temple shudder...",
                "That is... that is correct. The Sphinx does not like this...",
                "The sands tremble... yes, mortal, you are right.",
            ],
        },
        "condescending": {
            "fr": [
                "Oui, oui... meme un scarabee trouve un grain de sable.",
                "C'est exact. Meme un mortel tombe parfois juste.",
                "Les hieroglyphes confirment... mais ne te vante pas.",
            ],
            "en": [
                "Yes, yes... even a scarab finds a grain of sand.",
                "That is correct. Even a mortal stumbles upon truth sometimes.",
                "The hieroglyphs confirm... but do not boast.",
            ],
        },
    },
    "no": {
        "confident": {
            "fr": [
                "Les hieroglyphes tracent un autre chemin... non.",
                "Non... les sables du temps disent autrement.",
                "Le Sphinx secoue la tete... les pyramides restent muettes.",
                "Par Anubis, ce n'est pas cela...",
                "Non, mortel... le desert garde ses secrets.",
                "Tu t'egares dans le labyrinthe, mortel... non.",
            ],
            "en": [
                "The hieroglyphs trace a different path... no.",
                "No... the sands of time say otherwise.",
                "The Sphinx shakes its head... the pyramids remain silent.",
                "By Anubis, that is not it...",
                "No, mortal... the desert keeps its secrets.",
                "You wander the labyrinth, mortal... no.",
            ],
        },
        "intrigued": {
            "fr": [
                "Non... mais tu n'es pas loin. Cherche encore.",
                "Pas exactement... le Nil coule dans une autre direction.",
                "Non, mortel. Mais ta strategie est... interessante.",
            ],
            "en": [
                "No... but you are not far. Search further.",
                "Not exactly... the Nile flows in another direction.",
                "No, mortal. But your strategy is... interesting.",
            ],
        },
        "nervous": {
            "fr": [
                "N-Non ! Ha... heureusement. Le Sphinx respire.",
                "Non... ouf. Tu m'as fait peur un instant.",
                "Ce n'est pas ca... le Sphinx reprend confiance.",
            ],
            "en": [
                "N-No! Ha... thankfully. The Sphinx breathes.",
                "No... phew. You scared me for a moment.",
                "That is not it... the Sphinx regains composure.",
            ],
        },
        "condescending": {
            "fr": [
                "Non. Comme je m'y attendais... le desert est vaste, mortel.",
                "Evidemment non. Le Sphinx baille...",
                "Non... tu erres dans l'obscurite sans lanterne.",
            ],
            "en": [
                "No. As I expected... the desert is vast, mortal.",
                "Obviously not. The Sphinx yawns...",
                "No... you wander in darkness without a lantern.",
            ],
        },
    },
    "unknown": {
        "confident": {
            "fr": [
                "Meme les dieux de l'Olympe ignorent la reponse...",
                "Le papyrus est muet sur ce point, mortel...",
                "Hmm... meme le Sphinx a ses mysteres.",
                "Peut-etre... peut-etre pas. Le Nil garde ses secrets.",
                "Tu donnes ta langue au Sphinx ? Moi-meme, je l'ignore...",
            ],
            "en": [
                "Even the gods of Olympus do not know the answer...",
                "The papyrus is silent on this matter, mortal...",
                "Hmm... even the Sphinx has its mysteries.",
                "Perhaps... perhaps not. The Nile keeps its secrets.",
                "Cat got your tongue? Even I do not know...",
            ],
        },
        "intrigued": {
            "fr": [
                "Question interessante... mais meme le Sphinx ignore cette verite.",
                "L'oracle d'Amon se tait sur ce sujet...",
                "Les sables n'ont pas preserve cette verite... mystere.",
            ],
            "en": [
                "Interesting question... but even the Sphinx does not know.",
                "The oracle of Amun falls silent on this...",
                "The sands have not preserved this truth... mystery.",
            ],
        },
        "nervous": {
            "fr": [
                "Je... je ne sais pas. Mais pose d'autres questions !",
                "Cette enigme echappe meme au Sphinx... pour l'instant.",
            ],
            "en": [
                "I... I do not know. But ask more questions!",
                "This riddle escapes even the Sphinx... for now.",
            ],
        },
        "condescending": {
            "fr": [
                "Je l'ignore. Et toi, tu ignores bien plus encore...",
                "Nul ne sait... mais au moins, le Sphinx l'admet.",
            ],
            "en": [
                "I do not know. And you know even less...",
                "No one knows... but at least the Sphinx admits it.",
            ],
        },
    },
}

# ---------------------------------------------------------------------------
#  LLM voice prompt (mood-aware)
# ---------------------------------------------------------------------------
VOICE_SYSTEM_PROMPT = """You are the Sphinx, an ancient Egyptian mythical creature guarding the secrets of the pyramids.
Reformulate the given answer in your mysterious, theatrical style.

Your current mood: {mood}
- confident: mocking, dismissive, supremely sure of yourself
- intrigued: curious, slightly worried, impressed by the player
- nervous: anxious, stammering slightly, the player is getting close
- condescending: smug, patronizing, the player is struggling

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

WRONG_GUESS_PROMPT = """You are the Sphinx. A player just guessed "{guess_name}" but that is WRONG.
React to this specific wrong guess in a theatrical, {mood} way. Use Egyptian metaphors.
Keep it to 1-2 sentences in {language}. Reference the guessed name in your reaction.
NEVER reveal the real answer. Return ONLY JSON: {{"text": "..."}}"""


class SphinxVoice:
    """Generates theatrical Sphinx responses with mood awareness."""

    def __init__(self) -> None:
        self._client = Mistral(api_key=settings.mistral_api_key)
        self._used_templates: dict[str, set[int]] = {}

    async def speak(
        self,
        answer: str,
        language: str,
        question: str = "",
        matched_fact: str | None = None,
        mood: str = "confident",
    ) -> str:
        mode = settings.sphinx_voice_mode

        if mode == "template":
            return self._template_response(answer, language, mood)

        if mode == "llm":
            return await self._llm_response(answer, language, question, matched_fact, mood)

        template = self._template_response(answer, language, mood)
        try:
            result = await asyncio.wait_for(
                self._llm_response(answer, language, question, matched_fact, mood),
                timeout=settings.sphinx_voice_llm_timeout,
            )
            return result
        except (asyncio.TimeoutError, Exception) as exc:
            logger.info("SphinxVoice LLM timeout/error, using template: %s", exc)
            return template

    async def react_to_wrong_guess(
        self, guess_name: str, language: str, mood: str = "confident"
    ) -> str | None:
        """Generate a contextual reaction to a wrong guess."""
        lang_name = "French" if language == "fr" else "English"
        prompt = WRONG_GUESS_PROMPT.format(
            guess_name=guess_name, mood=mood, language=lang_name
        )
        try:
            response = await self._client.chat.complete_async(
                model=settings.mistral_model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                timeout_ms=3000,
            )
            data = json.loads(response.choices[0].message.content)
            text = data.get("text", "")
            if text and len(text) > 5:
                return text
        except Exception as exc:
            logger.info("Wrong guess reaction LLM failed: %s", exc)
        return None

    def _template_response(self, answer: str, language: str, mood: str) -> str:
        answer_templates = TEMPLATES.get(answer, TEMPLATES["unknown"])
        mood_templates = answer_templates.get(mood, answer_templates.get("confident", {}))
        pool = mood_templates.get(language, mood_templates.get("en", []))

        if not pool:
            fallback = answer_templates.get("confident", {})
            pool = fallback.get(language, fallback.get("en", ["..."]))

        cache_key = f"{answer}_{mood}_{language}"
        used = self._used_templates.get(cache_key, set())
        available = [i for i in range(len(pool)) if i not in used]
        if not available:
            self._used_templates[cache_key] = set()
            available = list(range(len(pool)))

        idx = random.choice(available)
        self._used_templates.setdefault(cache_key, set()).add(idx)
        return pool[idx]

    async def _llm_response(
        self,
        answer: str,
        language: str,
        question: str,
        matched_fact: str | None,
        mood: str,
    ) -> str:
        lang_name = "French" if language == "fr" else "English"
        fact_ctx = f"Related fact: {matched_fact}" if matched_fact else ""

        prompt = VOICE_SYSTEM_PROMPT.format(
            language=lang_name, answer=answer,
            fact_context=fact_ctx, mood=mood,
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

        return self._template_response(answer, language, mood)
