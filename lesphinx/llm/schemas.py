from typing import Literal

from pydantic import BaseModel, Field


class SphinxAction(BaseModel):
    type: Literal["question", "guess", "clarify", "end"]
    utterance: str
    confidence: float = 0.0
    top_candidates: list[str] = Field(default_factory=list)
    reasoning_brief: str = ""
