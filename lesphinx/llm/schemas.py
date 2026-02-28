from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class AttributeCheck(BaseModel):
    key: str
    value: str | bool


class ParsedQuestion(BaseModel):
    intent: Literal["question", "guess"] = "question"
    attribute_check: AttributeCheck | None = None
    fact_keywords: list[str] = Field(default_factory=list)
    guess_name: str | None = None


class SphinxUtterance(BaseModel):
    text: str
