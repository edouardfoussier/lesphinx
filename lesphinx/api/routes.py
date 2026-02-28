from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, HTTPException, Path
from fastapi.responses import Response

from lesphinx.api.deps import audio_store, game_engine, session_store
from lesphinx.logging import log_event
from lesphinx.game.models import (
    GameSession,
    GameStateResponse,
    NewGameRequest,
    TextAnswerRequest,
)
from lesphinx.game.state import GameState
from lesphinx.llm.client import MistralLLMClient
from lesphinx.llm.schemas import SphinxAction
from lesphinx.tts.client import ElevenLabsTTSClient

logger = logging.getLogger(__name__)

router = APIRouter()

llm_client = MistralLLMClient()
tts_client = ElevenLabsTTSClient()

SESSION_ID_MAX_LEN = 32
AUDIO_ID_LEN = 12


def _session_response(session: GameSession) -> GameStateResponse:
    return GameStateResponse(
        session_id=session.session_id,
        state=session.state,
        language=session.language,
        turns=session.turns,
        question_count=session.question_count,
        guess_count=session.guess_count,
        result=session.result,
        current_turn=session.current_turn,
    )


def _get_session(session_id: str) -> GameSession:
    if len(session_id) > SESSION_ID_MAX_LEN:
        raise HTTPException(status_code=400, detail="Invalid session ID")
    session = session_store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


async def _generate_tts(text: str, session: GameSession) -> str | None:
    """Generate TTS audio and store it. Returns audio_id or None on failure."""
    try:
        audio_data = await tts_client.synthesize(text)
        audio_id = uuid.uuid4().hex[:AUDIO_ID_LEN]
        audio_store.put(audio_id, audio_data, "audio/mpeg")
        return audio_id
    except Exception as exc:
        logger.error("TTS failed for session %s: %s", session.session_id, exc)
        return None


@router.post("/game/new")
async def new_game(req: NewGameRequest) -> GameStateResponse:
    session = GameSession(language=req.language)
    turn = game_engine.start_game(session)

    audio_id = await _generate_tts(turn.sphinx_utterance, session)
    if audio_id:
        turn.audio_id = audio_id

    log_event("game_started", session.session_id, language=session.language)
    session_store.save(session)
    return _session_response(session)


@router.get("/game/{session_id}/state")
async def get_state(session_id: str) -> GameStateResponse:
    session = _get_session(session_id)
    return _session_response(session)


@router.post("/game/{session_id}/answer_text")
async def answer_text(session_id: str, req: TextAnswerRequest) -> GameStateResponse:
    session = _get_session(session_id)

    if session.state == GameState.ENDED:
        raise HTTPException(status_code=400, detail="Game has ended")

    if session.state != GameState.LISTENING:
        raise HTTPException(status_code=400, detail="Game is not ready for an answer")

    try:
        sphinx_action = await llm_client.get_action(session, req.answer)
        logger.info("LLM OK type=%s confidence=%.2f", sphinx_action.type, sphinx_action.confidence)
    except Exception as exc:
        logger.error("LLM failed for session %s: %s", session.session_id, exc)
        sphinx_action = SphinxAction(
            type="question",
            utterance=game_engine.fallback_question(session),
            confidence=0.0,
            top_candidates=[],
            reasoning_brief="LLM fallback",
        )

    turn = game_engine.process_answer(session, req.answer, sphinx_action)

    audio_id = await _generate_tts(turn.sphinx_utterance, session)
    if audio_id:
        turn.audio_id = audio_id

    log_event("turn_text", session.session_id, answer=req.answer, action_type=turn.sphinx_action_type)
    session_store.save(session)
    return _session_response(session)


@router.get("/audio/{audio_id}")
async def get_audio(audio_id: str = Path(..., max_length=AUDIO_ID_LEN + 4)) -> Response:
    blob = audio_store.get(audio_id)
    if not blob:
        raise HTTPException(status_code=404, detail="Audio not found")
    data, content_type = blob
    return Response(content=data, media_type=content_type)
