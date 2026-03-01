"""Leaderboard and global stats management."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

DATA_FILE = Path(__file__).resolve().parent.parent.parent / "lesphinx" / "data" / "leaderboard.json"


class LeaderboardEntry(BaseModel):
    player_name: str = "Anonymous"
    score: int = 0
    difficulty: str = "medium"
    character_name: str = ""
    questions_count: int = 0
    hints_used: int = 0
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class GlobalStats(BaseModel):
    total_games: int = 0
    total_wins: int = 0
    avg_questions_to_win: float = 0.0


class LeaderboardStore:
    MAX_ENTRIES = 10

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or DATA_FILE
        self._entries: list[LeaderboardEntry] = []
        self._stats = GlobalStats()
        self._win_question_counts: list[int] = []
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text())
            self._entries = [LeaderboardEntry(**e) for e in data.get("entries", [])]
            if "stats" in data:
                self._stats = GlobalStats(**data["stats"])
            self._win_question_counts = data.get("win_question_counts", [])
        except Exception as exc:
            logger.warning("Failed to load leaderboard: %s", exc)

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "entries": [e.model_dump() for e in self._entries],
                "stats": self._stats.model_dump(),
                "win_question_counts": self._win_question_counts,
            }
            self._path.write_text(json.dumps(data, indent=2))
        except Exception as exc:
            logger.warning("Failed to save leaderboard: %s", exc)

    def get_top(self, limit: int = 10) -> list[dict]:
        return [e.model_dump() for e in self._entries[:limit]]

    def get_stats(self) -> dict:
        return self._stats.model_dump()

    def qualifies(self, score: int) -> bool:
        if len(self._entries) < self.MAX_ENTRIES:
            return True
        return score > self._entries[-1].score

    def submit(self, entry: LeaderboardEntry) -> int | None:
        self._entries.append(entry)
        self._entries.sort(key=lambda e: e.score, reverse=True)
        self._entries = self._entries[:self.MAX_ENTRIES]
        self._save()
        try:
            rank = next(i + 1 for i, e in enumerate(self._entries) if e is entry)
            return rank
        except StopIteration:
            return None

    def record_game(self, won: bool, questions: int) -> None:
        self._stats.total_games += 1
        if won:
            self._stats.total_wins += 1
            self._win_question_counts.append(questions)
            if self._win_question_counts:
                self._stats.avg_questions_to_win = round(
                    sum(self._win_question_counts) / len(self._win_question_counts), 1
                )
        self._save()


leaderboard_store = LeaderboardStore()
