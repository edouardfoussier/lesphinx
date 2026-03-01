"""Tests for SphinxVoice mood system and templates."""

import pytest

from lesphinx.game.models import GameSession, Turn
from lesphinx.game.state import GameState
from lesphinx.llm.voice import MOODS, TEMPLATES, get_mood


def _make_session(question_count=0, guess_count=0, yes_count=0, result=None) -> GameSession:
    turns = []
    for i in range(question_count):
        answer = "yes" if i < yes_count else "no"
        turns.append(Turn(
            turn_number=i + 1,
            player_text=f"Q{i}?",
            intent="question",
            raw_answer=answer,
            sphinx_utterance="...",
        ))
    return GameSession(
        language="fr",
        difficulty="medium",
        secret_character_id="x",
        question_count=question_count,
        guess_count=guess_count,
        turns=turns,
        result=result,
    )


class TestGetMood:
    def test_confident_early_game(self):
        s = _make_session(question_count=3)
        assert get_mood(s) == "confident"

    def test_confident_at_5_questions(self):
        s = _make_session(question_count=5)
        assert get_mood(s) == "confident"

    def test_intrigued_many_yes(self):
        s = _make_session(question_count=8, yes_count=4)
        assert get_mood(s) == "intrigued"

    def test_nervous_late_game(self):
        s = _make_session(question_count=13, yes_count=7)
        assert get_mood(s) == "nervous"

    def test_nervous_at_high_yes_ratio(self):
        s = _make_session(question_count=9, yes_count=6)
        assert get_mood(s) == "nervous"

    def test_condescending_after_2_wrong_guesses(self):
        s = _make_session(question_count=10, guess_count=2, yes_count=2)
        assert get_mood(s) == "condescending"

    def test_condescending_priority_over_other_moods(self):
        s = _make_session(question_count=15, guess_count=2, yes_count=10)
        assert get_mood(s) == "condescending"

    def test_not_condescending_after_win(self):
        s = _make_session(question_count=10, guess_count=2, yes_count=2, result="win")
        mood = get_mood(s)
        assert mood != "condescending" or s.result == "win"


class TestTemplates:
    def test_all_answer_types_exist(self):
        for answer in ("yes", "no", "unknown"):
            assert answer in TEMPLATES

    def test_all_moods_have_templates_for_yes(self):
        for mood in MOODS:
            assert mood in TEMPLATES["yes"]
            assert "fr" in TEMPLATES["yes"][mood]
            assert "en" in TEMPLATES["yes"][mood]
            assert len(TEMPLATES["yes"][mood]["fr"]) > 0
            assert len(TEMPLATES["yes"][mood]["en"]) > 0

    def test_all_moods_have_templates_for_no(self):
        for mood in MOODS:
            assert mood in TEMPLATES["no"]

    def test_all_moods_have_templates_for_unknown(self):
        for mood in MOODS:
            assert mood in TEMPLATES["unknown"]

    def test_moods_list(self):
        assert MOODS == ("confident", "intrigued", "nervous", "condescending")
