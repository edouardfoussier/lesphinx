"""LeSphinx MCP Server — lets AI agents play the guessing game programmatically.

Run standalone:
    python -m lesphinx.mcp_server          # stdio transport (default)
    python -m lesphinx.mcp_server --sse     # SSE transport on port 8100

The server talks to the LeSphinx REST API over HTTP.
Configure the base URL via the LESPHINX_API_URL env var (default: http://localhost:8000).
"""

from __future__ import annotations

import os
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

LESPHINX_API_URL = os.environ.get("LESPHINX_API_URL", "http://localhost:8000").rstrip("/")

# Configure transport security for production deployment
# Allow both localhost (dev) and production domain
transport_security = TransportSecuritySettings(
    enable_dns_rebinding_protection=True,
    allowed_hosts=[
        "127.0.0.1:*", "localhost:*", "[::1]:*",  # Local development
        "mcp.thesphinx.ai", "mcp.thesphinx.ai:*",  # Production
    ],
    allowed_origins=[
        "http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*",
        "https://mcp.thesphinx.ai", "https://thesphinx.ai",
    ],
)

mcp = FastMCP(
    "LeSphinx",
    instructions=(
        "LeSphinx is a guessing game where the Sphinx thinks of a famous person "
        "and you ask yes/no questions to figure out who it is. "
        "Start a game with start_game, then use ask_question to narrow down, "
        "request_hint if stuck, and make_guess when ready. "
        "You have 20 questions and 3 guess attempts. Good luck, mortal!"
    ),
    transport_security=transport_security,
)

_http = httpx.AsyncClient(base_url=LESPHINX_API_URL, timeout=30.0)


async def _post(path: str, json: dict[str, Any] | None = None) -> dict[str, Any]:
    resp = await _http.post(path, json=json or {})
    resp.raise_for_status()
    return resp.json()


async def _get(path: str) -> dict[str, Any]:
    resp = await _http.get(path)
    resp.raise_for_status()
    return resp.json()


def _format_turns(turns: list[dict]) -> list[dict]:
    """Simplify turn data for agent consumption."""
    return [
        {
            "turn": t["turn_number"],
            "player_text": t.get("player_text", ""),
            "intent": t.get("intent", ""),
            "raw_answer": t.get("raw_answer"),
            "sphinx_says": t.get("sphinx_utterance", ""),
        }
        for t in turns
    ]


def _format_state(data: dict) -> dict:
    """Build a clean game-state dict an agent can easily parse."""
    return {
        "session_id": data["session_id"],
        "state": data["state"],
        "language": data["language"],
        "difficulty": data["difficulty"],
        "questions_used": data["question_count"],
        "max_questions": data["max_questions"],
        "guesses_used": data["guess_count"],
        "max_guesses": data["max_guesses"],
        "result": data.get("result"),
        "score": data.get("score", 0),
        "sphinx_confidence": data.get("sphinx_confidence", 100),
        "current_streak": data.get("current_streak", 0),
        "revealed_character": data.get("revealed_character"),
        "revealed_summary": data.get("revealed_summary"),
        "achievements": data.get("achievements", []),
        "turns": _format_turns(data.get("turns", [])),
    }


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def start_game(
    language: str = "en",
    difficulty: str = "medium",
    themes: list[str] | None = None,
) -> dict:
    """Start a new LeSphinx game. The Sphinx will think of a famous person.

    Args:
        language: Game language — "en" (English) or "fr" (French). Default "en".
        difficulty: "easy", "medium", or "hard". Harder means more obscure characters.
        themes: Optional list of theme filters, e.g. ["science", "music", "cinema"].
                Available themes: activism, arts, business, cinema, exploration,
                history, literature, music, philosophy, politics, religion,
                science, sports, technology.

    Returns:
        The initial game state including session_id (needed for all subsequent calls)
        and the Sphinx's opening utterance.
    """
    data = await _post("/game/new", {
        "language": language,
        "difficulty": difficulty,
        "mode": "solo",
        "themes": themes or [],
    })
    return _format_state(data)


@mcp.tool()
async def ask_question(session_id: str, question: str) -> dict:
    """Ask the Sphinx a yes/no question about the secret character.

    The Sphinx answers with yes, no, or unknown. You have up to 20 questions.
    Ask strategic questions to narrow down the possibilities — start broad
    (alive? male? European?) then get specific.

    Args:
        session_id: The game session ID from start_game.
        question: A yes/no question in natural language, e.g. "Is this person alive?"

    Returns:
        Updated game state with the Sphinx's theatrical answer.
    """
    data = await _post(f"/game/{session_id}/ask", {"text": question})
    return _format_state(data)


@mcp.tool()
async def make_guess(session_id: str, name: str) -> dict:
    """Guess the secret character's name.

    You have 3 guess attempts per game. The name is fuzzy-matched (handles
    accents, partial names, aliases). Only guess when you're fairly confident.

    Args:
        session_id: The game session ID from start_game.
        name: Your guess — the full name of the character, e.g. "Albert Einstein".

    Returns:
        Updated game state. Check 'result' — "win" if correct, null if wrong
        but still playing, "lose" if out of guesses/questions.
    """
    data = await _post(f"/game/{session_id}/guess", {"name": name})
    return _format_state(data)


@mcp.tool()
async def request_hint(session_id: str) -> dict:
    """Ask the Sphinx for a hint about the secret character.

    You get up to 3 hints per game, but each one costs 50 points.
    Use sparingly — only when truly stuck.

    Args:
        session_id: The game session ID from start_game.

    Returns:
        The hint text and how many hints remain.
    """
    data = await _post(f"/game/{session_id}/hint")
    return {
        "hint": data.get("hint_text", ""),
        "hints_remaining": data.get("hints_remaining", 0),
    }


@mcp.tool()
async def get_game_state(session_id: str) -> dict:
    """Get the current state of a game.

    Useful to check game progress, review past turns, or see the final result.

    Args:
        session_id: The game session ID from start_game.

    Returns:
        Full game state including all turns, score, and result.
    """
    data = await _get(f"/game/{session_id}/state")
    return _format_state(data)


@mcp.tool()
async def submit_score(session_id: str, player_name: str = "AI Agent") -> dict:
    """Submit your score to the leaderboard after winning a game.

    Only works for games that ended in a win.

    Args:
        session_id: The game session ID.
        player_name: Name to display on the leaderboard (max 20 chars).

    Returns:
        Your rank and score on the leaderboard.
    """
    data = await _post("/leaderboard", {
        "session_id": session_id,
        "player_name": player_name[:20],
    })
    return {"rank": data.get("rank"), "score": data.get("score")}


@mcp.tool()
async def get_leaderboard() -> dict:
    """Get the current leaderboard and global game statistics.

    Returns:
        Top 10 scores and aggregate stats (total games, win rate, etc.).
    """
    return await _get("/leaderboard")


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------


@mcp.resource("lesphinx://rules")
async def game_rules() -> str:
    """Complete rules of the LeSphinx guessing game."""
    return """# LeSphinx — Game Rules

## Objective
The Sphinx has chosen a famous person (real or fictional). Your goal is to
figure out who it is by asking yes/no questions.

## Rules
- You may ask up to **20 questions** per game.
- You have **3 guess attempts**. Only guess when confident.
- You can request up to **3 hints** (each costs 50 points from your score).
- The Sphinx answers: **yes**, **no**, or **unknown** (if uncertain).
- The game ends when you guess correctly (win), run out of questions/guesses
  (lose), or surrender.

## Scoring
    score = 1000 - 40×questions - 100×wrong_guesses - 50×hints + difficulty_bonus
Difficulty bonus: easy=0, medium=+200, hard=+500.

## Difficulty Levels
- **Easy**: Well-known figures (Einstein, Cleopatra, Beatles members…)
- **Medium**: Moderately known (Frida Kahlo, Alan Turing, Serena Williams…)
- **Hard**: Obscure or historical (Hypatia, Nikola Tesla, Ada Lovelace…)

## Available Themes
activism, arts, business, cinema, exploration, history, literature, music,
philosophy, politics, religion, science, sports, technology.

## Achievements
- 𓂀 Novice du Désert — First win
- 𓁹 Œil d'Horus — Win in < 10 questions
- ⚔ Tueur de Sphinx — Win in < 5 questions
- 𓆣 Cauchemar du Sphinx — Win on hard difficulty
- 𓋹 Omniscient — Win with no hints and no wrong guesses
- 𓃀 Persistant — Win after 2+ wrong guesses
- 𓏛 Érudit — Win with 15+ questions asked
- ⚡ Éclair du Désert — Score > 900

## The Sphinx's Personality
The Sphinx is theatrical, mysterious, and slightly mocking. It addresses you
as "mortal" and speaks in riddles. Its mood shifts as the game progresses:
confident early on, intrigued mid-game, and nervous if you're closing in.
"""


@mcp.resource("lesphinx://strategy")
async def strategy_tips() -> str:
    """Strategy tips for AI agents playing LeSphinx."""
    return """# LeSphinx — Strategy Guide for AI Agents

## Optimal Question Strategy

### Phase 1: Binary Search (Questions 1-6)
Start with broad categorical questions to halve the search space each time:
1. "Is this person alive today?"
2. "Is this person male?"
3. "Is this person from Europe?" (then narrow continent)
4. "Is this person primarily known for science or technology?"
5. "Was this person born before 1900?"
6. "Is this person associated with politics or leadership?"

### Phase 2: Domain Narrowing (Questions 7-12)
Based on Phase 1 answers, drill into the specific domain:
- For scientists: "Did they win a Nobel Prize?", "Is their field physics?"
- For artists: "Are they a musician?", "Were they active in the 20th century?"
- For politicians: "Were they a head of state?", "Are they American?"

### Phase 3: Identification (Questions 13-18)
Ask about distinguishing characteristics:
- "Is this person known for a specific theory or invention?"
- "Did they live past the age of 70?"
- "Are they known for a tragic or dramatic life event?"

### Phase 4: Confirmation & Guess (Questions 18-20)
When you're fairly sure, make your guess. Don't waste all 20 questions —
guess once you have a strong hypothesis.

## Key Tips
- **Don't guess too early.** You only have 3 guesses. Wait until you're >80% sure.
- **Use hints wisely.** They cost 50 points each but can save you 2-3 questions
  (worth 80-120 points). Use them when stuck mid-game.
- **Track the Sphinx's confidence.** It drops as you ask good questions.
  A low sphinx_confidence means you're on the right track.
- **Watch for streaks.** Consecutive "yes" answers (current_streak) mean
  you're narrowing in — keep that line of questioning going.
- **The Sphinx sometimes slips.** On ~15% of "yes" answers it may drop a
  subtle clue about the character's continent, era, or field. Pay attention!

## Response Parsing
- `raw_answer` in each turn is the canonical answer: "yes", "no", or "unknown"
- `sphinx_says` is the theatrical version — entertaining but redundant for logic
- `state` == "ended" means the game is over; check `result` for "win"/"lose"
- `revealed_character` and `revealed_summary` appear when the game ends

## Common Mistakes
- Asking non-yes/no questions (the Sphinx may give an "unknown")
- Guessing too early with limited information
- Forgetting to track what you've already learned from previous answers
- Not using the available themes filter to narrow the character pool
"""


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def main() -> None:
    import sys
    transport = "sse" if "--sse" in sys.argv else "stdio"
    if transport == "sse":
        import uvicorn
        from starlette.middleware import Middleware
        from starlette.middleware.trustedhost import TrustedHostMiddleware
        
        app = mcp.sse_app()
        # Allow all hosts for reverse proxy setup
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])
        uvicorn.run(app, host="0.0.0.0", port=8100)
    else:
        mcp.run(transport=transport)


if __name__ == "__main__":
    main()
