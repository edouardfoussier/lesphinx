"""Normalize free-text STT output to yes/no/unknown."""

_YES_KEYWORDS = {
    "fr": {"oui", "ouais", "yes", "yep", "yeah", "bien sur", "tout a fait", "absolument", "exact", "exactement", "si", "correct"},
    "en": {"yes", "yeah", "yep", "yup", "sure", "of course", "absolutely", "correct", "right", "exactly", "indeed"},
}

_NO_KEYWORDS = {
    "fr": {"non", "no", "nope", "pas du tout", "absolument pas", "nan", "nah", "jamais"},
    "en": {"no", "nope", "nah", "not at all", "absolutely not", "never", "wrong", "incorrect"},
}

_UNKNOWN_KEYWORDS = {
    "fr": {"je ne sais pas", "je sais pas", "aucune idee", "sais pas", "peut etre", "pas sur", "unknown", "bof"},
    "en": {"i don't know", "don't know", "no idea", "not sure", "maybe", "unknown", "idk", "unsure"},
}


def normalize_answer(text: str, language: str = "fr") -> str:
    """Normalize transcribed text to 'yes', 'no', or 'unknown'.

    Checks longer keywords first to avoid partial matches
    (e.g. "absolutely not" must match NO before "absolutely" matches YES).
    """
    cleaned = text.lower().strip().rstrip(".!?,;")

    # Build a scored list: (keyword, category) sorted longest-first
    candidates: list[tuple[str, str]] = []
    for lang in (language, "fr" if language == "en" else "en"):
        for kw in _NO_KEYWORDS.get(lang, set()):
            candidates.append((kw, "no"))
        for kw in _YES_KEYWORDS.get(lang, set()):
            candidates.append((kw, "yes"))
        for kw in _UNKNOWN_KEYWORDS.get(lang, set()):
            candidates.append((kw, "unknown"))

    # Sort by length descending so longer (more specific) phrases match first
    candidates.sort(key=lambda x: len(x[0]), reverse=True)

    for keyword, category in candidates:
        if keyword in cleaned:
            return category

    return "unknown"
