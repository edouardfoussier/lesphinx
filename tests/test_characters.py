"""Tests for character loading, selection, fact store, and answer resolution."""

import pytest

import json
from pathlib import Path

from lesphinx.game.characters import AnswerResolver, FactStore, SecretSelector


class TestSecretSelector:
    def test_pick_by_difficulty(self, selector):
        char = selector.pick("easy")
        assert char.difficulty == "easy"

    def test_pick_medium(self, selector):
        char = selector.pick("medium")
        assert char.difficulty == "medium"

    def test_pick_fallback_when_empty(self, selector):
        char = selector.pick("hard", exclude_ids={"kylian_mbappe"})
        assert char is not None

    def test_pick_excludes_ids(self, selector):
        char = selector.pick("easy", exclude_ids={"albert_einstein", "cleopatra"})
        assert char.id not in {"albert_einstein", "cleopatra"}

    def test_count(self, selector):
        assert selector.count == 3

    def test_count_by_difficulty(self, selector):
        assert selector.count_by_difficulty("easy") == 2
        assert selector.count_by_difficulty("medium") == 1

    def test_raises_when_no_characters(self):
        sel = SecretSelector([])
        with pytest.raises(ValueError):
            sel.pick("easy")


class TestFactStore:
    def test_check_attribute_gender_yes(self, einstein_facts):
        assert einstein_facts.check_attribute("gender", "male") == "yes"

    def test_check_attribute_gender_no(self, einstein_facts):
        assert einstein_facts.check_attribute("gender", "female") == "no"

    def test_check_attribute_alive_false(self, einstein_facts):
        assert einstein_facts.check_attribute("alive", False) == "yes"

    def test_check_attribute_alive_true(self, einstein_facts):
        assert einstein_facts.check_attribute("alive", True) == "no"

    def test_check_attribute_nationality(self, einstein_facts):
        assert einstein_facts.check_attribute("nationality", "german") == "yes"
        assert einstein_facts.check_attribute("nationality", "french") == "no"

    def test_check_attribute_unknown_key(self, einstein_facts):
        assert einstein_facts.check_attribute("favorite_color", "blue") == "unknown"

    def test_search_facts_match(self, einstein_facts):
        answer, fact = einstein_facts.search_facts(["Nobel", "Prize"])
        assert answer == "yes"
        assert fact is not None
        assert "Nobel" in fact

    def test_search_facts_violin(self, einstein_facts):
        answer, fact = einstein_facts.search_facts(["violin"])
        assert answer == "yes"
        assert "violin" in fact.lower()

    def test_search_facts_no_match(self, einstein_facts):
        answer, fact = einstein_facts.search_facts(["basketball", "NBA"])
        assert answer == "unknown"
        assert fact is None

    def test_search_facts_empty_keywords(self, einstein_facts):
        answer, fact = einstein_facts.search_facts([])
        assert answer == "unknown"


class TestAnswerResolver:
    def test_resolve_attribute(self, einstein_facts):
        result = AnswerResolver.resolve(
            einstein_facts,
            attribute_check={"key": "field", "value": "science"},
        )
        assert result.answer == "yes"
        assert result.source == "attribute"

    def test_resolve_fact_keywords(self, einstein_facts):
        result = AnswerResolver.resolve(
            einstein_facts,
            fact_keywords=["relativity"],
        )
        assert result.answer == "yes"
        assert result.source == "fact"
        assert result.matched_fact is not None

    def test_resolve_no_match(self, einstein_facts):
        result = AnswerResolver.resolve(
            einstein_facts,
            fact_keywords=["tennis", "wimbledon"],
        )
        assert result.answer == "unknown"
        assert result.source == "fact"

    def test_resolve_attribute_takes_priority(self, einstein_facts):
        result = AnswerResolver.resolve(
            einstein_facts,
            attribute_check={"key": "gender", "value": "male"},
            fact_keywords=["something"],
        )
        assert result.answer == "yes"
        assert result.source == "attribute"

    def test_resolve_nothing(self, einstein_facts):
        result = AnswerResolver.resolve(einstein_facts)
        assert result.answer == "unknown"
        assert result.source == "none"


class TestEnrichedCharacterAttributes:
    """Verify all characters in the real JSON have the enriched attributes."""

    VALID_ERAS = {"ancient", "medieval", "renaissance", "modern", "contemporary"}
    REQUIRED_ENRICHED_KEYS = {"birth_year", "era", "has_nobel_prize", "has_oscar", "primary_language"}

    @pytest.fixture(scope="class")
    def raw_characters(self):
        data_path = Path(__file__).parent.parent / "lesphinx" / "data" / "characters.json"
        with open(data_path) as f:
            return json.load(f)

    def test_all_characters_have_enriched_keys(self, raw_characters):
        for char in raw_characters:
            attrs = char.get("attributes", {})
            for key in self.REQUIRED_ENRICHED_KEYS:
                assert key in attrs, (
                    f"{char['id']} missing attribute '{key}'"
                )

    def test_era_values_are_valid(self, raw_characters):
        for char in raw_characters:
            era = char.get("attributes", {}).get("era")
            assert era in self.VALID_ERAS, (
                f"{char['id']} has invalid era '{era}'"
            )

    def test_birth_year_is_integer_or_none(self, raw_characters):
        for char in raw_characters:
            by = char.get("attributes", {}).get("birth_year")
            assert by is None or isinstance(by, int), (
                f"{char['id']} birth_year is {type(by).__name__}, expected int or None"
            )

    def test_most_characters_have_birth_year(self, raw_characters):
        with_year = sum(1 for c in raw_characters if c["attributes"].get("birth_year") is not None)
        assert with_year >= len(raw_characters) * 0.95

    def test_has_nobel_prize_is_boolean(self, raw_characters):
        for char in raw_characters:
            val = char.get("attributes", {}).get("has_nobel_prize")
            assert isinstance(val, bool), (
                f"{char['id']} has_nobel_prize is {type(val).__name__}, expected bool"
            )

    def test_has_oscar_is_boolean(self, raw_characters):
        for char in raw_characters:
            val = char.get("attributes", {}).get("has_oscar")
            assert isinstance(val, bool), (
                f"{char['id']} has_oscar is {type(val).__name__}, expected bool"
            )

    def test_primary_language_is_string(self, raw_characters):
        for char in raw_characters:
            val = char.get("attributes", {}).get("primary_language")
            assert isinstance(val, str) and len(val) > 0, (
                f"{char['id']} primary_language is invalid: {val!r}"
            )

    def test_at_least_150_characters(self, raw_characters):
        assert len(raw_characters) >= 150
