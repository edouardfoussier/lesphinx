from __future__ import annotations

import logging
import random
import uuid

from fastapi import APIRouter, HTTPException, Path
from fastapi.responses import Response

from lesphinx.api.deps import audio_store, game_engine, secret_selector, session_store
from lesphinx.config.settings import settings
from lesphinx.game.characters import AnswerResolver, Character, FactStore, ResolvedAnswer
from lesphinx.game.judge import check_guess
from lesphinx.game.models import (
    AskRequest,
    GameSession,
    GameStateResponse,
    GuessRequest,
    NewGameRequest,
)
from lesphinx.game.state import GameState
from lesphinx.llm.fallback_resolver import LLMFallbackResolver
from lesphinx.llm.interpreter import QuestionInterpreter
from lesphinx.llm.voice import SphinxVoice
from lesphinx.logging import log_event
from lesphinx.tts.client import ElevenLabsTTSClient

logger = logging.getLogger(__name__)

router = APIRouter()

interpreter = QuestionInterpreter()
sphinx_voice = SphinxVoice()
tts_client = ElevenLabsTTSClient()
fallback_resolver = LLMFallbackResolver()

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

EASTER_EGG_RESPONSES = {
    "sphinx_identity": {
        "fr": "Hahaha ! Le Sphinx ? Je suis bien trop ancien et trop majestueux pour figurer dans une simple base de donnees, mortel !",
        "en": "Hahaha! The Sphinx? I am far too ancient and majestic to appear in a mere database, mortal!",
    },
    "knows_answer": {
        "fr": "Evidemment que je connais la reponse, mortel. Je sais TOUT. C'est toi qui cherches, pas moi.",
        "en": "Of course I know the answer, mortal. I know EVERYTHING. It is you who searches, not I.",
    },
    "cheating": {
        "fr": "Tricher ? MOI ? Le Sphinx est au-dessus de tels artifices ! C'est toi qui manques de perspicacite...",
        "en": "Cheat? ME? The Sphinx is above such trickery! It is you who lacks insight...",
    },
    "love": {
        "fr": "L'amour ? Le Sphinx ne connait que les enigmes et le sable, mortel. Revenons a nos questions.",
        "en": "Love? The Sphinx knows only riddles and sand, mortal. Back to our questions.",
    },
}


def _get_easter_egg_response(egg_id: str, language: str) -> str:
    responses = EASTER_EGG_RESPONSES.get(egg_id, {})
    return responses.get(language, responses.get("en", "..."))


SLIP_TEMPLATES = {
    "continent": {
        "fr": "Les vents de {value} portent cette verite...",
        "en": "The winds of {value} carry this truth...",
    },
    "era": {
        "fr": "Les echos d'une epoque {value} resonnent...",
        "en": "Echoes of a {value} era resonate...",
    },
    "field": {
        "fr": "Le monde de {value} murmure en ta faveur...",
        "en": "The world of {value} whispers in your favor...",
    },
}


def _generate_slip(character: Character, session: GameSession) -> str | None:
    """Generate a subtle micro-clue the Sphinx 'accidentally' reveals."""
    attrs = character.attributes
    used_slip_keys = set()
    for t in session.turns:
        for key in ("continent", "era", "field"):
            if key in t.sphinx_utterance.lower():
                used_slip_keys.add(key)

    candidates = []
    for key in ("continent", "era", "field"):
        if key in used_slip_keys:
            continue
        val = attrs.get(key)
        if val and isinstance(val, str) and val != "unknown":
            candidates.append((key, val))

    if not candidates:
        return None

    key, value = random.choice(candidates)
    templates = SLIP_TEMPLATES.get(key, {})
    tmpl = templates.get(session.language, templates.get("en"))
    if tmpl:
        return tmpl.format(value=value)
    return None


def _finalize_game(session: GameSession) -> None:
    """Calculate score and record stats exactly once when a game ends."""
    if getattr(session, '_finalized', False):
        return
    if session.result == "win" and session.score == 0:
        session.score = game_engine.calculate_score(session)
    from lesphinx.store.leaderboard import leaderboard_store
    leaderboard_store.record_game(session.result == "win", session.question_count)
    session._finalized = True  # type: ignore[attr-defined]


def _get_character(char_id: str) -> Character:
    char = _characters_by_id.get(char_id)
    if not char:
        raise HTTPException(status_code=500, detail="Character data unavailable")
    return char


def _session_response(session: GameSession) -> GameStateResponse:
    revealed = None
    revealed_image = None
    revealed_summary = None
    achievements = []

    if session.state == GameState.ENDED:
        char = _characters_by_id.get(session.secret_character_id)
        if char:
            revealed = char.name
            if char.image and char.image.get("local_path"):
                revealed_image = char.image["local_path"]
            if char.summary:
                revealed_summary = char.summary.get(session.language, char.summary.get("en"))
        from lesphinx.game.achievements import check_achievements
        achievements = check_achievements(session)

    return GameStateResponse(
        session_id=session.session_id,
        state=session.state,
        language=session.language,
        difficulty=session.difficulty,
        mode=session.mode,
        current_player=session.current_player,
        turns=session.turns,
        question_count=session.question_count,
        guess_count=session.guess_count,
        max_questions=settings.max_questions,
        max_guesses=settings.max_guesses,
        player_guess_counts=session.player_guess_counts,
        player_results=session.player_results,
        result=session.result,
        score=session.score,
        current_turn=session.current_turn,
        current_streak=session.current_streak,
        sphinx_confidence=game_engine.get_sphinx_confidence(session),
        achievements=achievements,
        revealed_character=revealed,
        revealed_image=revealed_image,
        revealed_summary=revealed_summary,
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
        mode=req.mode,
        num_players=2 if req.mode == "multiplayer" else 1,
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

    # 0a. Check if player is accepting a pending hint offer ("oui"/"yes" after Sphinx asked)
    _HINT_ACCEPT = {"oui", "yes", "ok", "d'accord", "daccord", "bien sur", "vas-y", "go", "go ahead", "allez", "yeah", "yep", "ouais"}
    if session.pending_hint_offer:
        session.pending_hint_offer = False
        if req.text.strip().lower().rstrip("!.") in _HINT_ACCEPT:
            if len(session.hints_given) < settings.max_hints:
                hint_text = game_engine.generate_hint(fact_store, session)
                if hint_text:
                    flavor = {"fr": "Tres bien, voici un indice...", "en": "Very well, here is a hint..."}.get(session.language, "Here's a hint...")
                    hint_response = f"{flavor} {hint_text}"
                    turn = game_engine.process_question(session, req.text, "unknown", hint_response)
                    audio_id = await _generate_tts(hint_response)
                    if audio_id:
                        turn.audio_id = audio_id
                    session_store.save(session)
                    return _session_response(session)

    # 0b. Check for easter eggs
    from lesphinx.llm.interpreter import check_easter_egg
    egg = check_easter_egg(req.text)
    if egg:
        if egg == "wants_hint" and len(session.hints_given) < settings.max_hints:
            hint_text = game_engine.generate_hint(fact_store, session)
            if hint_text:
                flavor = session.language == "fr" \
                    and "Tu donnes ta langue au Sphinx ? Tres bien..." \
                    or "Cat got your tongue? Very well..."
                egg_response = f"{flavor} {hint_text}"
            else:
                egg_response = _get_easter_egg_response(egg, session.language)
        else:
            egg_response = _get_easter_egg_response(egg, session.language)
        turn = game_engine.process_question(session, req.text, "unknown", egg_response)
        audio_id = await _generate_tts(egg_response)
        if audio_id:
            turn.audio_id = audio_id
        session_store.save(session)
        return _session_response(session)

    # 1. Interpret the question
    parsed = await interpreter.interpret(req.text)

    # If the interpreter detects a guess, redirect to guess flow
    # In multiplayer, only allow if the current player still has guesses
    can_guess = (
        session.mode != "multiplayer"
        or game_engine.can_player_guess(session, session.current_player)
    )
    if parsed.intent == "guess" and parsed.guess_name and can_guess:
        correct = check_guess(parsed.guess_name, character)
        turn = game_engine.process_guess(session, req.text, correct, character)

        if session.state == GameState.ENDED and session.result == "lose":
            defeat_msg = game_engine.get_defeat_message(session, character)
            turn.sphinx_utterance += f" {defeat_msg}"

        audio_id = await _generate_tts(turn.sphinx_utterance)
        if audio_id:
            turn.audio_id = audio_id
        if session.state == GameState.ENDED:
            _finalize_game(session)
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

    # 2b. LLM fallback if deterministic resolver returned unknown
    if resolved.answer == "unknown":
        llm_answer = await fallback_resolver.resolve(
            req.text,
            facts=character.facts or None,
            attributes=character.attributes or None,
        )
        if llm_answer in ("yes", "no"):
            resolved = ResolvedAnswer(answer=llm_answer, source="fact")
            logger.info("LLM fallback resolved '%s' -> %s", req.text[:40], llm_answer)

    # 3. Generate Sphinx voice (mood-aware)
    from lesphinx.llm.voice import get_mood
    mood = get_mood(session)
    sphinx_text = await sphinx_voice.speak(
        answer=resolved.answer,
        language=session.language,
        question=req.text,
        matched_fact=resolved.matched_fact,
        mood=mood,
    )

    # 3b. Track hint offer if Sphinx teases the player
    _HINT_IDIOMS = ("langue au sphinx", "cat got your tongue", "tongue to the sphinx")
    if any(idiom in sphinx_text.lower() for idiom in _HINT_IDIOMS):
        session.pending_hint_offer = True

    # 3c. Sphinx "slip" - subtle hint embedded in response (~15% on yes)
    if resolved.answer == "yes" and random.random() < 0.15:
        slip = _generate_slip(character, session)
        if slip:
            sphinx_text = f"{sphinx_text} {slip}"

    # 4. Record turn
    turn = game_engine.process_question(
        session, req.text, resolved.answer, sphinx_text,
    )

    # 5. Check for auto-hint (disabled by default)
    hint_text = None
    if settings.auto_hints and game_engine.should_give_hint(session):
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

    if session.state == GameState.ENDED:
        _finalize_game(session)
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

    if session.mode == "multiplayer" and not game_engine.can_player_guess(session, session.current_player):
        raise HTTPException(status_code=400, detail="This player has no guesses remaining")

    correct = check_guess(req.name, character)

    turn = game_engine.process_guess(session, req.name, correct, character)

    # Contextual wrong guess reaction
    if not correct and session.state != GameState.ENDED:
        from lesphinx.llm.voice import get_mood
        mood = get_mood(session)
        reaction = await sphinx_voice.react_to_wrong_guess(req.name, session.language, mood)
        if reaction:
            turn.sphinx_utterance = reaction

    if session.state == GameState.ENDED and session.result == "lose":
        defeat_msg = game_engine.get_defeat_message(session, character)
        turn.sphinx_utterance += f" {defeat_msg}"

    audio_id = await _generate_tts(turn.sphinx_utterance)
    if audio_id:
        turn.audio_id = audio_id

    if session.state == GameState.ENDED:
        _finalize_game(session)
    log_event("guess", session.session_id, name=req.name, correct=correct)
    session_store.save(session)
    return _session_response(session)


@router.post("/game/{session_id}/hint")
async def request_hint(session_id: str):
    session = _get_session(session_id)

    if session.state == GameState.ENDED:
        raise HTTPException(status_code=400, detail="Game has ended")
    if session.state != GameState.LISTENING:
        raise HTTPException(status_code=400, detail="Game is not ready")

    if len(session.hints_given) >= settings.max_hints:
        raise HTTPException(status_code=400, detail="No hints remaining")

    character = _get_character(session.secret_character_id)
    fact_store = FactStore(character)

    hint_text = game_engine.generate_hint(fact_store, session)
    if not hint_text:
        raise HTTPException(status_code=400, detail="No hints available")

    audio_id = await _generate_tts(hint_text)

    log_event("hint", session.session_id, hint=hint_text,
              hints_used=len(session.hints_given))
    session_store.save(session)

    return {
        "hint_text": hint_text,
        "audio_id": audio_id,
        "hints_remaining": settings.max_hints - len(session.hints_given),
    }


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


# --- Leaderboard & Stats ---

@router.get("/leaderboard")
async def get_leaderboard():
    from lesphinx.store.leaderboard import leaderboard_store
    return {
        "entries": leaderboard_store.get_top(),
        "stats": leaderboard_store.get_stats(),
    }


@router.post("/leaderboard")
async def submit_leaderboard(body: dict):
    from lesphinx.store.leaderboard import LeaderboardEntry, leaderboard_store
    session_id = body.get("session_id", "")
    import re as _re
    raw_name = body.get("player_name", "Anonymous").strip()[:20] or "Anonymous"
    player_name = _re.sub(r"[<>&\"']", "", raw_name) or "Anonymous"

    session = _get_session(session_id)
    if session.state != GameState.ENDED or session.result != "win":
        raise HTTPException(status_code=400, detail="Only winning games can be submitted")

    if session.score <= 0:
        session.score = game_engine.calculate_score(session)

    char = _characters_by_id.get(session.secret_character_id)
    char_name = char.name if char else "?"

    entry = LeaderboardEntry(
        player_name=player_name,
        score=session.score,
        difficulty=session.difficulty,
        character_name=char_name,
        questions_count=session.question_count,
        hints_used=len(session.hints_given),
    )
    rank = leaderboard_store.submit(entry)
    return {"rank": rank, "score": session.score}
