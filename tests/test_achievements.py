"""Tests for the achievement system."""

import pytest

from lesphinx.game.achievements import ACHIEVEMENTS, check_achievements
from lesphinx.game.models import GameSession, Turn
from lesphinx.game.state import GameState


def _make_session(**kwargs) -> GameSession:
    defaults = {
        "language": "fr",
        "difficulty": "medium",
        "secret_character_id": "x",
        "state": GameState.ENDED,
    }
    defaults.update(kwargs)
    return GameSession(**defaults)


class TestSpeedDemon:
    def test_unlocked_under_5_questions(self):
        s = _make_session(result="win", question_count=4, guess_count=1)
        ids = [a["id"] for a in check_achievements(s)]
        assert "speed_demon" in ids

    def test_locked_at_5_questions(self):
        s = _make_session(result="win", question_count=5, guess_count=1)
        ids = [a["id"] for a in check_achievements(s)]
        assert "speed_demon" not in ids

    def test_locked_on_loss(self):
        s = _make_session(result="lose", question_count=3, guess_count=1)
        ids = [a["id"] for a in check_achievements(s)]
        assert "speed_demon" not in ids


class TestNoHints:
    def test_unlocked_with_no_hints(self):
        s = _make_session(result="win", hints_given=[])
        ids = [a["id"] for a in check_achievements(s)]
        assert "no_hints" in ids

    def test_locked_with_hints(self):
        s = _make_session(result="win", hints_given=["hint1"])
        ids = [a["id"] for a in check_achievements(s)]
        assert "no_hints" not in ids


class TestFirstTry:
    def test_unlocked_on_first_guess(self):
        s = _make_session(result="win", guess_count=1)
        ids = [a["id"] for a in check_achievements(s)]
        assert "first_try" in ids

    def test_locked_on_second_guess(self):
        s = _make_session(result="win", guess_count=2)
        ids = [a["id"] for a in check_achievements(s)]
        assert "first_try" not in ids


class TestHardWinner:
    def test_unlocked_on_hard(self):
        s = _make_session(result="win", difficulty="hard")
        ids = [a["id"] for a in check_achievements(s)]
        assert "hard_winner" in ids

    def test_locked_on_medium(self):
        s = _make_session(result="win", difficulty="medium")
        ids = [a["id"] for a in check_achievements(s)]
        assert "hard_winner" not in ids


class TestPersistent:
    def test_unlocked_at_15_questions(self):
        s = _make_session(result="win", question_count=15, guess_count=1)
        ids = [a["id"] for a in check_achievements(s)]
        assert "persistent" in ids

    def test_locked_at_14_questions(self):
        s = _make_session(result="win", question_count=14, guess_count=1)
        ids = [a["id"] for a in check_achievements(s)]
        assert "persistent" not in ids


class TestStreak:
    def test_unlocked_at_streak_3(self):
        s = _make_session(result="win", current_streak=3)
        ids = [a["id"] for a in check_achievements(s)]
        assert "streak_3" in ids

    def test_locked_at_streak_2(self):
        s = _make_session(result="win", current_streak=2)
        ids = [a["id"] for a in check_achievements(s)]
        assert "streak_3" not in ids


class TestPerfectGame:
    def test_unlocked_perfect(self):
        s = _make_session(
            result="win", guess_count=1, hints_given=[], question_count=9
        )
        ids = [a["id"] for a in check_achievements(s)]
        assert "perfect_game" in ids

    def test_locked_with_hint(self):
        s = _make_session(
            result="win", guess_count=1, hints_given=["h1"], question_count=5
        )
        ids = [a["id"] for a in check_achievements(s)]
        assert "perfect_game" not in ids

    def test_locked_at_10_questions(self):
        s = _make_session(
            result="win", guess_count=1, hints_given=[], question_count=10
        )
        ids = [a["id"] for a in check_achievements(s)]
        assert "perfect_game" not in ids


class TestMediumWin:
    def test_unlocked_on_medium(self):
        s = _make_session(result="win", difficulty="medium")
        ids = [a["id"] for a in check_achievements(s)]
        assert "medium_win" in ids

    def test_locked_on_hard(self):
        s = _make_session(result="win", difficulty="hard")
        ids = [a["id"] for a in check_achievements(s)]
        assert "medium_win" not in ids


class TestCheckAchievementsFormat:
    def test_returns_list_of_dicts(self):
        s = _make_session(result="win", question_count=3, guess_count=1)
        achievements = check_achievements(s)
        assert isinstance(achievements, list)
        for a in achievements:
            assert "id" in a
            assert "icon" in a
            assert "name" in a
            assert "desc" in a

    def test_achievement_definitions_count(self):
        assert len(ACHIEVEMENTS) == 8

    def test_all_achievements_have_required_keys(self):
        for a in ACHIEVEMENTS:
            assert "id" in a
            assert "icon" in a
            assert "name" in a
            assert "desc" in a
            assert "check" in a
            assert callable(a["check"])
