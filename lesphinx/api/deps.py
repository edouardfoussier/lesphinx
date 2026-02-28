"""Dependency injection for FastAPI routes."""

from __future__ import annotations

import logging
from pathlib import Path

from lesphinx.game.characters import SecretSelector, load_characters
from lesphinx.game.engine import GameEngine
from lesphinx.store.memory import InMemoryAudioBlobStore, InMemorySessionStore

logger = logging.getLogger(__name__)

session_store = InMemorySessionStore()
audio_store = InMemoryAudioBlobStore()
game_engine = GameEngine()

DATA_PATH = Path(__file__).parent.parent / "data" / "characters.json"

try:
    _characters = load_characters(DATA_PATH)
    secret_selector = SecretSelector(_characters)
    logger.info("Loaded %d characters", secret_selector.count)
except FileNotFoundError:
    logger.warning("characters.json not found -- run: python -m scripts.build_characters")
    secret_selector = SecretSelector([])
except Exception as e:
    logger.error("Failed to load characters: %s", e)
    secret_selector = SecretSelector([])
