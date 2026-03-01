"""Tests for the reversed GameEngine."""

import pytest

from lesphinx.game.engine import GameEngine
from lesphinx.game.models import GameSession, Turn
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


class TestCalculateScore:
    def test_base_score_zero_questions(self, engine):
        s = GameSession(
            language="fr", difficulty="easy", secret_character_id="x",
            result="win", question_count=0, guess_count=1, state=GameState.ENDED,
        )
        assert engine.calculate_score(s) == 1000

    def test_questions_deduction(self, engine):
        s = GameSession(
            language="fr", difficulty="easy", secret_character_id="x",
            result="win", question_count=5, guess_count=1, state=GameState.ENDED,
        )
        assert engine.calculate_score(s) == 1000 - 5 * 40  # 800

    def test_wrong_guesses_deduction(self, engine):
        s = GameSession(
            language="fr", difficulty="easy", secret_character_id="x",
            result="win", question_count=0, guess_count=3, state=GameState.ENDED,
        )
        # 2 wrong guesses (3 total - 1 winning)
        assert engine.calculate_score(s) == 1000 - 2 * 100  # 800

    def test_hints_deduction(self, engine):
        s = GameSession(
            language="fr", difficulty="easy", secret_character_id="x",
            result="win", question_count=0, guess_count=1, state=GameState.ENDED,
            hints_given=["h1", "h2"],
        )
        assert engine.calculate_score(s) == 1000 - 2 * 50  # 900

    def test_difficulty_bonus_easy(self, engine):
        s = GameSession(
            language="fr", difficulty="easy", secret_character_id="x",
            result="win", question_count=10, guess_count=1, state=GameState.ENDED,
        )
        assert engine.calculate_score(s) == 1000 - 400 + 0  # 600

    def test_difficulty_bonus_medium(self, engine):
        s = GameSession(
            language="fr", difficulty="medium", secret_character_id="x",
            result="win", question_count=10, guess_count=1, state=GameState.ENDED,
        )
        assert engine.calculate_score(s) == 1000 - 400 + 200  # 800

    def test_difficulty_bonus_hard(self, engine):
        s = GameSession(
            language="fr", difficulty="hard", secret_character_id="x",
            result="win", question_count=10, guess_count=1, state=GameState.ENDED,
        )
        assert engine.calculate_score(s) == 1000 - 400 + 500  # 1100

    def test_score_never_below_zero(self, engine):
        s = GameSession(
            language="fr", difficulty="easy", secret_character_id="x",
            result="win", question_count=30, guess_count=5, state=GameState.ENDED,
            hints_given=["h1", "h2", "h3"],
        )
        assert engine.calculate_score(s) == 0

    def test_score_is_zero_for_loss(self, engine):
        s = GameSession(
            language="fr", difficulty="hard", secret_character_id="x",
            result="lose", question_count=5, guess_count=1, state=GameState.ENDED,
        )
        assert engine.calculate_score(s) == 0

    def test_score_is_zero_when_no_result(self, engine):
        s = GameSession(
            language="fr", difficulty="easy", secret_character_id="x",
        )
        assert engine.calculate_score(s) == 0

    def test_combined_deductions(self, engine):
        s = GameSession(
            language="fr", difficulty="medium", secret_character_id="x",
            result="win", question_count=8, guess_count=2, state=GameState.ENDED,
            hints_given=["h1"],
        )
        expected = 1000 - 8 * 40 - 1 * 100 - 1 * 50 + 200  # 730
        assert engine.calculate_score(s) == expected


class TestSphinxConfidence:
    def test_initial_confidence_is_100(self, engine):
        s = GameSession(
            language="fr", difficulty="easy", secret_character_id="x",
            question_count=0,
        )
        assert engine.get_sphinx_confidence(s) == 100

    def test_confidence_drops_with_yes_answers(self, engine):
        s = GameSession(
            language="fr", difficulty="easy", secret_character_id="x",
            question_count=5,
            turns=[
                Turn(turn_number=i, player_text=f"Q{i}?", intent="question",
                     raw_answer="yes", sphinx_utterance="Yes.")
                for i in range(5)
            ],
        )
        conf = engine.get_sphinx_confidence(s)
        assert conf < 100

    def test_confidence_higher_with_no_answers(self, engine):
        yes_session = GameSession(
            language="fr", difficulty="easy", secret_character_id="x",
            question_count=5,
            turns=[
                Turn(turn_number=i, player_text=f"Q{i}?", intent="question",
                     raw_answer="yes", sphinx_utterance="Yes.")
                for i in range(5)
            ],
        )
        no_session = GameSession(
            language="fr", difficulty="easy", secret_character_id="x",
            question_count=5,
            turns=[
                Turn(turn_number=i, player_text=f"Q{i}?", intent="question",
                     raw_answer="no", sphinx_utterance="No.")
                for i in range(5)
            ],
        )
        assert engine.get_sphinx_confidence(no_session) > engine.get_sphinx_confidence(yes_session)

    def test_confidence_in_valid_range(self, engine):
        s = GameSession(
            language="fr", difficulty="easy", secret_character_id="x",
            question_count=20,
            turns=[
                Turn(turn_number=i, player_text=f"Q{i}?", intent="question",
                     raw_answer="yes", sphinx_utterance="Yes.")
                for i in range(20)
            ],
        )
        conf = engine.get_sphinx_confidence(s)
        assert 0 <= conf <= 100

    def test_confidence_bounded_at_zero(self, engine):
        s = GameSession(
            language="fr", difficulty="easy", secret_character_id="x",
            question_count=50,
            turns=[
                Turn(turn_number=i, player_text=f"Q{i}?", intent="question",
                     raw_answer="yes", sphinx_utterance="Yes.")
                for i in range(50)
            ],
        )
        assert engine.get_sphinx_confidence(s) >= 0
