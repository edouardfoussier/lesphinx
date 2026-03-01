"""Tests for the leaderboard store."""

import json
import tempfile
from pathlib import Path

import pytest

from lesphinx.store.leaderboard import GlobalStats, LeaderboardEntry, LeaderboardStore


@pytest.fixture
def tmp_path_store():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        p = Path(f.name)
    yield p
    p.unlink(missing_ok=True)


@pytest.fixture
def store(tmp_path_store) -> LeaderboardStore:
    return LeaderboardStore(path=tmp_path_store)


class TestSubmit:
    def test_submit_single_entry(self, store):
        entry = LeaderboardEntry(player_name="Alice", score=500)
        rank = store.submit(entry)
        assert rank == 1
        assert len(store.get_top()) == 1

    def test_entries_sorted_by_score_desc(self, store):
        store.submit(LeaderboardEntry(player_name="Low", score=100))
        store.submit(LeaderboardEntry(player_name="High", score=900))
        store.submit(LeaderboardEntry(player_name="Mid", score=500))
        top = store.get_top()
        scores = [e["score"] for e in top]
        assert scores == [900, 500, 100]

    def test_max_10_entries(self, store):
        for i in range(15):
            store.submit(LeaderboardEntry(player_name=f"P{i}", score=i * 100))
        assert len(store.get_top()) == 10

    def test_lowest_entry_evicted(self, store):
        for i in range(10):
            store.submit(LeaderboardEntry(player_name=f"P{i}", score=(i + 1) * 100))
        store.submit(LeaderboardEntry(player_name="NewHigh", score=5000))
        top = store.get_top()
        names = [e["player_name"] for e in top]
        assert "NewHigh" in names
        assert len(top) == 10


class TestQualifies:
    def test_qualifies_when_under_max(self, store):
        assert store.qualifies(0) is True

    def test_qualifies_when_above_lowest(self, store):
        for i in range(10):
            store.submit(LeaderboardEntry(player_name=f"P{i}", score=100))
        assert store.qualifies(200) is True

    def test_does_not_qualify_when_below_lowest(self, store):
        for i in range(10):
            store.submit(LeaderboardEntry(player_name=f"P{i}", score=100))
        assert store.qualifies(50) is False


class TestRecordGame:
    def test_total_games_incremented(self, store):
        store.record_game(won=False, questions=10)
        stats = store.get_stats()
        assert stats["total_games"] == 1

    def test_wins_counted(self, store):
        store.record_game(won=True, questions=5)
        stats = store.get_stats()
        assert stats["total_wins"] == 1

    def test_avg_questions_to_win(self, store):
        store.record_game(won=True, questions=4)
        store.record_game(won=True, questions=8)
        stats = store.get_stats()
        assert stats["avg_questions_to_win"] == 6.0

    def test_losses_dont_affect_avg(self, store):
        store.record_game(won=True, questions=10)
        store.record_game(won=False, questions=20)
        stats = store.get_stats()
        assert stats["avg_questions_to_win"] == 10.0


class TestPersistence:
    def test_survives_reload(self, tmp_path_store):
        store1 = LeaderboardStore(path=tmp_path_store)
        store1.submit(LeaderboardEntry(player_name="Persisted", score=999))
        store1.record_game(won=True, questions=7)

        store2 = LeaderboardStore(path=tmp_path_store)
        top = store2.get_top()
        assert len(top) == 1
        assert top[0]["player_name"] == "Persisted"
        stats = store2.get_stats()
        assert stats["total_games"] == 1

    def test_handles_missing_file(self):
        store = LeaderboardStore(path=Path("/tmp/nonexistent_leaderboard_test.json"))
        assert store.get_top() == []
        assert store.get_stats()["total_games"] == 0


class TestGlobalStats:
    def test_defaults(self):
        s = GlobalStats()
        assert s.total_games == 0
        assert s.total_wins == 0
        assert s.avg_questions_to_win == 0.0
