"""Tests for the GameEngine (rules, state transitions, overrides)."""

import pytest

from lesphinx.game.engine import GameEngine, FALLBACK_QUESTIONS
from lesphinx.game.models import GameSession
from lesphinx.game.state import GameState
from lesphinx.llm.schemas import SphinxAction


@pytest.fixture
def engine():
    return GameEngine()


@pytest.fixture
def session_fr():
    return GameSession(language="fr")


@pytest.fixture
def session_en():
    return GameSession(language="en")


def _make_action(**kwargs) -> SphinxAction:
    defaults = {
        "type": "question",
        "utterance": "Test question?",
        "confidence": 0.3,
        "top_candidates": [],
        "reasoning_brief": "test",
    }
    defaults.update(kwargs)
    return SphinxAction(**defaults)


class TestStartGame:
    def test_initial_state(self, engine, session_fr):
        engine.start_game(session_fr)
        assert session_fr.state == GameState.LISTENING

    def test_creates_intro_turn(self, engine, session_fr):
        turn = engine.start_game(session_fr)
        assert len(session_fr.turns) == 1
        assert turn.sphinx_action_type == "question"
        assert "Sphinx" in turn.sphinx_utterance

    def test_intro_language_en(self, engine, session_en):
        turn = engine.start_game(session_en)
        assert "Sphinx" in turn.sphinx_utterance
        assert "famous" in turn.sphinx_utterance.lower()


class TestProcessAnswer:
    def _start_and_answer(self, engine, session, action=None):
        engine.start_game(session)
        if action is None:
            action = _make_action()
        return engine.process_answer(session, "yes", action)

    def test_records_player_answer(self, engine, session_fr):
        engine.start_game(session_fr)
        engine.process_answer(session_fr, "yes", _make_action())
        assert session_fr.turns[0].player_answer == "yes"

    def test_increments_question_count(self, engine, session_fr):
        self._start_and_answer(engine, session_fr)
        assert session_fr.question_count == 1

    def test_increments_guess_count(self, engine, session_fr):
        engine.start_game(session_fr)
        # Need enough questions before guessing
        for i in range(5):
            action = _make_action(utterance=f"Q{i}?")
            engine.process_answer(session_fr, "yes", action)

        guess = _make_action(type="guess", utterance="Is it Einstein?", confidence=0.9)
        engine.process_answer(session_fr, "yes", guess)
        assert session_fr.guess_count == 1

    def test_state_after_question(self, engine, session_fr):
        self._start_and_answer(engine, session_fr)
        assert session_fr.state == GameState.LISTENING

    def test_state_after_end(self, engine, session_fr):
        engine.start_game(session_fr)
        action = _make_action(type="end", utterance="I give up")
        engine.process_answer(session_fr, "yes", action)
        assert session_fr.state == GameState.ENDED


class TestApplyRules:
    def _setup_session(self, engine, session, question_count=0):
        """Start game and simulate N questions."""
        engine.start_game(session)
        for i in range(question_count):
            action = _make_action(utterance=f"Question {i}?")
            engine.process_answer(session, "yes", action)

    def test_clamps_confidence(self, engine, session_fr):
        self._setup_session(engine, session_fr)
        action = _make_action(confidence=5.0)
        engine.process_answer(session_fr, "yes", action)
        # confidence should have been clamped, we check indirectly
        # by ensuring no crash and normal flow
        assert session_fr.state == GameState.LISTENING

    def test_blocks_early_guess(self, engine, session_fr):
        """Guess before min_questions_before_guess should be overridden to question."""
        self._setup_session(engine, session_fr, question_count=2)
        action = _make_action(type="guess", utterance="Is it X?")
        turn = engine.process_answer(session_fr, "yes", action)
        assert turn.sphinx_action_type == "question"
        assert session_fr.guess_count == 0

    def test_allows_guess_after_enough_questions(self, engine, session_fr):
        """Guess after min_questions_before_guess should be allowed."""
        self._setup_session(engine, session_fr, question_count=5)
        action = _make_action(type="guess", utterance="Est-ce Einstein ?", confidence=0.9)
        turn = engine.process_answer(session_fr, "yes", action)
        assert turn.sphinx_action_type == "guess"
        assert session_fr.guess_count == 1

    def test_auto_guess_on_high_confidence(self, engine, session_fr):
        """High confidence after enough questions should trigger auto-guess."""
        self._setup_session(engine, session_fr, question_count=5)
        action = _make_action(
            type="question",
            utterance="Hmm...",
            confidence=0.9,
            top_candidates=["Einstein"],
        )
        turn = engine.process_answer(session_fr, "yes", action)
        assert turn.sphinx_action_type == "guess"
        assert "Einstein" in turn.sphinx_utterance


class TestFallbackQuestion:
    def test_returns_from_list(self, engine, session_fr):
        q = engine.fallback_question(session_fr)
        assert q in FALLBACK_QUESTIONS["fr"]

    def test_cycles_through_questions(self, engine, session_fr):
        questions = set()
        for i in range(len(FALLBACK_QUESTIONS["fr"])):
            session_fr.question_count = i
            questions.add(engine.fallback_question(session_fr))
        assert len(questions) == len(FALLBACK_QUESTIONS["fr"])


class TestRecordGuessResult:
    def test_correct_guess_wins(self, engine, session_fr):
        engine.start_game(session_fr)
        engine.record_guess_result(session_fr, correct=True)
        assert session_fr.result == "win"
        assert session_fr.state == GameState.ENDED

    def test_incorrect_guess_no_change(self, engine, session_fr):
        engine.start_game(session_fr)
        engine.record_guess_result(session_fr, correct=False)
        assert session_fr.result is None
