"""Guess verification: fuzzy match player's guess against the secret character."""

from __future__ import annotations

import unicodedata

from lesphinx.game.characters import Character

MIN_CANDIDATE_LEN = 4


def _normalize(text: str) -> str:
    """Lowercase, strip accents, collapse whitespace."""
    text = text.lower().strip()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return " ".join(text.split())


def _levenshtein(a: str, b: str) -> int:
    if len(a) < len(b):
        return _levenshtein(b, a)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a):
        curr = [i + 1]
        for j, cb in enumerate(b):
            cost = 0 if ca == cb else 1
            curr.append(min(curr[j] + 1, prev[j + 1] + 1, prev[j] + cost))
        prev = curr
    return prev[-1]


def check_guess(guess: str, character: Character) -> bool:
    """Check if the player's guess matches the secret character.

    Strategy:
    1. Exact normalized match against full name or aliases
    2. Last-name match (if guess is a single word matching the last name)
    3. Levenshtein fuzzy match -- only between strings of similar length
    """
    guess_norm = _normalize(guess)
    if not guess_norm:
        return False

    full_name_norm = _normalize(character.name)

    # Build candidate list, skipping very short aliases that cause false positives
    candidates = [character.name]
    for alias in character.aliases:
        if len(alias.strip()) >= MIN_CANDIDATE_LEN:
            candidates.append(alias)

    # Pass 1: exact normalized match
    for candidate in candidates:
        if guess_norm == _normalize(candidate):
            return True

    # Pass 2: last-name match (single-word guess matching last word of full name)
    name_parts = full_name_norm.split()
    if len(name_parts) >= 2:
        last_name = name_parts[-1]
        if len(last_name) >= MIN_CANDIDATE_LEN and guess_norm == last_name:
            return True

    # Pass 3: Levenshtein with strict threshold, only between similar-length strings
    for candidate in candidates:
        cand_norm = _normalize(candidate)
        if not cand_norm:
            continue

        shorter, longer = min(len(guess_norm), len(cand_norm)), max(len(guess_norm), len(cand_norm))
        if shorter < MIN_CANDIDATE_LEN:
            continue
        # Reject if lengths differ too much (> 40% difference)
        if shorter / longer < 0.6:
            continue

        dist = _levenshtein(guess_norm, cand_norm)
        threshold = max(2, longer // 5)
        if dist <= threshold:
            return True

    return False
