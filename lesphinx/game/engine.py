"""Game engine for the reversed LeSphinx game."""

from __future__ import annotations

from lesphinx.config.settings import settings
from lesphinx.game.characters import Character, FactStore
from lesphinx.game.models import GameSession, Turn
from lesphinx.game.state import GameState, can_transition

INTRO_TEXT = {
    "fr": (
        "Je suis le Sphinx. Je pense a un personnage celebre... "
        "Pose-moi des questions pour decouvrir qui c'est. "
        "Je ne repondrai que par oui, non, ou je ne sais pas. "
        "A toi de jouer, mortel."
    ),
    "en": (
        "I am the Sphinx. I am thinking of a famous person... "
        "Ask me questions to discover who it is. "
        "I will only answer yes, no, or I don't know. "
        "Your move, mortal."
    ),
}

MULTI_INTRO_TEXT = {
    "fr": (
        "Bienvenue, mortels ! Deux challengers osent m'affronter... "
        "Posez vos questions a tour de role. "
        "Le premier a percer mon secret l'emporte !"
    ),
    "en": (
        "Welcome, mortals! Two challengers dare to face me... "
        "Take turns asking questions. "
        "The first to uncover my secret wins!"
    ),
}

VICTORY_TEXT = {
    "fr": "Tu m'as demaske, mortel ! Tu as perce mon secret... {name}. Le Sphinx s'incline.",
    "en": "You have unmasked me, mortal! You uncovered my secret... {name}. The Sphinx bows.",
}

DEFEAT_TEXT = {
    "fr": "Le temps est ecoule, mortel. Mon secret etait... {name}. Le Sphinx triomphe !",
    "en": "Time is up, mortal. My secret was... {name}. The Sphinx triumphs!",
}

WRONG_GUESS_TEXT = {
    "fr": "Non, mortel... ce n'est pas la bonne reponse. Continue a chercher.",
    "en": "No, mortal... that is not the right answer. Keep searching.",
}

MULTI_VICTORY_TEXT = {
    "fr": "Joueur {player} m'a demaske ! Mon secret etait... {name}. Bien joue, mortel.",
    "en": "Player {player} has unmasked me! My secret was... {name}. Well played, mortal.",
}

MULTI_DEFEAT_TEXT = {
    "fr": "Aucun de vous n'a perce mon secret ! C'etait... {name}. Le Sphinx triomphe !",
    "en": "Neither of you uncovered my secret! It was... {name}. The Sphinx triumphs!",
}

NO_MORE_GUESSES_TEXT = {
    "fr": "Non, mortel... Tu n'as plus de tentatives. Tu peux encore poser des questions.",
    "en": "No, mortal... You have no more guesses left. You may still ask questions.",
}

HINT_TEXT = {
    "fr": "Le Sphinx t'offre un indice : {hint}",
    "en": "The Sphinx offers you a hint: {hint}",
}


class GameEngine:
    """Server-side rules for the reversed guessing game."""

    def start_game(self, session: GameSession) -> Turn:
        self._transition(session, GameState.SPHINX_SPEAKING)
        if session.mode == "multiplayer":
            intro = MULTI_INTRO_TEXT[session.language]
        else:
            intro = INTRO_TEXT[session.language]
        turn = Turn(
            turn_number=session.current_turn,
            player_text="",
            intent="question",
            sphinx_utterance=intro,
        )
        session.turns.append(turn)
        self._transition(session, GameState.LISTENING)
        return turn

    def process_question(
        self,
        session: GameSession,
        player_text: str,
        raw_answer: str,
        sphinx_utterance: str,
    ) -> Turn:
        """Record a question turn with the resolved answer."""
        self._transition(session, GameState.THINKING)

        session.question_count += 1
        turn = Turn(
            turn_number=session.current_turn,
            player=session.current_player,
            player_text=player_text,
            intent="question",
            raw_answer=raw_answer,
            sphinx_utterance=sphinx_utterance,
        )
        session.turns.append(turn)

        if session.question_count >= settings.max_questions:
            self._end_game_loss(session)
        elif session.current_turn >= settings.hard_stop_turns:
            self._end_game_loss(session)
        else:
            if session.mode == "multiplayer":
                self._switch_player(session)
            self._transition(session, GameState.SPHINX_SPEAKING)
            self._transition(session, GameState.LISTENING)

        return turn

    def process_guess(
        self,
        session: GameSession,
        player_text: str,
        correct: bool,
        character: Character,
    ) -> Turn:
        """Record a guess turn."""
        self._transition(session, GameState.THINKING)

        player = session.current_player
        session.guess_count += 1
        session.player_guess_counts[player] = session.player_guess_counts.get(player, 0) + 1

        if correct:
            session.result = "win"
            session.player_results[player] = "win"
            if session.mode == "multiplayer":
                other = 3 - player
                session.player_results[other] = "lose"
                utterance = MULTI_VICTORY_TEXT[session.language].format(
                    player=player, name=character.name,
                )
            else:
                utterance = VICTORY_TEXT[session.language].format(name=character.name)
            turn = Turn(
                turn_number=session.current_turn,
                player=player,
                player_text=player_text,
                intent="guess",
                raw_answer="yes",
                sphinx_utterance=utterance,
            )
            session.turns.append(turn)
            self._transition(session, GameState.ENDED)
        else:
            utterance = WRONG_GUESS_TEXT[session.language]
            turn = Turn(
                turn_number=session.current_turn,
                player=player,
                player_text=player_text,
                intent="guess",
                raw_answer="no",
                sphinx_utterance=utterance,
            )
            session.turns.append(turn)

            if session.mode == "multiplayer":
                if self._all_players_out_of_guesses(session):
                    self._end_game_loss(session)
                else:
                    if not self.can_player_guess(session, player):
                        utterance_extra = NO_MORE_GUESSES_TEXT[session.language]
                        turn.sphinx_utterance += f" {utterance_extra}"
                    self._switch_player(session)
                    self._transition(session, GameState.SPHINX_SPEAKING)
                    self._transition(session, GameState.LISTENING)
            else:
                if session.guess_count >= settings.max_guesses:
                    session.result = "lose"
                    self._transition(session, GameState.ENDED)
                else:
                    self._transition(session, GameState.SPHINX_SPEAKING)
                    self._transition(session, GameState.LISTENING)

        return turn

    def should_give_hint(self, session: GameSession) -> bool:
        """Check if it's time for a free hint."""
        if session.question_count == 0:
            return False
        return (
            session.question_count % settings.hint_every_n_questions == 0
            and session.guess_count == 0
        )

    def generate_hint(self, fact_store: FactStore, session: GameSession) -> str | None:
        """Pick a random unused fact as a hint."""
        used = set(session.hints_given)
        available = [f for f in fact_store.character.facts if f not in used]
        if not available:
            return None
        import random
        hint = random.choice(available)
        session.hints_given.append(hint)
        return HINT_TEXT[session.language].format(hint=hint)

    def get_defeat_message(self, session: GameSession, character: Character) -> str:
        if session.mode == "multiplayer":
            return MULTI_DEFEAT_TEXT[session.language].format(name=character.name)
        return DEFEAT_TEXT[session.language].format(name=character.name)

    def can_player_guess(self, session: GameSession, player: int) -> bool:
        return session.player_guess_counts.get(player, 0) < settings.max_guesses

    def _switch_player(self, session: GameSession) -> None:
        if session.num_players < 2:
            return
        session.current_player = 3 - session.current_player

    def _all_players_out_of_guesses(self, session: GameSession) -> bool:
        for p in range(1, session.num_players + 1):
            if self.can_player_guess(session, p):
                return False
        return True

    def _end_game_loss(self, session: GameSession) -> None:
        self._transition(session, GameState.ENDED)
        session.result = "lose"
        if session.mode == "multiplayer":
            for p in range(1, session.num_players + 1):
                session.player_results[p] = "lose"

    def _transition(self, session: GameSession, target: GameState) -> None:
        if not can_transition(session.state, target):
            raise ValueError(f"Invalid transition: {session.state} -> {target}")
        session.state = target
