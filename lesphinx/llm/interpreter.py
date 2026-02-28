"""Hybrid QuestionInterpreter: rule-based matching + LLM fallback."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from mistralai import Mistral

from lesphinx.config.settings import settings
from lesphinx.llm.schemas import AttributeCheck, ParsedQuestion

logger = logging.getLogger(__name__)

# --- Rule-based patterns (Layer 1: instant, free, 100% reliable) ---

_ATTRIBUTE_PATTERNS: list[tuple[re.Pattern, str, Any]] = []


def _p(pattern: str, key: str, value: Any) -> None:
    _ATTRIBUTE_PATTERNS.append((re.compile(pattern, re.IGNORECASE), key, value))


# Gender
_p(r"\b(homme|man|male|garcon|guy|monsieur|un homme)\b", "gender", "male")
_p(r"\b(femme|woman|female|fille|lady|madame|une femme)\b", "gender", "female")

# Alive
_p(r"\b(vivant|alive|still alive|en vie|encore en vie|living)\b", "alive", True)
_p(r"\b(mort|dead|decede|deceased|died)\b", "alive", False)

# Nationality (common ones -- must come before continent to avoid "american" -> continent)
_p(r"\b(francais|french|france)\b", "nationality", "french")
_p(r"\b(americain|american|etats.unis|usa|united states)\b", "nationality", "american")
_p(r"\b(anglais|english|british|britannique|royaume.uni|united kingdom)\b", "nationality", "british")
_p(r"\b(allemand|german|germany|allemagne)\b", "nationality", "german")
_p(r"\b(italien|italian|italy|italie)\b", "nationality", "italian")
_p(r"\b(espagnol|spanish|spain|espagne)\b", "nationality", "spanish")
_p(r"\b(japonais|japanese|japan|japon)\b", "nationality", "japanese")
_p(r"\b(chinois|chinese|china|chine)\b", "nationality", "chinese")
_p(r"\b(russe|russian|russia|russie)\b", "nationality", "russian")
_p(r"\b(bresilien|brazilian|brazil|bresil)\b", "nationality", "brazilian")
_p(r"\b(canadien|canadian|canada)\b", "nationality", "canadian")
_p(r"\b(australien|australian|australia|australie)\b", "nationality", "australian")
_p(r"\b(indien|indian|india|inde)\b", "nationality", "indian")
_p(r"\b(mexicain|mexican|mexico|mexique)\b", "nationality", "mexican")
_p(r"\b(argentino?|argentin|argentine|argentina)\b", "nationality", "argentine")

# Continent
_p(r"\b(europeen|european|europe|d.europe)\b", "continent", "europe")
_p(r"\b(americain|american|americas|amerique|d.amerique)\b", "continent", "americas")
_p(r"\b(asiatique|asian|asia|asie|d.asie)\b", "continent", "asia")
_p(r"\b(africain|african|africa|afrique|d.afrique)\b", "continent", "africa")
_p(r"\b(oceanien|oceanian|oceania|oceanie)\b", "continent", "oceania")

# Field
_p(r"\b(scientifique|scientist|science|sciences)\b", "field", "science")
_p(r"\b(politicien|politician|politics|politique|political)\b", "field", "politics")
_p(r"\b(musicien|musician|music|musique|chanteur|singer|chanteuse)\b", "field", "music")
_p(r"\b(acteur|actor|actress|actrice|cinema|film|movie)\b", "field", "cinema")
_p(r"\b(sportif|sportive|athlete|sport|sports)\b", "field", "sports")
_p(r"\b(football|footballeur|soccer)\b", "field", "sports")
_p(r"\b(ecrivain|writer|author|auteur|litterature|literature)\b", "field", "literature")
_p(r"\b(artiste|artist|peintre|painter|arts|art)\b", "field", "arts")
_p(r"\b(philosophe|philosopher|philosophy|philosophie)\b", "field", "philosophy")
_p(r"\b(business|entrepreneur|affaires|homme.d.affaires)\b", "field", "business")
_p(r"\b(explorateur|explorer|exploration|astronaute|astronaut)\b", "field", "exploration")
_p(r"\b(religion|religieux|religious|pape|pope)\b", "field", "religion")

# Era
_p(r"\b(ne avant 1900|born before 1900|19e siecle|19th century|xix)\b", "born_before_1900", True)
_p(r"\b(ne avant 1950|born before 1950|premiere moitie du 20e)\b", "born_before_1950", True)
_p(r"\b(ne apres 1950|born after 1950|contemporain|contemporary|modern)\b", "born_before_1950", False)

# Fictional
_p(r"\b(fictif|fictional|fiction|personnage fictif)\b", "fictional", True)
_p(r"\b(reel|real|real person|personne reelle)\b", "fictional", False)

# --- Guess detection patterns ---

_GUESS_PATTERNS = [
    re.compile(r"(?:je pense que c'est|i think it'?s)\s+(.+)", re.IGNORECASE),
    re.compile(r"(?:je devine|i guess|my guess is|ma reponse est)\s+(.+)", re.IGNORECASE),
    re.compile(r"(?:c'est|est-ce|is it)\s+(.+)", re.IGNORECASE),
]


def rule_match(text: str) -> ParsedQuestion | None:
    """Try to parse the question using regex rules. Returns None if no match."""
    cleaned = text.strip().rstrip("?!.")

    # Check attribute patterns first (they're more specific)
    for pattern, key, value in _ATTRIBUTE_PATTERNS:
        if pattern.search(cleaned):
            return ParsedQuestion(
                intent="question",
                attribute_check=AttributeCheck(key=key, value=value),
            )

    # Then check for guess patterns
    for pattern in _GUESS_PATTERNS:
        m = pattern.match(cleaned)
        if m:
            name = m.group(1).strip().rstrip("?!.")
            if len(name) > 1:
                return ParsedQuestion(intent="guess", guess_name=name)

    return None


# --- LLM fallback (Layer 2: for complex/ambiguous questions) ---

INTERPRETER_SYSTEM_PROMPT = """You parse player questions from a guessing game into structured queries.

Available attribute keys and their possible values:
- gender: "male" or "female"
- alive: true or false
- nationality: country adjective lowercase (e.g. "french", "american", "german")
- field: "science", "politics", "music", "cinema", "sports", "literature", "arts", "business", "philosophy", "religion", "exploration"
- subfield: specific area (e.g. "physics", "rap", "football", "painting")
- continent: "europe", "americas", "asia", "africa", "oceania"
- born_before_1900: true or false
- born_before_1950: true or false
- fictional: true or false

Return ONLY a JSON object:
{"intent": "question", "attribute_check": {"key": "...", "value": ...} or null, "fact_keywords": ["keyword1", "keyword2"], "guess_name": null}

If the player is guessing a person's name:
{"intent": "guess", "attribute_check": null, "fact_keywords": [], "guess_name": "Person Name"}

Rules:
- Use attribute_check for questions about basic traits (gender, nationality, field, era, alive)
- Use fact_keywords for specific questions (awards, achievements, works, events)
- If unsure, return fact_keywords with the most relevant words from the question
- NEVER include the answer in your response
- NEVER reveal any information about any person
"""


class QuestionInterpreter:
    """Hybrid interpreter: rules first, LLM fallback."""

    def __init__(self) -> None:
        self._client = Mistral(api_key=settings.mistral_api_key)

    async def interpret(self, text: str) -> ParsedQuestion:
        # Layer 1: rule-based matching
        result = rule_match(text)
        if result is not None:
            logger.info("RuleMatcher hit for: %s", text[:60])
            return result

        # Layer 2: LLM fallback
        logger.info("LLM fallback for: %s", text[:60])
        return await self._llm_interpret(text)

    async def _llm_interpret(self, text: str) -> ParsedQuestion:
        try:
            response = await self._client.chat.complete_async(
                model=settings.mistral_model,
                messages=[
                    {"role": "system", "content": INTERPRETER_SYSTEM_PROMPT},
                    {"role": "user", "content": text},
                ],
                response_format={"type": "json_object"},
                timeout_ms=settings.llm_timeout * 1000,
            )

            content = response.choices[0].message.content
            data = json.loads(content)

            intent = data.get("intent", "question")
            guess_name = data.get("guess_name")
            attr_raw = data.get("attribute_check")
            fact_kw = data.get("fact_keywords", [])

            attr_check = None
            if attr_raw and isinstance(attr_raw, dict) and "key" in attr_raw:
                attr_check = AttributeCheck(
                    key=str(attr_raw["key"]),
                    value=attr_raw["value"],
                )

            if not isinstance(fact_kw, list):
                fact_kw = []
            fact_kw = [str(kw) for kw in fact_kw if kw]

            return ParsedQuestion(
                intent=intent if intent in ("question", "guess") else "question",
                attribute_check=attr_check,
                fact_keywords=fact_kw,
                guess_name=str(guess_name) if guess_name else None,
            )
        except Exception as exc:
            logger.warning("LLM interpreter failed: %s", exc)
            words = text.lower().split()
            stop = {"est", "ce", "il", "elle", "un", "une", "le", "la", "les", "des",
                    "is", "he", "she", "a", "an", "the", "was", "has", "did", "do",
                    "que", "qui", "de", "du", "it", "this", "that", "are", "were"}
            keywords = [w.strip("?!.,") for w in words if len(w) > 2 and w not in stop]
            return ParsedQuestion(intent="question", fact_keywords=keywords[:5])
