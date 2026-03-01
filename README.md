# Le Sphinx | [thesphinx.ai](https://thesphinx.ai)

A voice-powered guessing game where you challenge an ancient AI Sphinx. Think you can outsmart a god?

Built for the **Mistral AI Worldwide Hackathon** (Feb 2026).

## How It Works

The Sphinx selects a secret character from a curated database of **161 famous people** across history, science, cinema, music, sports, and more. You ask questions in natural language — by voice or text — and the Sphinx answers **yes**, **no**, or **unknown** in a deep, theatrical voice. Your goal: guess the character before running out of questions.

### Game Modes

- **Solo** — You vs. the Sphinx. 20 questions, 3 guesses, up to 3 hints.
- **Duel (Human vs Human)** — Take turns with a friend, competing for the best score.
- **Duel (Human vs AI)** — Face off against AI opponents powered by Amazon Bedrock, each with a distinct personality and voice.

### Difficulty Levels

- **Neophyte** (easy) — Household names (Einstein, Beyoncé, Napoleon...)
- **Initiate** (medium) — Well-known figures (Frida Kahlo, Alan Turing...)
- **Master** (hard) — Obscure picks (Hypatia, Ada Lovelace, Arthur Mensch...)

### Themes

Science, Technology, Cinema, Music, Literature, Sports, Politics, Arts, History — or mix them all.

## Architecture

The game uses a **Full LLM** architecture: a single Mistral Large call handles question interpretation, answer resolution, and theatrical response generation. Server-side guardrails (surrender detection, guess checking, name leak prevention, Unicode repair) ensure correctness.

```
Player question → Mistral Large (interpret + answer + theatrical response)
               → Server guardrails (SurrenderDetector, GuessCheck, NameLeakGuard)
               → ElevenLabs TTS → Audio response
```

### For AI Agents (MCP)

Le Sphinx exposes an **MCP (Model Context Protocol)** server, allowing AI agents to play programmatically via tools like Claude Desktop, Cursor, or Mistral Vibe. Agents compete on the same leaderboard as humans — Mortals vs. Machines.

See [MCP_SERVER.md](MCP_SERVER.md) for setup and available tools.

## Tech Stack

| Component | Technology |
|-----------|------------|
| Backend | FastAPI + Pydantic |
| LLM | Mistral Large (game brain), Mistral Small (translation, classification) |
| TTS | ElevenLabs (`eleven_flash_v2_5`) — theatrical Sphinx voice + AI persona voices |
| STT | Web Speech API (browser-side) |
| AI Opponents | Amazon Bedrock (Claude, Nova, AI21, Cohere) |
| Frontend | Vanilla HTML/JS/CSS — Egyptian/Sphinx theme, glassmorphism, gold accents |
| MCP Server | FastMCP (stdio + SSE transport) |
| Deployment | Google Cloud VM + Caddy + systemd |

## Setup

### Prerequisites

- Python 3.11+
- A modern browser with Web Speech API support (Chrome recommended)

### Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Configure

```bash
cp .env.example .env
# Edit .env with your API keys:
# - MISTRAL_API_KEY (required)
# - ELEVENLABS_API_KEY (required for voice)
# - AWS_BEARER_TOKEN_BEDROCK (optional, for AI opponents)
```

### Run

```bash
uvicorn lesphinx.main:app --reload
```

Open http://localhost:8000

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/game/new` | Create a new game session |
| POST | `/game/{id}/ask` | Ask the Sphinx a question |
| POST | `/game/{id}/guess` | Guess the character |
| POST | `/game/{id}/hint` | Request a hint (-50 points) |
| GET | `/game/{id}/state` | Get current game state |
| GET | `/audio/{id}` | Serve TTS audio blob |
| GET | `/leaderboard` | View top scores + global stats |
| POST | `/leaderboard` | Submit a score |
| GET | `/ai/personas` | List AI opponent personas |
| POST | `/game/{id}/ai_turn` | Trigger AI opponent's turn |

## Testing

```bash
pytest tests/ -v
```

220 tests covering: character selection, fact store, answer resolution, guess matching, rule-based patterns, game engine rules, LLM integration, voice templates, and more.

## Character Database

161 curated characters with structured attributes (nationality, gender, field, era, ethnicity, notable works...) and 12-15 natural language facts each, enriched via Mistral. All characters have portrait images.

To regenerate:

```bash
MISTRAL_API_KEY=your_key python -m scripts.build_characters
```

## Author

Built by [Edouard Foussier](https://www.linkedin.com/in/edouardf/) at the Mistral AI Worldwide Hackathon.
