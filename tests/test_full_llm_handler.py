"""Tests for Full LLM handler utilities (encoding repair, name leak, surrender)."""

import pytest
from lesphinx.llm.full_llm_handler import (
    _repair_unicode,
    _sanitize_response,
    _contains_name,
    is_surrender,
)
from lesphinx.game.characters import Character


@pytest.fixture
def sample_character():
    return Character(
        id="abe",
        name="Abraham Lincoln",
        aliases=["Abe", "Honest Abe", "Lincoln"],
        difficulty="medium",
        attributes={"field": "politics", "nationality": "American"},
        facts=["16th President of the United States"],
    )


class TestRepairUnicode:
    def test_no_digits_unchanged(self):
        assert _repair_unicode("Bonjour le monde") == "Bonjour le monde"

    def test_fixes_e_acute(self):
        assert _repair_unicode("v9rit9") == "vérité"

    def test_fixes_e_grave(self):
        assert _repair_unicode("r8ve") == "rève"

    def test_fixes_a_grave_mid_word(self):
        assert _repair_unicode("bient0t") == "bientàt"

    def test_mixed_corruption(self):
        result = _repair_unicode("La v9rit9 se r9v8le")
        assert "vérité" in result
        assert "révèle" in result

    def test_preserves_standalone_numbers(self):
        assert _repair_unicode("Il a 42 ans") == "Il a 42 ans"

    def test_preserves_dates(self):
        assert _repair_unicode("En 1789") == "En 1789"


class TestSanitizeResponse:
    def test_strips_full_name(self, sample_character):
        text = "C'est Abraham Lincoln qui a fait cela"
        result = _sanitize_response(text, sample_character)
        assert "Abraham" not in result
        assert "Lincoln" not in result

    def test_strips_partial_name(self, sample_character):
        text = "Lincoln was a great president"
        result = _sanitize_response(text, sample_character)
        assert "Lincoln" not in result

    def test_strips_alias(self, sample_character):
        text = "They called him Honest Abe"
        result = _sanitize_response(text, sample_character)
        assert "Honest Abe" not in result

    def test_preserves_innocent_text(self, sample_character):
        text = "Oui, mortel, cette personne est un homme"
        result = _sanitize_response(text, sample_character)
        assert result == text


class TestContainsName:
    def test_detects_full_name(self, sample_character):
        assert _contains_name("C'est Abraham Lincoln", sample_character)

    def test_detects_partial_name(self, sample_character):
        assert _contains_name("Lincoln was great", sample_character)

    def test_detects_alias(self, sample_character):
        assert _contains_name("Honest Abe did it", sample_character)

    def test_no_false_positive(self, sample_character):
        assert not _contains_name("Oui, mortel, c'est exact", sample_character)

    def test_short_alias_ignored(self, sample_character):
        assert not _contains_name("I abe my time", sample_character)


class TestIsSurrender:
    @pytest.mark.parametrize("text", [
        "je donne ma langue au sphinx",
        "Je donne ma langue au Sphinx !",
        "j'abandonne",
        "J'abandonne",
        "I give up",
        "i give up!",
        "I surrender",
        "je sais plus",
        "dis moi la réponse",
        "tell me the answer",
        "dis moi qui c'est",
        "je ne trouverai jamais",
    ])
    def test_detects_surrender(self, text):
        assert is_surrender(text), f"Should detect surrender: {text!r}"

    @pytest.mark.parametrize("text", [
        "est-ce qu'il est un homme ?",
        "est-il vivant ?",
        "Leonardo DiCaprio",
        "oui",
        "non",
        "je pense que c'est Einstein",
    ])
    def test_no_false_positive(self, text):
        assert not is_surrender(text), f"Should NOT detect surrender: {text!r}"
