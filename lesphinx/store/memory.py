from lesphinx.game.models import GameSession


class InMemorySessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, GameSession] = {}

    def get(self, session_id: str) -> GameSession | None:
        return self._sessions.get(session_id)

    def save(self, session: GameSession) -> None:
        self._sessions[session.session_id] = session

    def delete(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)


class InMemoryAudioBlobStore:
    def __init__(self) -> None:
        self._blobs: dict[str, tuple[bytes, str]] = {}

    def put(self, audio_id: str, data: bytes, content_type: str = "audio/mpeg") -> None:
        self._blobs[audio_id] = (data, content_type)

    def get(self, audio_id: str) -> tuple[bytes, str] | None:
        return self._blobs.get(audio_id)
