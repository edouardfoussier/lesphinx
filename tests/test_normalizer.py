"""Tests for STT answer normalizer (longest-match keyword logic)."""

import pytest

from lesphinx.stt.normalizer import normalize_answer


class TestNormalizeFrench:
    def test_oui(self):
        assert normalize_answer("oui", "fr") == "yes"

    def test_ouais(self):
        assert normalize_answer("ouais", "fr") == "yes"

    def test_non(self):
        assert normalize_answer("non", "fr") == "no"

    def test_absolument_pas_matches_no(self):
        """'absolument pas' (NO) must match before 'absolument' (YES)."""
        assert normalize_answer("absolument pas", "fr") == "no"

    def test_absolument_alone_matches_yes(self):
        assert normalize_answer("absolument", "fr") == "yes"

    def test_je_ne_sais_pas(self):
        assert normalize_answer("je ne sais pas", "fr") == "unknown"

    def test_peut_etre(self):
        assert normalize_answer("peut etre", "fr") == "unknown"

    def test_pas_du_tout(self):
        assert normalize_answer("pas du tout", "fr") == "no"

    def test_strips_punctuation(self):
        assert normalize_answer("oui!", "fr") == "yes"
        assert normalize_answer("non...", "fr") == "no"

    def test_case_insensitive(self):
        assert normalize_answer("OUI", "fr") == "yes"
        assert normalize_answer("Non", "fr") == "no"

    def test_unknown_gibberish(self):
        assert normalize_answer("blablabla", "fr") == "unknown"


class TestNormalizeEnglish:
    def test_yes(self):
        assert normalize_answer("yes", "en") == "yes"

    def test_no(self):
        assert normalize_answer("no", "en") == "no"

    def test_absolutely_not_matches_no(self):
        """'absolutely not' (NO) must match before 'absolutely' (YES)."""
        assert normalize_answer("absolutely not", "en") == "no"

    def test_absolutely_alone_matches_yes(self):
        assert normalize_answer("absolutely", "en") == "yes"

    def test_not_at_all(self):
        assert normalize_answer("not at all", "en") == "no"

    def test_i_dont_know(self):
        assert normalize_answer("i don't know", "en") == "unknown"

    def test_maybe(self):
        assert normalize_answer("maybe", "en") == "unknown"

    def test_unknown_gibberish(self):
        assert normalize_answer("xyzzy", "en") == "unknown"


class TestCrossLanguage:
    def test_yes_recognized_in_french_mode(self):
        """English 'yes' should still work when language is French."""
        assert normalize_answer("yes", "fr") == "yes"

    def test_oui_recognized_in_english_mode(self):
        """French 'oui' should still work when language is English."""
        assert normalize_answer("oui", "en") == "yes"
