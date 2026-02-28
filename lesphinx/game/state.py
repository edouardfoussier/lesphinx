from enum import Enum


class GameState(str, Enum):
    IDLE = "idle"
    SPHINX_SPEAKING = "sphinx_speaking"
    LISTENING = "listening"
    THINKING = "thinking"
    ENDED = "ended"


# Valid transitions: current_state -> set of allowed next states
TRANSITIONS: dict[GameState, set[GameState]] = {
    GameState.IDLE: {GameState.SPHINX_SPEAKING},
    GameState.SPHINX_SPEAKING: {GameState.LISTENING, GameState.ENDED},
    GameState.LISTENING: {GameState.THINKING},
    GameState.THINKING: {GameState.SPHINX_SPEAKING, GameState.ENDED},
    GameState.ENDED: set(),
}


def can_transition(current: GameState, target: GameState) -> bool:
    return target in TRANSITIONS.get(current, set())
