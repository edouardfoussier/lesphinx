# LeSphinx

Vocal Akinator-style guessing game. Think of a famous person, the Sphinx will guess who it is by asking yes/no questions - using voice.

Built for the Mistral Hackathon.

## Setup

### Prerequisites

- Python 3.11+
- ffmpeg (for audio conversion): `brew install ffmpeg`

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
2. Think of a famous person
3. Click "New Game"
4. The Sphinx asks yes/no questions
5. Answer by voice (hold the mic button) or click the buttons
6. The Sphinx tries to guess your character!

## Tech Stack

- **Backend**: FastAPI + Pydantic
- **LLM**: Mistral (structured output)
- **TTS**: ElevenLabs
- **STT**: Mistral Audio
- **Frontend**: Vanilla HTML/JS/CSS
