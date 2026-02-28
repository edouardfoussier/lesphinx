from __future__ import annotations

from lesphinx.config.settings import settings
from lesphinx.game.models import GameSession, Turn
from lesphinx.game.state import GameState, can_transition
from lesphinx.llm.schemas import SphinxAction


INTRO_TEXT = {
    "fr": (
        "Je suis le Sphinx. Pense a un personnage celebre... "
        "Je vais le deviner. Reponds par oui, non, ou je ne sais pas. "
        "Es-tu pret ?"
    ),
    "en": (
        "I am the Sphinx. Think of a famous person... "
        "I will guess who it is. Answer yes, no, or I don't know. "
        "Are you ready?"
    ),
}

FALLBACK_QUESTIONS = {
    "fr": [
        "Ce personnage est-il un homme ?",
        "Ce personnage est-il encore en vie ?",
        "Ce personnage est-il europeen ?",
        "Ce personnage est-il connu pour la musique ?",
        "Ce personnage est-il un acteur ?",
    ],
    "en": [
        "Is this person a man?",
        "Is this person still alive?",
        "Is this person European?",
        "Is this person known for music?",
        "Is this person an actor?",
    ],
}

END_TEXT = {
    "fr": "Le Sphinx s'incline... Tu as gagne cette fois. Qui etait-ce ?",
    "en": "The Sphinx bows... You win this time. Who was it?",
}

CONFIDENCE_MIN = 0.0
CONFIDENCE_MAX = 1.0


class GameEngine:
    """Server-side game rules. The LLM proposes actions, the engine validates/overrides."""

    def start_game(self, session: GameSession) -> Turn:
        self._transition(session, GameState.SPHINX_SPEAKING)
        intro = INTRO_TEXT[session.language]
        turn = Turn(
            turn_number=session.current_turn,
            sphinx_utterance=intro,
            sphinx_action_type="question",
        )
        session.turns.append(turn)
        self._transition(session, GameState.LISTENING)
        return turn

    def process_answer(
        self, session: GameSession, player_answer: str, sphinx_action: SphinxAction
    ) -> Turn:
        if session.turns:
            session.turns[-1].player_answer = player_answer

        self._transition(session, GameState.THINKING)

        action = self._apply_rules(session, sphinx_action)

        turn = Turn(
            turn_number=session.current_turn,
            sphinx_utterance=action.utterance,
            sphinx_action_type=action.type,
        )

        if action.type == "question":
            session.question_count += 1
        elif action.type == "guess":
            session.guess_count += 1

        session.turns.append(turn)

        if action.type == "end":
            self._transition(session, GameState.ENDED)
            if session.guess_count >= settings.max_guesses:
                session.result = "lose"
            else:
                session.result = "give_up"
        else:
            self._transition(session, GameState.SPHINX_SPEAKING)
            self._transition(session, GameState.LISTENING)

        return turn

    def record_guess_result(self, session: GameSession, correct: bool) -> None:
        if correct:
            session.result = "win"
            session.state = GameState.ENDED

    def fallback_question(self, session: GameSession) -> str:
        questions = FALLBACK_QUESTIONS[session.language]
        idx = session.question_count % len(questions)
        return questions[idx]

    def _apply_rules(self, session: GameSession, action: SphinxAction) -> SphinxAction:
        """Override the LLM's action if it violates game rules."""
        action.confidence = max(CONFIDENCE_MIN, min(CONFIDENCE_MAX, action.confidence))

        if session.current_turn >= settings.hard_stop_turns:
            action.type = "end"
            action.utterance = END_TEXT[session.language]
            return action

        if session.guess_count >= settings.max_guesses and action.type == "guess":
            action.type = "end"
            action.utterance = END_TEXT[session.language]
            return action

        if action.type == "guess" and session.question_count < settings.min_questions_before_guess:
            action.type = "question"
            action.utterance = self.fallback_question(session)
            return action

        if (
            action.type == "question"
            and action.confidence >= settings.auto_guess_confidence
            and session.question_count >= settings.min_questions_before_guess
            and session.guess_count < settings.max_guesses
            and action.top_candidates
        ):
            candidate = action.top_candidates[0]
            action.type = "guess"
            if session.language == "fr":
                action.utterance = f"Je pense que tu penses a... {candidate} !"
            else:
                action.utterance = f"I think you are thinking of... {candidate}!"

        if action.type == "question" and session.question_count >= settings.max_questions:
            if session.guess_count < settings.max_guesses and action.top_candidates:
                candidate = action.top_candidates[0]
                action.type = "guess"
                if session.language == "fr":
                    action.utterance = f"Le temps presse... Je pense que c'est {candidate} !"
                else:
                    action.utterance = f"Time is running out... I think it's {candidate}!"
            else:
                action.type = "end"
                action.utterance = END_TEXT[session.language]

        return action

    def _transition(self, session: GameSession, target: GameState) -> None:
        if not can_transition(session.state, target):
            raise ValueError(
                f"Invalid transition: {session.state} -> {target}"
            )
        session.state = target
