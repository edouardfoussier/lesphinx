from __future__ import annotations

import time
from collections import OrderedDict

from lesphinx.game.models import GameSession

SESSION_TTL = 7200  # 2 hours
AUDIO_MAX_ENTRIES = 500


class InMemorySessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, GameSession] = {}
        self._last_purge: float = time.time()

    def get(self, session_id: str) -> GameSession | None:
        self._maybe_purge()
        return self._sessions.get(session_id)

    def save(self, session: GameSession) -> None:
        self._sessions[session.session_id] = session

    def delete(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def _maybe_purge(self) -> None:
        now = time.time()
        if now - self._last_purge < 300:
            return
        self._last_purge = now
        cutoff = now - SESSION_TTL
        stale = [
            sid for sid, s in self._sessions.items()
            if s.created_at.timestamp() < cutoff
        ]
        for sid in stale:
            del self._sessions[sid]


class InMemoryAudioBlobStore:
    def __init__(self) -> None:
        self._blobs: OrderedDict[str, tuple[bytes, str]] = OrderedDict()

    def put(self, audio_id: str, data: bytes, content_type: str = "audio/mpeg") -> None:
        self._blobs[audio_id] = (data, content_type)
        while len(self._blobs) > AUDIO_MAX_ENTRIES:
            self._blobs.popitem(last=False)

    def get(self, audio_id: str) -> tuple[bytes, str] | None:
        return self._blobs.get(audio_id)
