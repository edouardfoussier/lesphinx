from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

from lesphinx.game.state import GameState


class Turn(BaseModel):
    turn_number: int
    sphinx_utterance: str
    sphinx_action_type: Literal["question", "guess", "clarify", "end"]
    player_answer: str | None = None
    audio_id: str | None = None  # TTS audio blob id


class GameSession(BaseModel):
    session_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    language: Literal["fr", "en"] = "fr"
    state: GameState = GameState.IDLE
    turns: list[Turn] = Field(default_factory=list)
    question_count: int = 0
    guess_count: int = 0
    result: Literal["win", "lose", "give_up"] | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def current_turn(self) -> int:
        return len(self.turns)


class NewGameRequest(BaseModel):
    language: Literal["fr", "en"] = "fr"


class TextAnswerRequest(BaseModel):
    answer: Literal["yes", "no", "unknown"]


class GameStateResponse(BaseModel):
    session_id: str
    state: GameState
    language: str
    turns: list[Turn]
    question_count: int
    guess_count: int
    result: str | None = None
    current_turn: int
