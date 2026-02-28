"""Tests for the rule-based question interpreter."""

from lesphinx.llm.interpreter import rule_match


class TestRuleMatchGender:
    def test_french_homme(self):
        r = rule_match("Est-ce un homme ?")
        assert r is not None
        assert r.attribute_check.key == "gender"
        assert r.attribute_check.value == "male"

    def test_english_man(self):
        r = rule_match("Is it a man?")
        assert r is not None
        assert r.attribute_check.key == "gender"
        assert r.attribute_check.value == "male"

    def test_french_femme(self):
        r = rule_match("Est-ce une femme ?")
        assert r is not None
        assert r.attribute_check.key == "gender"
        assert r.attribute_check.value == "female"

    def test_english_woman(self):
        r = rule_match("Is this person a woman?")
        assert r is not None
        assert r.attribute_check.key == "gender"
        assert r.attribute_check.value == "female"


class TestRuleMatchAlive:
    def test_french_vivant(self):
        r = rule_match("Est-il encore en vie ?")
        assert r is not None
        assert r.attribute_check.key == "alive"
        assert r.attribute_check.value is True

    def test_english_alive(self):
        r = rule_match("Is this person still alive?")
        assert r is not None
        assert r.attribute_check.key == "alive"
        assert r.attribute_check.value is True

    def test_french_mort(self):
        r = rule_match("Est-il mort ?")
        assert r is not None
        assert r.attribute_check.key == "alive"
        assert r.attribute_check.value is False


class TestRuleMatchNationality:
    def test_french(self):
        r = rule_match("Est-il francais ?")
        assert r is not None
        assert r.attribute_check.key == "nationality"
        assert r.attribute_check.value == "french"

    def test_american(self):
        r = rule_match("Is this person american?")
        assert r is not None
        assert r.attribute_check.key == "nationality"
        assert r.attribute_check.value == "american"

    def test_british(self):
        r = rule_match("Is he british?")
        assert r is not None
        assert r.attribute_check.key == "nationality"
        assert r.attribute_check.value == "british"


class TestRuleMatchContinent:
    def test_european(self):
        r = rule_match("Is he european?")
        assert r is not None
        assert r.attribute_check.key == "continent"
        assert r.attribute_check.value == "europe"

    def test_french_asiatique(self):
        r = rule_match("Est-il asiatique ?")
        assert r is not None
        assert r.attribute_check.key == "continent"
        assert r.attribute_check.value == "asia"


class TestRuleMatchField:
    def test_scientist(self):
        r = rule_match("Is he a scientist?")
        assert r is not None
        assert r.attribute_check.key == "field"
        assert r.attribute_check.value == "science"

    def test_french_musicien(self):
        r = rule_match("Est-ce un musicien ?")
        assert r is not None
        assert r.attribute_check.key == "field"
        assert r.attribute_check.value == "music"

    def test_sportif(self):
        r = rule_match("Est-il sportif ?")
        assert r is not None
        assert r.attribute_check.key == "field"
        assert r.attribute_check.value == "sports"


class TestRuleMatchGuess:
    def test_french_guess(self):
        r = rule_match("Je pense que c'est Einstein")
        assert r is not None
        assert r.intent == "guess"
        assert r.guess_name == "Einstein"

    def test_english_guess(self):
        r = rule_match("I think it's Albert Einstein")
        assert r is not None
        assert r.intent == "guess"
        assert r.guess_name == "Albert Einstein"

    def test_est_ce_guess(self):
        r = rule_match("Est-ce Einstein ?")
        assert r is not None
        assert r.intent == "guess"
        assert r.guess_name == "Einstein"


class TestRuleMatchNoMatch:
    def test_complex_question(self):
        r = rule_match("Did this person win a Nobel Prize?")
        assert r is None

    def test_vague_question(self):
        r = rule_match("Was this person important in the 20th century?")
        assert r is None
