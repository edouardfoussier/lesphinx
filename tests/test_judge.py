"""Tests for guess verification (fuzzy matching)."""

from lesphinx.game.characters import Character
from lesphinx.game.judge import check_guess


class TestCheckGuess:
    def test_exact_match(self, einstein):
        assert check_guess("Albert Einstein", einstein) is True

    def test_case_insensitive(self, einstein):
        assert check_guess("albert einstein", einstein) is True

    def test_alias_match(self, einstein):
        assert check_guess("Einstein", einstein) is True

    def test_alias_case_insensitive(self, einstein):
        assert check_guess("einstein", einstein) is True

    def test_accents(self, mbappe):
        assert check_guess("Kylian Mbappé", mbappe) is True

    def test_close_typo(self, einstein):
        assert check_guess("Albrt Einstein", einstein) is True

    def test_wrong_name(self, einstein):
        assert check_guess("Isaac Newton", einstein) is False

    def test_completely_different(self, einstein):
        assert check_guess("Madonna", einstein) is False

    def test_empty_string(self, einstein):
        assert check_guess("", einstein) is False

    def test_single_alias(self, cleopatra):
        assert check_guess("Cleopatra", cleopatra) is True

    def test_alias_variant(self, cleopatra):
        assert check_guess("Cleopatra VII", cleopatra) is True

    def test_last_name_match(self, mbappe):
        assert check_guess("Mbappe", mbappe) is True


class TestJudgeFalsePositiveRegression:
    """Regression tests for the false positive bug:
    substring match + short aliases caused cross-character matches."""

    def test_albert_camus_not_einstein(self, einstein):
        assert check_guess("Albert Camus", einstein) is False

    def test_einstein_not_camus(self):
        camus = Character(
            id="albert_camus", name="Albert Camus", aliases=["Camus"],
            difficulty="hard", attributes={"gender": "male"}, facts=[],
        )
        assert check_guess("Albert Einstein", camus) is False

    def test_short_alias_ignored(self):
        char = Character(
            id="test", name="Albert Einstein", aliases=["Al", "AE"],
            difficulty="easy", attributes={}, facts=[],
        )
        assert check_guess("Al Pacino", char) is False
        assert check_guess("Alexander the Great", char) is False

    def test_similar_first_name_different_person(self):
        char = Character(
            id="michael_jordan", name="Michael Jordan", aliases=["Jordan"],
            difficulty="easy", attributes={}, facts=[],
        )
        assert check_guess("Michael Jackson", char) is False

    def test_partial_overlap_rejected(self):
        char = Character(
            id="bob_marley", name="Bob Marley", aliases=["Marley"],
            difficulty="easy", attributes={}, facts=[],
        )
        assert check_guess("Bob Dylan", char) is False
