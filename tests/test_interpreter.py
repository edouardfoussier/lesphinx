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
    def test_truly_complex_question(self):
        r = rule_match("Did this person revolutionize their field?")
        assert r is None

    def test_truly_vague_question(self):
        r = rule_match("Was this person influential in their community?")
        assert r is None

class TestNewAttributePatterns:
    def test_nobel_prize(self):
        r = rule_match("Did this person win a Nobel Prize?")
        assert r is not None
        assert r.attribute_check.key == "has_nobel_prize"
        assert r.attribute_check.value is True

    def test_20th_century(self):
        r = rule_match("Was this person important in the 20th century?")
        assert r is not None
        assert r.attribute_check.key == "era"
        assert r.attribute_check.value == "contemporary"

    def test_oscar(self):
        r = rule_match("A-t-il gagné un Oscar ?")
        assert r is not None
        assert r.attribute_check.key == "has_oscar"

    def test_era_ancient(self):
        r = rule_match("Is this person from ancient times?")
        assert r is not None
        assert r.attribute_check.key == "era"
        assert r.attribute_check.value == "ancient"


class TestNobelPrizePatterns:
    def test_french_prix_nobel(self):
        r = rule_match("A-t-il recu le prix Nobel ?")
        assert r is not None
        assert r.attribute_check.key == "has_nobel_prize"
        assert r.attribute_check.value is True

    def test_nobelise_ascii(self):
        r = rule_match("Est-il nobelise ?")
        assert r is not None
        assert r.attribute_check.key == "has_nobel_prize"

    def test_english_nobel(self):
        r = rule_match("Has this person won a Nobel?")
        assert r is not None
        assert r.attribute_check.key == "has_nobel_prize"

    def test_nobel_prize_full(self):
        r = rule_match("Did this person win a Nobel Prize?")
        assert r is not None
        assert r.attribute_check.key == "has_nobel_prize"
        assert r.attribute_check.value is True


class TestOscarPatterns:
    def test_academy_award(self):
        r = rule_match("Did they win an Academy Award?")
        assert r is not None
        assert r.attribute_check.key == "has_oscar"
        assert r.attribute_check.value is True

    def test_french_oscar(self):
        r = rule_match("A-t-il gagne un oscar ?")
        assert r is not None
        assert r.attribute_check.key == "has_oscar"

    def test_cesars_ascii(self):
        r = rule_match("A-t-il recu un cesars ?")
        assert r is not None
        assert r.attribute_check.key == "has_oscar"


class TestEraPatterns:
    def test_medieval(self):
        r = rule_match("Is this person from the Middle Ages?")
        assert r is not None
        assert r.attribute_check.key == "era"
        assert r.attribute_check.value == "medieval"

    def test_french_moyen_age(self):
        r = rule_match("Vient-il du Moyen-Age ?")
        assert r is not None
        assert r.attribute_check.key == "era"
        assert r.attribute_check.value == "medieval"

    def test_renaissance(self):
        r = rule_match("Is this person from the Renaissance?")
        assert r is not None
        assert r.attribute_check.key == "era"
        assert r.attribute_check.value == "renaissance"

    def test_ancient(self):
        r = rule_match("Is this person from antiquite?")
        assert r is not None
        assert r.attribute_check.key == "era"
        assert r.attribute_check.value == "ancient"

    def test_ancient_english(self):
        r = rule_match("Is this person ancient?")
        assert r is not None
        assert r.attribute_check.key == "era"
        assert r.attribute_check.value == "ancient"

    def test_19th_century_matches_born_before_1900(self):
        """'19th century' is first caught by the born_before_1900 pattern."""
        r = rule_match("Was this person born in the 19th century?")
        assert r is not None
        assert r.attribute_check.key == "born_before_1900"
        assert r.attribute_check.value is True

    def test_ne_au_20e_siecle(self):
        """'ne au 20e' matches the century/era pattern for contemporary."""
        r = rule_match("Est-il ne au 20e siecle ?")
        assert r is not None
        assert r.attribute_check.key == "era"
        assert r.attribute_check.value == "contemporary"

    def test_21st_century(self):
        r = rule_match("Is this person from the 21st century?")
        assert r is not None
        assert r.attribute_check.key == "era"
        assert r.attribute_check.value == "contemporary"

    def test_born_before_1900(self):
        r = rule_match("Was this person born before 1900?")
        assert r is not None
        assert r.attribute_check.key == "born_before_1900"
        assert r.attribute_check.value is True

    def test_born_before_1950(self):
        r = rule_match("Was this person born before 1950?")
        assert r is not None
        assert r.attribute_check.key == "born_before_1950"
        assert r.attribute_check.value is True

    def test_epoque_moderne(self):
        r = rule_match("Est-il de l'epoque moderne ?")
        assert r is not None
        assert r.attribute_check.key == "era"
        assert r.attribute_check.value == "modern"


class TestLanguagePatterns:
    def test_francophone(self):
        r = rule_match("Est-il francophone ?")
        assert r is not None
        assert r.attribute_check.key == "primary_language"
        assert r.attribute_check.value == "french"

    def test_anglophone(self):
        r = rule_match("Is this person anglophone?")
        assert r is not None
        assert r.attribute_check.key == "primary_language"
        assert r.attribute_check.value == "english"

    def test_langue_anglaise(self):
        r = rule_match("Sa langue est-elle la langue anglaise ?")
        assert r is not None
        assert r.attribute_check.key == "primary_language"
        assert r.attribute_check.value == "english"

    def test_nationality_words_hit_nationality_first(self):
        """Words like 'francais', 'allemand' match nationality before language
        due to pattern ordering. The dedicated keywords (francophone, etc.)
        bypass this to reliably match language."""
        r = rule_match("Parle-t-il allemand ?")
        assert r is not None
        assert r.attribute_check.key == "nationality"
        assert r.attribute_check.value == "german"

    def test_hispanophone(self):
        r = rule_match("Is this person hispanophone?")
        assert r is not None
        assert r.attribute_check.key == "primary_language"
        assert r.attribute_check.value == "spanish"

    def test_germanophone(self):
        r = rule_match("Is this person germanophone?")
        assert r is not None
        assert r.attribute_check.key == "primary_language"
        assert r.attribute_check.value == "german"

    def test_langue_francaise(self):
        r = rule_match("La langue francaise est-elle sa langue ?")
        assert r is not None
        assert r.attribute_check.key == "primary_language"
        assert r.attribute_check.value == "french"


class TestEasterEggs:
    def test_sphinx_identity_french(self):
        from lesphinx.llm.interpreter import check_easter_egg
        assert check_easter_egg("Es-tu le Sphinx ?") == "sphinx_identity"

    def test_sphinx_identity_tu_es(self):
        from lesphinx.llm.interpreter import check_easter_egg
        assert check_easter_egg("Tu es le Sphinx ?") == "sphinx_identity"

    def test_knows_answer_french(self):
        from lesphinx.llm.interpreter import check_easter_egg
        assert check_easter_egg("Connais-tu la reponse ?") == "knows_answer"

    def test_knows_answer_sais_tu(self):
        from lesphinx.llm.interpreter import check_easter_egg
        assert check_easter_egg("Sais-tu la reponse ?") == "knows_answer"

    def test_wants_hint_french(self):
        from lesphinx.llm.interpreter import check_easter_egg
        assert check_easter_egg("Donne-moi un indice") == "wants_hint"

    def test_wants_hint_peux_tu(self):
        from lesphinx.llm.interpreter import check_easter_egg
        assert check_easter_egg("Peux-tu un indice") == "wants_hint"

    def test_cheating_french(self):
        from lesphinx.llm.interpreter import check_easter_egg
        assert check_easter_egg("Tu triches !") == "cheating"

    def test_cheating_tricheur(self):
        from lesphinx.llm.interpreter import check_easter_egg
        assert check_easter_egg("Tu es un tricheur") == "cheating"

    def test_cheating_english(self):
        from lesphinx.llm.interpreter import check_easter_egg
        assert check_easter_egg("You are cheating!") == "cheating"

    def test_love_french(self):
        from lesphinx.llm.interpreter import check_easter_egg
        assert check_easter_egg("Je t'aime, Sphinx") == "love"

    def test_love_english(self):
        from lesphinx.llm.interpreter import check_easter_egg
        assert check_easter_egg("I love you") == "love"

    def test_no_easter_egg_on_normal_question(self):
        from lesphinx.llm.interpreter import check_easter_egg
        assert check_easter_egg("Is this person a scientist?") is None

    def test_no_easter_egg_empty(self):
        from lesphinx.llm.interpreter import check_easter_egg
        assert check_easter_egg("") is None
