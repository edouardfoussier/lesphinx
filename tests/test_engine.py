"""Tests for the reversed GameEngine."""

import pytest

from lesphinx.game.engine import GameEngine
from lesphinx.game.models import GameSession
from lesphinx.game.state import GameState


@pytest.fixture
def engine():
    return GameEngine()


@pytest.fixture
def session():
    return GameSession(language="fr", difficulty="medium", secret_character_id="albert_einstein")


class TestStartGame:
    def test_transitions_to_listening(self, engine, session):
        engine.start_game(session)
        assert session.state == GameState.LISTENING

    def test_creates_intro_turn(self, engine, session):
        turn = engine.start_game(session)
        assert len(session.turns) == 1
        assert "Sphinx" in turn.sphinx_utterance

    def test_intro_en(self, engine):
        session = GameSession(language="en", difficulty="easy", secret_character_id="x")
        turn = engine.start_game(session)
        assert "famous" in turn.sphinx_utterance.lower()


class TestProcessQuestion:
    def _start(self, engine, session):
        engine.start_game(session)

    def test_increments_question_count(self, engine, session):
        self._start(engine, session)
        engine.process_question(session, "Is he a man?", "yes", "Yes, mortal.")
        assert session.question_count == 1

    def test_records_turn(self, engine, session):
        self._start(engine, session)
        turn = engine.process_question(session, "Is he alive?", "no", "No, mortal.")
        assert turn.player_text == "Is he alive?"
        assert turn.raw_answer == "no"
        assert turn.intent == "question"

    def test_state_listening_after_question(self, engine, session):
        self._start(engine, session)
        engine.process_question(session, "Q?", "yes", "Yes.")
        assert session.state == GameState.LISTENING

    def test_game_ends_at_max_questions(self, engine, session):
        self._start(engine, session)
        for i in range(20):
            engine.process_question(session, f"Q{i}?", "yes", "Yes.")
        assert session.state == GameState.ENDED
        assert session.result == "lose"


class TestProcessGuess:
    def _start(self, engine, session):
        engine.start_game(session)

    def test_correct_guess_wins(self, engine, session, einstein):
        self._start(engine, session)
        turn = engine.process_guess(session, "Einstein", True, einstein)
        assert session.result == "win"
        assert session.state == GameState.ENDED
        assert "Einstein" in turn.sphinx_utterance

    def test_wrong_guess_continues(self, engine, session, einstein):
        self._start(engine, session)
        turn = engine.process_guess(session, "Newton", False, einstein)
        assert session.result is None
        assert session.state == GameState.LISTENING
        assert session.guess_count == 1

    def test_max_guesses_ends_game(self, engine, session, einstein):
        self._start(engine, session)
        engine.process_guess(session, "A", False, einstein)
        engine.process_guess(session, "B", False, einstein)
        engine.process_guess(session, "C", False, einstein)
        assert session.state == GameState.ENDED
        assert session.result == "lose"
        assert session.guess_count == 3


class TestHints:
    def test_no_hint_at_start(self, engine, session):
        engine.start_game(session)
        assert engine.should_give_hint(session) is False

    def test_hint_after_n_questions(self, engine, session):
        engine.start_game(session)
        for i in range(7):
            engine.process_question(session, f"Q{i}?", "yes", "Yes.")
        assert engine.should_give_hint(session) is True

    def test_no_hint_if_guessed(self, engine, session, einstein):
        engine.start_game(session)
        for i in range(6):
            engine.process_question(session, f"Q{i}?", "yes", "Yes.")
        engine.process_guess(session, "Wrong", False, einstein)
        engine.process_question(session, "Q7?", "yes", "Yes.")
        assert engine.should_give_hint(session) is False
