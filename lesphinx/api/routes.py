from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, HTTPException, Path
from fastapi.responses import Response

from lesphinx.api.deps import audio_store, game_engine, secret_selector, session_store
from lesphinx.config.settings import settings
from lesphinx.game.characters import AnswerResolver, Character, FactStore
from lesphinx.game.judge import check_guess
from lesphinx.game.models import (
    AskRequest,
    GameSession,
    GameStateResponse,
    GuessRequest,
    NewGameRequest,
)
from lesphinx.game.state import GameState
from lesphinx.llm.interpreter import QuestionInterpreter
from lesphinx.llm.voice import SphinxVoice
from lesphinx.logging import log_event
from lesphinx.tts.client import ElevenLabsTTSClient

logger = logging.getLogger(__name__)

router = APIRouter()

interpreter = QuestionInterpreter()
sphinx_voice = SphinxVoice()
tts_client = ElevenLabsTTSClient()

SESSION_ID_MAX_LEN = 32
AUDIO_ID_LEN = 12

# --- In-memory character lookup (keyed by character.id) ---
_characters_by_id: dict[str, Character] = {}


def _init_character_lookup() -> None:
    global _characters_by_id
    from lesphinx.api.deps import DATA_PATH
    from lesphinx.game.characters import load_characters
    try:
        chars = load_characters(DATA_PATH)
        _characters_by_id = {c.id: c for c in chars}
    except Exception:
        _characters_by_id = {}


_init_character_lookup()


def _get_character(char_id: str) -> Character:
    char = _characters_by_id.get(char_id)
    if not char:
        raise HTTPException(status_code=500, detail="Character data unavailable")
    return char


def _session_response(session: GameSession) -> GameStateResponse:
    revealed = None
    if session.state == GameState.ENDED:
        char = _characters_by_id.get(session.secret_character_id)
        revealed = char.name if char else None

    return GameStateResponse(
        session_id=session.session_id,
        state=session.state,
        language=session.language,
        difficulty=session.difficulty,
        turns=session.turns,
        question_count=session.question_count,
        guess_count=session.guess_count,
        max_questions=settings.max_questions,
        max_guesses=settings.max_guesses,
        result=session.result,
        current_turn=session.current_turn,
        revealed_character=revealed,
    )


def _get_session(session_id: str) -> GameSession:
    if len(session_id) > SESSION_ID_MAX_LEN:
        raise HTTPException(status_code=400, detail="Invalid session ID")
    session = session_store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


async def _generate_tts(text: str) -> str | None:
    try:
        audio_data = await tts_client.synthesize(text)
        audio_id = uuid.uuid4().hex[:AUDIO_ID_LEN]
        audio_store.put(audio_id, audio_data, "audio/mpeg")
        return audio_id
    except Exception as exc:
        logger.error("TTS failed: %s", exc)
        return None


@router.post("/game/new")
async def new_game(req: NewGameRequest) -> GameStateResponse:
    if secret_selector.count == 0:
        raise HTTPException(status_code=503, detail="No characters loaded")

    selected_themes = [t.strip().lower() for t in req.themes if t.strip()]
    character = secret_selector.pick(req.difficulty, themes=selected_themes or None)
    session = GameSession(
        language=req.language,
        difficulty=req.difficulty,
        secret_character_id=character.id,
    )
    turn = game_engine.start_game(session)

    audio_id = await _generate_tts(turn.sphinx_utterance)
    if audio_id:
        turn.audio_id = audio_id

    log_event("game_started", session.session_id,
              language=session.language, difficulty=session.difficulty,
              character=character.id, themes=selected_themes)
    session_store.save(session)
    return _session_response(session)


@router.post("/game/{session_id}/ask")
async def ask_question(session_id: str, req: AskRequest) -> GameStateResponse:
    session = _get_session(session_id)

    if session.state == GameState.ENDED:
        raise HTTPException(status_code=400, detail="Game has ended")
    if session.state != GameState.LISTENING:
        raise HTTPException(status_code=400, detail="Game is not ready for a question")

    character = _get_character(session.secret_character_id)
    fact_store = FactStore(character)

    # 1. Interpret the question
    parsed = await interpreter.interpret(req.text)

    # If the interpreter detects a guess, redirect to guess flow
    if parsed.intent == "guess" and parsed.guess_name:
        correct = check_guess(parsed.guess_name, character)
        turn = game_engine.process_guess(session, req.text, correct, character)

        if session.state == GameState.ENDED and session.result == "lose":
            defeat_msg = game_engine.get_defeat_message(session, character)
            turn.sphinx_utterance += f" {defeat_msg}"

        audio_id = await _generate_tts(turn.sphinx_utterance)
        if audio_id:
            turn.audio_id = audio_id
        log_event("guess_via_ask", session.session_id,
                  guess=parsed.guess_name, correct=correct)
        session_store.save(session)
        return _session_response(session)

    # 2. Resolve answer deterministically
    resolved = AnswerResolver.resolve(
        fact_store,
        attribute_check=parsed.attribute_check.model_dump() if parsed.attribute_check else None,
        fact_keywords=parsed.fact_keywords,
    )

    # 3. Generate Sphinx voice
    sphinx_text = await sphinx_voice.speak(
        answer=resolved.answer,
        language=session.language,
        question=req.text,
        matched_fact=resolved.matched_fact,
    )

    # 4. Record turn
    turn = game_engine.process_question(
        session, req.text, resolved.answer, sphinx_text,
    )

    # 5. Check for hint
    hint_text = None
    if game_engine.should_give_hint(session):
        hint_text = game_engine.generate_hint(fact_store, session)

    # 6. TTS
    full_text = sphinx_text
    if hint_text:
        full_text = f"{sphinx_text} {hint_text}"

    audio_id = await _generate_tts(full_text)
    if audio_id:
        turn.audio_id = audio_id
    if hint_text:
        turn.sphinx_utterance = full_text

    # If game just ended (max questions), add defeat message
    if session.state == GameState.ENDED and session.result == "lose":
        defeat_msg = game_engine.get_defeat_message(session, character)
        turn.sphinx_utterance += f" {defeat_msg}"
        audio_id = await _generate_tts(turn.sphinx_utterance)
        if audio_id:
            turn.audio_id = audio_id

    log_event("ask", session.session_id, text=req.text,
              answer=resolved.answer, source=resolved.source)
    session_store.save(session)
    return _session_response(session)


@router.post("/game/{session_id}/guess")
async def guess_character(session_id: str, req: GuessRequest) -> GameStateResponse:
    session = _get_session(session_id)

    if session.state == GameState.ENDED:
        raise HTTPException(status_code=400, detail="Game has ended")
    if session.state != GameState.LISTENING:
        raise HTTPException(status_code=400, detail="Game is not ready for a guess")

    character = _get_character(session.secret_character_id)
    correct = check_guess(req.name, character)

    turn = game_engine.process_guess(session, req.name, correct, character)

    # If game ended with loss (max guesses), append defeat message
    if session.state == GameState.ENDED and session.result == "lose":
        defeat_msg = game_engine.get_defeat_message(session, character)
        turn.sphinx_utterance += f" {defeat_msg}"

    audio_id = await _generate_tts(turn.sphinx_utterance)
    if audio_id:
        turn.audio_id = audio_id

    log_event("guess", session.session_id, name=req.name, correct=correct)
    session_store.save(session)
    return _session_response(session)


@router.get("/game/{session_id}/state")
async def get_state(session_id: str) -> GameStateResponse:
    session = _get_session(session_id)
    return _session_response(session)


@router.get("/audio/{audio_id}")
async def get_audio(audio_id: str = Path(..., max_length=AUDIO_ID_LEN + 4)) -> Response:
    blob = audio_store.get(audio_id)
    if not blob:
        raise HTTPException(status_code=404, detail="Audio not found")
    data, content_type = blob
    return Response(content=data, media_type=content_type)
