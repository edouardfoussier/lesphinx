"""WebSocket handler for real-time voice interaction.

Endpoint: ws://host/game/{session_id}/voice

Two modes:

  "streaming" (default, deterministic):
    Browser STT → text over WS → game logic → SphinxVoice → ElevenLabs
    streaming TTS → audio chunks back over WS.

  "personaplex" (experimental):
    Raw audio over WS → fal.ai PersonaPlex → audio + text back over WS.
    Persona prompt embeds character facts for approximate determinism.
    Game state is tracked but answers are LLM-generated.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import uuid

from fastapi import WebSocket, WebSocketDisconnect

from lesphinx.api.deps import audio_store, game_engine, session_store
from lesphinx.config.settings import settings
from lesphinx.game.characters import AnswerResolver, Character, FactStore
from lesphinx.game.judge import check_guess
from lesphinx.game.models import GameSession
from lesphinx.game.state import GameState
from lesphinx.llm.interpreter import QuestionInterpreter
from lesphinx.llm.voice import SphinxVoice
from lesphinx.logging import log_event
from lesphinx.voice_agent import streaming as el_streaming

logger = logging.getLogger(__name__)

interpreter = QuestionInterpreter()
sphinx_voice = SphinxVoice()

_characters_by_id: dict[str, Character] = {}


def _ensure_characters() -> None:
    global _characters_by_id
    if _characters_by_id:
        return
    from lesphinx.api.deps import DATA_PATH
    from lesphinx.game.characters import load_characters
    try:
        _characters_by_id = {c.id: c for c in load_characters(DATA_PATH)}
    except Exception:
        pass


async def _send_json(ws: WebSocket, data: dict) -> None:
    try:
        await ws.send_text(json.dumps(data))
    except Exception:
        pass


def _build_state_payload(session: GameSession) -> dict:
    revealed = None
    if session.state == GameState.ENDED:
        char = _characters_by_id.get(session.secret_character_id)
        if char:
            revealed = char.name
    return {
        "type": "state",
        "session_id": session.session_id,
        "state": session.state.value,
        "question_count": session.question_count,
        "guess_count": session.guess_count,
        "max_questions": settings.max_questions,
        "max_guesses": settings.max_guesses,
        "result": session.result,
        "current_turn": session.current_turn,
        "revealed_character": revealed,
    }


async def handle_voice_ws(ws: WebSocket, session_id: str) -> None:
    """Main WebSocket handler dispatching to the configured mode."""
    await ws.accept()
    _ensure_characters()

    session = session_store.get(session_id)
    if not session:
        await _send_json(ws, {"type": "error", "message": "Session not found"})
        await ws.close()
        return

    mode = "streaming"

    await _send_json(ws, {
        "type": "connected",
        "mode": mode,
        "session_id": session_id,
    })

    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await _send_json(ws, {"type": "error", "message": "Invalid JSON"})
                continue

            msg_type = msg.get("type", "")

            if msg_type == "config":
                requested_mode = msg.get("mode", "streaming")
                if requested_mode == "personaplex" and settings.fal_api_key:
                    mode = "personaplex"
                else:
                    mode = "streaming"
                await _send_json(ws, {"type": "mode_set", "mode": mode})

            elif msg_type == "text":
                if mode == "streaming":
                    await _handle_streaming_text(ws, session, msg.get("text", ""))
                else:
                    await _handle_personaplex_text(ws, session, msg.get("text", ""))

            elif msg_type == "guess":
                await _handle_guess(ws, session, msg.get("name", ""))

            elif msg_type == "audio" and mode == "personaplex":
                await _handle_personaplex_audio(ws, session, msg.get("audio", ""))

            elif msg_type == "ping":
                await _send_json(ws, {"type": "pong"})

            else:
                await _send_json(ws, {"type": "error", "message": f"Unknown type: {msg_type}"})

    except WebSocketDisconnect:
        logger.info("Voice WS disconnected: %s", session_id)
    except Exception as exc:
        logger.error("Voice WS error: %s", exc)
        await _send_json(ws, {"type": "error", "message": str(exc)})


async def _handle_streaming_text(ws: WebSocket, session: GameSession, text: str) -> None:
    """Process a text question through the deterministic pipeline with streaming TTS."""
    if not text.strip():
        await _send_json(ws, {"type": "error", "message": "Empty text"})
        return

    if session.state == GameState.ENDED:
        await _send_json(ws, {"type": "error", "message": "Game has ended"})
        return
    if session.state != GameState.LISTENING:
        await _send_json(ws, {"type": "error", "message": "Not ready for questions"})
        return

    char = _characters_by_id.get(session.secret_character_id)
    if not char:
        await _send_json(ws, {"type": "error", "message": "Character unavailable"})
        return

    fact_store = FactStore(char)

    parsed = await interpreter.interpret(text)

    if parsed.intent == "guess" and parsed.guess_name:
        await _handle_guess(ws, session, parsed.guess_name)
        return

    resolved = AnswerResolver.resolve(
        fact_store,
        attribute_check=parsed.attribute_check.model_dump() if parsed.attribute_check else None,
        fact_keywords=parsed.fact_keywords,
    )

    sphinx_text = await sphinx_voice.speak(
        answer=resolved.answer,
        language=session.language,
        question=text,
        matched_fact=resolved.matched_fact,
    )

    turn = game_engine.process_question(session, text, resolved.answer, sphinx_text)

    await _send_json(ws, {"type": "sphinx_text", "text": sphinx_text})

    if settings.voice_agent_streaming_tts:
        audio_chunks: list[bytes] = []
        async for chunk in el_streaming.stream_tts(sphinx_text):
            audio_chunks.append(chunk)
            chunk_b64 = base64.b64encode(chunk).decode("ascii")
            await _send_json(ws, {"type": "audio_chunk", "audio": chunk_b64, "format": "mp3"})
        await _send_json(ws, {"type": "audio_end"})

        if audio_chunks:
            full_audio = b"".join(audio_chunks)
            audio_id = uuid.uuid4().hex[:12]
            audio_store.put(audio_id, full_audio, "audio/mpeg")
            turn.audio_id = audio_id
    else:
        from lesphinx.tts.client import ElevenLabsTTSClient
        tts = ElevenLabsTTSClient()
        try:
            audio_data = await tts.synthesize(sphinx_text)
            audio_id = uuid.uuid4().hex[:12]
            audio_store.put(audio_id, audio_data, "audio/mpeg")
            turn.audio_id = audio_id
            chunk_b64 = base64.b64encode(audio_data).decode("ascii")
            await _send_json(ws, {"type": "audio_chunk", "audio": chunk_b64, "format": "mp3"})
            await _send_json(ws, {"type": "audio_end"})
        except Exception as exc:
            logger.error("TTS failed: %s", exc)

    log_event("ask_ws", session.session_id, text=text,
              answer=resolved.answer, source=resolved.source)
    session_store.save(session)
    await _send_json(ws, _build_state_payload(session))


async def _handle_guess(ws: WebSocket, session: GameSession, name: str) -> None:
    """Process a guess through the deterministic pipeline."""
    if not name.strip():
        await _send_json(ws, {"type": "error", "message": "Empty guess"})
        return

    if session.state == GameState.ENDED:
        await _send_json(ws, {"type": "error", "message": "Game has ended"})
        return
    if session.state != GameState.LISTENING:
        await _send_json(ws, {"type": "error", "message": "Not ready for guesses"})
        return

    char = _characters_by_id.get(session.secret_character_id)
    if not char:
        await _send_json(ws, {"type": "error", "message": "Character unavailable"})
        return

    correct = check_guess(name, char)
    turn = game_engine.process_guess(session, name, correct, char)

    if session.state == GameState.ENDED and session.result == "lose":
        defeat_msg = game_engine.get_defeat_message(session, char)
        turn.sphinx_utterance += f" {defeat_msg}"

    await _send_json(ws, {"type": "sphinx_text", "text": turn.sphinx_utterance})

    from lesphinx.tts.client import ElevenLabsTTSClient
    tts = ElevenLabsTTSClient()
    try:
        audio_data = await tts.synthesize(turn.sphinx_utterance)
        audio_id = uuid.uuid4().hex[:12]
        audio_store.put(audio_id, audio_data, "audio/mpeg")
        turn.audio_id = audio_id
        chunk_b64 = base64.b64encode(audio_data).decode("ascii")
        await _send_json(ws, {"type": "audio_chunk", "audio": chunk_b64, "format": "mp3"})
        await _send_json(ws, {"type": "audio_end"})
    except Exception as exc:
        logger.error("TTS failed: %s", exc)

    log_event("guess_ws", session.session_id, name=name, correct=correct)
    session_store.save(session)
    await _send_json(ws, _build_state_payload(session))


async def _handle_personaplex_text(ws: WebSocket, session: GameSession, text: str) -> None:
    """In PersonaPlex mode, text input is still processed through game logic
    for state tracking, then PersonaPlex generates the theatrical voice."""
    await _handle_streaming_text(ws, session, text)


async def _handle_personaplex_audio(ws: WebSocket, session: GameSession, audio_b64: str) -> None:
    """Forward raw audio to PersonaPlex for full-duplex voice processing.

    The PersonaPlex persona prompt constrains responses to match character facts.
    Game state is updated based on extracted answer signals from the response text.
    """
    from lesphinx.voice_agent.client import PersonaPlexSession, extract_answer_signal
    from lesphinx.voice_agent.persona import build_persona_prompt

    char = _characters_by_id.get(session.secret_character_id)
    if not char:
        await _send_json(ws, {"type": "error", "message": "Character unavailable"})
        return

    if session.state == GameState.ENDED:
        await _send_json(ws, {"type": "error", "message": "Game has ended"})
        return

    persona_prompt = build_persona_prompt(char, session.language)
    pp_session = PersonaPlexSession(
        persona_prompt=persona_prompt,
        voice=settings.personaplex_voice,
    )

    try:
        await pp_session.connect()
        audio_bytes = base64.b64decode(audio_b64)
        await pp_session.send_audio(audio_bytes)

        collected_text = ""
        async for response in pp_session.receive_responses():
            if response.audio:
                resp_b64 = base64.b64encode(response.audio).decode("ascii")
                await _send_json(ws, {
                    "type": "audio_chunk",
                    "audio": resp_b64,
                    "format": "pcm_24k",
                })
            if response.text:
                collected_text += response.text

        await _send_json(ws, {"type": "audio_end"})

        if collected_text:
            await _send_json(ws, {"type": "sphinx_text", "text": collected_text})
            answer_signal = extract_answer_signal(collected_text)
            if answer_signal and session.state == GameState.LISTENING:
                game_engine.process_question(
                    session, "(audio)", answer_signal, collected_text,
                )
                session_store.save(session)

        await _send_json(ws, _build_state_payload(session))
    except Exception as exc:
        logger.error("PersonaPlex audio error: %s", exc)
        await _send_json(ws, {"type": "error", "message": f"PersonaPlex error: {exc}"})
    finally:
        await pp_session.disconnect()
