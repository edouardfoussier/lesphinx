# LeSphinx

A vocal guessing game where the Sphinx thinks of a famous person and you must figure out who it is by asking questions -- using your voice.

Built for the Mistral Hackathon.

## How It Works

The Sphinx selects a secret character from a database of 160+ famous people. You ask questions in natural language (voice or text), and the Sphinx answers **yes**, **no**, or **I don't know** in a theatrical voice. Your goal: guess the character before running out of questions.

**Key design**: the LLM never decides truth. A deterministic engine resolves answers from structured character data. The LLM only parses questions and adds theatrical flair to responses.

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
```

### Run

```bash
uvicorn lesphinx.main:app --reload
```

Open http://localhost:8000

## How to Play

1. Choose your language (French or English)
2. Choose difficulty (Easy / Medium / Hard)
3. Click "New Game" -- the Sphinx picks a secret character
4. Ask questions by typing or using the microphone
5. The Sphinx answers yes/no/unknown with its theatrical voice
6. Click "I want to guess!" when you think you know who it is
7. You have 20 questions and 3 guess attempts

## Architecture

```
Player question -> RuleMatcher (regex, instant) or LLM fallback
                -> AnswerResolver (deterministic, from FactStore)
                -> SphinxVoice (templates or LLM theatrical reformulation)
                -> ElevenLabs TTS -> Audio response
```

- **RuleMatcher**: handles common questions (gender, nationality, field...) with zero latency
- **QuestionInterpreter (LLM)**: parses complex questions into structured queries
- **AnswerResolver**: purely deterministic answers from character attributes and facts
- **SphinxVoice**: theatrical responses via templates (instant) or LLM enrichment (configurable)
- **Judge**: fuzzy name matching for guesses (Levenshtein, aliases, accents)

## Tech Stack

- **Backend**: FastAPI + Pydantic
- **LLM**: Mistral Large (question interpretation + voice enrichment)
- **TTS**: ElevenLabs (text-to-speech for the Sphinx voice)
- **STT**: Web Speech API (browser-side speech recognition)
- **Frontend**: Vanilla HTML/JS/CSS (Egyptian/Sphinx theme)
- **Character data**: 160 curated famous people with structured attributes + Mistral-generated facts

## Character Database

The character database is pre-built and committed. To regenerate:

```bash
MISTRAL_API_KEY=your_key python -m scripts.build_characters
```

This generates `lesphinx/data/characters.json` with 160 characters across 3 difficulty levels, each with structured attributes and 12-15 natural language facts.

## Testing

```bash
pytest tests/ -v
```

68 tests covering: character selection, fact store, answer resolution, guess matching, rule-based interpreter patterns, and game engine rules.
