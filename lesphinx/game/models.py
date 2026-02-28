from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

from lesphinx.game.state import GameState


class Turn(BaseModel):
    turn_number: int
    player_text: str
    intent: Literal["question", "guess"]
    raw_answer: Literal["yes", "no", "unknown"] | None = None
    sphinx_utterance: str
    audio_id: str | None = None


class GameSession(BaseModel):
    session_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    language: Literal["fr", "en"] = "fr"
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    state: GameState = GameState.IDLE
    secret_character_id: str = ""
    turns: list[Turn] = Field(default_factory=list)
    question_count: int = 0
    guess_count: int = 0
    hints_given: list[str] = Field(default_factory=list)
    result: Literal["win", "lose"] | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def current_turn(self) -> int:
        return len(self.turns)


class NewGameRequest(BaseModel):
    language: Literal["fr", "en"] = "fr"
    difficulty: Literal["easy", "medium", "hard"] = "medium"
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
    turns: list[Turn]
    question_count: int
    guess_count: int
    max_questions: int
    max_guesses: int
    result: str | None = None
    current_turn: int
    revealed_character: str | None = None
