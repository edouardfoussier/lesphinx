"""Dependency injection for FastAPI routes."""

from lesphinx.game.engine import GameEngine
from lesphinx.store.memory import InMemoryAudioBlobStore, InMemorySessionStore

# Singletons (in-memory, single process)
session_store = InMemorySessionStore()
audio_store = InMemoryAudioBlobStore()
game_engine = GameEngine()
