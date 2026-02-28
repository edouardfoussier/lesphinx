"""Character database: loading, selection, fact store, and answer resolution."""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

DATA_PATH = Path(__file__).parent.parent / "data" / "characters.json"


class Character(BaseModel):
    id: str
    name: str
    aliases: list[str] = Field(default_factory=list)
    difficulty: Literal["easy", "medium", "hard"]
    attributes: dict[str, str | bool]
    facts: list[str] = Field(default_factory=list)
    themes: list[str] = Field(default_factory=list)


AnswerType = Literal["yes", "no", "unknown"]


class ResolvedAnswer(BaseModel):
    answer: AnswerType
    matched_fact: str | None = None
    source: Literal["attribute", "fact", "none"] = "none"


def load_characters(path: Path = DATA_PATH) -> list[Character]:
    """Load characters from the JSON database."""
    with open(path) as f:
        raw = json.load(f)
    return [Character(**c) for c in raw]


class SecretSelector:
    """Picks a random character by difficulty level."""

    def __init__(self, characters: list[Character]) -> None:
        self._by_difficulty: dict[str, list[Character]] = {
            "easy": [], "medium": [], "hard": [],
        }
        for c in characters:
            self._by_difficulty[c.difficulty].append(c)

    def pick(
        self,
        difficulty: str = "medium",
        exclude_ids: set[str] | None = None,
        themes: list[str] | None = None,
    ) -> Character:
        pool = self._by_difficulty.get(difficulty, [])
        if themes:
            wanted = {t.lower().strip() for t in themes if t.strip()}
            if wanted:
                filtered = [
                    c for c in pool
                    if wanted.intersection({t.lower() for t in c.themes})
                ]
                if filtered:
                    pool = filtered
        if exclude_ids:
            pool = [c for c in pool if c.id not in exclude_ids]
        if not pool:
            all_chars = [c for chars in self._by_difficulty.values() for c in chars]
            if exclude_ids:
                all_chars = [c for c in all_chars if c.id not in exclude_ids]
            pool = all_chars
        if not pool:
            raise ValueError("No characters available")
        return random.choice(pool)

    @property
    def count(self) -> int:
        return sum(len(v) for v in self._by_difficulty.values())

    def count_by_difficulty(self, difficulty: str) -> int:
        return len(self._by_difficulty.get(difficulty, []))


class FactStore:
    """Wraps a Character and exposes deterministic answer lookup."""

    def __init__(self, character: Character) -> None:
        self.character = character
        self._fact_words: list[tuple[set[str], str]] = []
        for fact in character.facts:
            words = set(fact.lower().split())
            self._fact_words.append((words, fact))

    def check_attribute(self, key: str, value: str | bool) -> AnswerType:
        """Check a structured attribute. Returns yes/no."""
        stored = self.character.attributes.get(key)
        if stored is None:
            return "unknown"

        if isinstance(value, bool):
            return "yes" if stored == value else "no"

        if isinstance(stored, bool):
            str_val = str(value).lower()
            if str_val in ("true", "yes", "1"):
                return "yes" if stored else "no"
            if str_val in ("false", "no", "0"):
                return "yes" if not stored else "no"
            return "unknown"

        return "yes" if str(stored).lower() == str(value).lower() else "no"

    def search_facts(self, keywords: list[str]) -> tuple[AnswerType, str | None]:
        """Search natural language facts for keyword matches.
        Returns (yes, matched_fact) or (unknown, None)."""
        if not keywords:
            return "unknown", None

        kw_lower = [kw.lower() for kw in keywords]

        best_match: str | None = None
        best_score = 0

        for fact_words, fact_text in self._fact_words:
            score = sum(1 for kw in kw_lower if kw in fact_words or any(kw in w for w in fact_words))
            if score > best_score:
                best_score = score
                best_match = fact_text

        if best_score >= 1 and best_match:
            return "yes", best_match

        return "unknown", None


class AnswerResolver:
    """Resolves a parsed question against the FactStore. Purely deterministic."""

    @staticmethod
    def resolve(
        fact_store: FactStore,
        attribute_check: dict[str, str | bool] | None = None,
        fact_keywords: list[str] | None = None,
    ) -> ResolvedAnswer:
        if attribute_check:
            key = attribute_check.get("key", "")
            value = attribute_check.get("value", "")
            if key:
                answer = fact_store.check_attribute(key, value)
                return ResolvedAnswer(answer=answer, source="attribute")

        if fact_keywords:
            answer, matched = fact_store.search_facts(fact_keywords)
            return ResolvedAnswer(answer=answer, matched_fact=matched, source="fact")

        return ResolvedAnswer(answer="unknown", source="none")
