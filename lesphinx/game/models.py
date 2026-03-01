from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

from lesphinx.game.state import GameState


class Turn(BaseModel):
    turn_number: int
    player: int = 1
    player_text: str
    intent: Literal["question", "guess"]
    raw_answer: Literal["yes", "no", "unknown"] | None = None
    sphinx_utterance: str
    audio_id: str | None = None


class GameSession(BaseModel):
    session_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    language: Literal["fr", "en"] = "fr"
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    mode: Literal["solo", "multiplayer"] = "solo"
    num_players: int = 1
    current_player: int = 1
    state: GameState = GameState.IDLE
    secret_character_id: str = ""
    turns: list[Turn] = Field(default_factory=list)
    question_count: int = 0
    guess_count: int = 0
    player_guess_counts: dict[int, int] = Field(default_factory=lambda: {1: 0, 2: 0})
    player_results: dict[int, str | None] = Field(default_factory=lambda: {1: None, 2: None})
    hints_given: list[str] = Field(default_factory=list)
    pending_hint_offer: bool = False
    result: Literal["win", "lose"] | None = None
    score: int = 0
    current_streak: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def current_turn(self) -> int:
        return len(self.turns)


class NewGameRequest(BaseModel):
    language: Literal["fr", "en"] = "fr"
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    mode: Literal["solo", "multiplayer"] = "solo"
    themes: list[str] = Field(default_factory=list)


class AskRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=500)


class GuessRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)


class GameStateResponse(BaseModel):
    session_id: str
    state: GameState
    language: str
    difficulty: str
    mode: str = "solo"
    current_player: int = 1
    turns: list[Turn]
    question_count: int
    guess_count: int
    max_questions: int
    max_guesses: int
    player_guess_counts: dict[int, int] = Field(default_factory=lambda: {1: 0, 2: 0})
    player_results: dict[int, str | None] = Field(default_factory=lambda: {1: None, 2: None})
    result: str | None = None
    score: int = 0
    current_turn: int
    current_streak: int = 0
    sphinx_confidence: int = 100
    achievements: list[dict] = Field(default_factory=list)
    revealed_character: str | None = None
    revealed_image: str | None = None
    revealed_summary: str | None = None
