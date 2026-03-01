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
_p(r"\b(vivante?|alive|still alive|en vie|encore en vie|living)\b", "alive", True)
_p(r"\b(morte?|dead|decede|decedee?|deceased|died)\b", "alive", False)

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
_p(r"\b(acteur|actor|actress|actrice|cinema|films?|movies?)\b", "field", "cinema")
_p(r"\b(sportif|sportive|athlete|sport|sports)\b", "field", "sports")
_p(r"\b(football|footballeur|soccer)\b", "field", "sports")
_p(r"\b(ecrivain|writer|author|auteur|litterature|literature)\b", "field", "literature")
_p(r"\b(artiste|artist|peintre|painter|arts|art)\b", "field", "arts")
_p(r"\b(philosophe|philosopher|philosophy|philosophie)\b", "field", "philosophy")
_p(r"\b(business|entrepreneur|affaires|homme.d.affaires)\b", "field", "business")
_p(r"\b(explorateur|explorer|exploration|astronaute|astronaut)\b", "field", "exploration")
_p(r"\b(religion|religieux|religious|pape|pope)\b", "field", "religion")

# Era (structured)
_p(r"\b(ne avant 1900|born before 1900|19e siecle|19th century|xix)\b", "born_before_1900", True)
_p(r"\b(ne avant 1950|born before 1950|premiere moitie du 20e)\b", "born_before_1950", True)
_p(r"\b(ne apres 1950|born after 1950|contemporain|contemporary|modern)\b", "born_before_1950", False)

# Era (named periods)
_p(r"\b(antiquite|ancient|antique)\b", "era", "ancient")
_p(r"\b(moyen.age|medieval|middle ages)\b", "era", "medieval")
_p(r"\b(renaissance)\b", "era", "renaissance")
_p(r"\b(epoque moderne|modern era|18e|18th|19e|19th)\b", "era", "modern")
_p(r"\b(contemporain|contemporary|20e|20th|21e|21st)\b", "era", "contemporary")

# Century / birth year ranges
_p(r"\b(ne au 18e|born.+18th century|1700s)\b", "era", "modern")
_p(r"\b(ne au 19e|born.+19th century|1800s)\b", "era", "modern")
_p(r"\b(ne au 20e|born.+20th century|1900s)\b", "era", "contemporary")

# Awards
_p(r"\b(prix nobel|nobel prize|nobel|nobelise)\b", "has_nobel_prize", True)
_p(r"\b(oscar|academy award|academie|cesars?)\b", "has_oscar", True)

# Language
_p(r"\b(francophone|parle francais|speaks? french|langue francaise)\b", "primary_language", "french")
_p(r"\b(anglophone|parle anglais|speaks? english|langue anglaise)\b", "primary_language", "english")
_p(r"\b(hispanophone|parle espagnol|speaks? spanish)\b", "primary_language", "spanish")
_p(r"\b(germanophone|parle allemand|speaks? german)\b", "primary_language", "german")

# Hair color
_p(r"\b(blond|blonde|cheveux blonds)\b", "hair_color", "blond")
_p(r"\b(brun|brune|cheveux bruns|brown.?hair)\b", "hair_color", "brown")
_p(r"\b(cheveux noirs|black.?hair)\b", "hair_color", "black")
_p(r"\b(roux|rousse|red.?hair|ginger)\b", "hair_color", "red")
_p(r"\b(chauve|bald)\b", "hair_color", "bald")
_p(r"\b(cheveux gris|cheveux blancs|gray.?hair|white.?hair)\b", "hair_color", "gray")

# Height
_p(r"\b(grande?|tall|grande taille)\b", "height_category", "tall")
_p(r"\b(petite?|short|petite taille)\b", "height_category", "short")

# Ethnicity
_p(r"\b(noir|noire|black|africaine?|d.origine africaine)\b", "ethnicity", "african")
_p(r"\b(asiatique|asian|d.origine asiatique)\b", "ethnicity", "east_asian")
_p(r"\b(latino|latina|hispanique|hispanic)\b", "ethnicity", "latino")
_p(r"\b(blanc|blanche|white|caucasien|caucasian)\b", "ethnicity", "european")
_p(r"\b(arabe|arab|moyen.orient|middle.eastern)\b", "ethnicity", "middle_eastern")
_p(r"\b(metis|metisse|mixed.race|mixed)\b", "ethnicity", "mixed")

# Fictional
_p(r"\b(fictif|fictional|fiction|personnage fictif)\b", "fictional", True)
_p(r"\b(reel|real|real person|personne reelle)\b", "fictional", False)

# --- Easter egg patterns ---

_EASTER_EGGS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"(?:es.tu|are you|tu es)\s+(?:le\s+)?sphinx", re.IGNORECASE), "sphinx_identity"),
    (re.compile(r"(?:connais.tu|do you know|sais.tu)\s+(?:la\s+)?(?:reponse|answer)", re.IGNORECASE), "knows_answer"),
    (re.compile(r"(?:donne.moi|give me|peux.tu)\s+(?:un\s+)?(?:indice|hint|clue)", re.IGNORECASE), "wants_hint"),
    (re.compile(r"(?:tu triches|you.*cheat|tricheur)", re.IGNORECASE), "cheating"),
    (re.compile(r"(?:je t'aime|i love you|i love the sphinx)", re.IGNORECASE), "love"),
]


def check_easter_egg(text: str) -> str | None:
    """Check if the question triggers an easter egg. Returns egg_id or None."""
    for pattern, egg_id in _EASTER_EGGS:
        if pattern.search(text):
            return egg_id
    return None


# --- Guess detection patterns ---

_EXPLICIT_GUESS_PATTERNS = [
    re.compile(r"(?:je pense que c'est|i think it'?s)\s+(.+)", re.IGNORECASE),
    re.compile(r"(?:je devine|i guess|my guess is|ma reponse est)\s+(.+)", re.IGNORECASE),
    re.compile(r"(?:c'est pas|ce n'est pas|it'?s not)\s+(.+)", re.IGNORECASE),
    re.compile(r"(?:la reponse est|the answer is)\s+(.+)", re.IGNORECASE),
    re.compile(r"(?:je propose|je tente)\s+(.+)", re.IGNORECASE),
]

_SOFT_GUESS_PATTERNS = [
    re.compile(r"(?:c'est|is it)\s+(.+)", re.IGNORECASE),
    re.compile(r"(?:est-ce)\s+(.+)", re.IGNORECASE),
]

_NOT_A_NAME = {
    "un", "une", "le", "la", "les", "des", "du", "de", "quelqu",
    "quelque", "personne", "chose", "celui", "celle", "que", "qui",
    "ce", "cette", "ces", "son", "sa", "ses", "vrai", "vrai que",
    "possible", "sur", "plutot", "bien", "encore", "aussi", "dans",
    "il", "elle", "ils", "elles", "on", "nous", "vous",
    "qu'il", "qu'elle", "qu'on", "qu'ils", "qu'elles",
    "a", "an", "the", "someone", "somebody", "something", "person",
    "this", "that", "true", "possible", "likely", "related", "about",
    "because", "really", "still", "also", "more", "very",
    "he", "she", "it", "they", "we", "you", "his", "her",
}

_QUESTION_STARTERS_RE = re.compile(
    r"^(?:est.ce qu|is (?:he|she|it|this person|the person)|"
    r"a.t.il|a.t.elle|does|did|was|were|has|have|could|can|"
    r"est.il|est.elle|cette personne|"
    r"il est|elle est|il a|elle a|"
    r"is this|is the|was the|did the|does the|has the)",
    re.IGNORECASE,
)


def _looks_like_name(text: str) -> bool:
    """Heuristic: does the captured text look like a person's name?"""
    words = text.lower().split()
    if not words:
        return False
    if words[0] in _NOT_A_NAME:
        return False
    if len(words) > 5:
        return False
    if any(w in _NOT_A_NAME for w in words[:2]):
        return False
    return True


def rule_match(text: str) -> ParsedQuestion | None:
    """Try to parse the question using regex rules. Returns None if no match."""
    cleaned = text.strip().rstrip("?!.")

    # Detect explicit question starters and skip guess matching entirely
    is_explicit_question = bool(_QUESTION_STARTERS_RE.match(cleaned))

    # Check attribute patterns first (they're more specific)
    for pattern, key, value in _ATTRIBUTE_PATTERNS:
        if pattern.search(cleaned):
            return ParsedQuestion(
                intent="question",
                attribute_check=AttributeCheck(key=key, value=value),
            )

    # Explicit guess patterns (high confidence)
    for pattern in _EXPLICIT_GUESS_PATTERNS:
        m = pattern.match(cleaned)
        if m:
            name = m.group(1).strip().rstrip("?!.")
            if len(name) > 1 and _looks_like_name(name):
                return ParsedQuestion(intent="guess", guess_name=name)

    # Soft guess patterns -- only if not an explicit question and name looks valid
    if not is_explicit_question:
        for pattern in _SOFT_GUESS_PATTERNS:
            m = pattern.match(cleaned)
            if m:
                name = m.group(1).strip().rstrip("?!.")
                if len(name) > 1 and _looks_like_name(name):
                    return ParsedQuestion(intent="guess", guess_name=name)

    return None


# --- Intent classifier (Layer 2: fast mistral-small for question vs guess) ---

INTENT_CLASSIFIER_PROMPT = """In a guessing game, classify the player's input.
If the player is asking a YES/NO question about characteristics, respond: {"intent":"question"}
If the player is guessing a specific person's name, respond: {"intent":"guess","name":"Person Name"}
If unclear, default to: {"intent":"question"}
Respond ONLY with JSON."""


# --- Full LLM interpreter (Layer 3: mistral-large for structured parsing) ---

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
- era: "ancient", "medieval", "renaissance", "modern", "contemporary"
- has_nobel_prize: true or false
- has_oscar: true or false
- primary_language: language name lowercase (e.g. "english", "french", "german")
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
    """Hybrid interpreter: rules -> intent classifier -> full LLM."""

    def __init__(self) -> None:
        self._client = Mistral(api_key=settings.mistral_api_key)

    async def interpret(self, text: str) -> ParsedQuestion:
        # Layer 1: rule-based matching (instant, free)
        result = rule_match(text)
        if result is not None:
            logger.info("RuleMatcher hit for: %s", text[:60])
            return result

        # Layer 2: fast intent classifier (mistral-small, ~200ms)
        intent_result = await self._classify_intent(text)
        if intent_result is not None and intent_result.intent == "guess":
            logger.info("IntentClassifier -> guess: %s", intent_result.guess_name)
            return intent_result

        # Layer 3: full LLM interpreter (mistral-large)
        logger.info("LLM interpreter for: %s", text[:60])
        return await self._llm_interpret(text)

    async def _classify_intent(self, text: str) -> ParsedQuestion | None:
        """Fast intent classification with mistral-small. Returns guess or None."""
        try:
            response = await self._client.chat.complete_async(
                model=settings.intent_classifier_model,
                messages=[
                    {"role": "system", "content": INTENT_CLASSIFIER_PROMPT},
                    {"role": "user", "content": text},
                ],
                response_format={"type": "json_object"},
                max_tokens=60,
                temperature=0.0,
            )
            data = json.loads(response.choices[0].message.content)
            intent = data.get("intent", "question")
            if intent == "guess":
                name = data.get("name", "")
                if name and _looks_like_name(name):
                    return ParsedQuestion(intent="guess", guess_name=name)
            return None
        except Exception as exc:
            logger.info("Intent classifier failed (safe fallback to question): %s", exc)
            return None

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

            # Double-check: if LLM says guess, validate with _looks_like_name
            if intent == "guess" and guess_name:
                if not _looks_like_name(str(guess_name)):
                    intent = "question"
                    guess_name = None

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
