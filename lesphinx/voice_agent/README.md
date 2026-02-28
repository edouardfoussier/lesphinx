# Voice Agent — Real-Time Voice for LeSphinx

## What was chosen and why

### Research Summary

| Technology | Type | Latency | Deterministic? | Status |
|---|---|---|---|---|
| **PersonaPlex (NVIDIA)** | Speech-to-speech, full-duplex | ~170ms | No (generates own responses) | Open weights + fal.ai hosted API |
| ElevenLabs Conv. AI | Autonomous voice agent | ~500ms | No | GA, WebSocket API |
| OpenAI Realtime API | Speech-to-speech | ~300ms | No | GA, WebSocket |
| Deepgram Voice Agent | Autonomous voice agent | ~300ms | No | GA, WebSocket |

### The problem with full speech-to-speech models

LeSphinx requires **deterministic answers** from the FactStore/AnswerResolver.
All speech-to-speech models (PersonaPlex, OpenAI Realtime, etc.) generate their
own responses via LLM — they cannot be constrained to return only what our game
logic dictates.

### Our solution: two-mode architecture

**Mode 1: "streaming" (default, deterministic)**
- Browser STT → text sent via WebSocket → server game logic (unchanged)
- ElevenLabs **WebSocket streaming TTS** replaces the batch REST API
- Audio chunks stream back to the client as they're generated
- **Result: ~1s faster time-to-first-audio** vs the current REST pipeline

**Mode 2: "personaplex" (experimental)**
- Full-duplex voice via PersonaPlex on fal.ai
- Persona prompt embeds the character's attributes and facts
- Answers are *approximately* deterministic (constrained by prompt, not FactStore)
- Game state is still tracked server-side
- **Result: ~170ms latency, natural conversation feel**

## Architecture

```
                     ┌──────────────────────────────────┐
                     │       Browser (Chrome)            │
                     │  Web Speech API (STT)             │
                     │  AudioContext (playback)           │
                     └───────────┬──────────────────────┘
                                 │ WebSocket
                                 │ ws://host/game/{id}/voice
                     ┌───────────▼──────────────────────┐
                     │    ws_handler.py (FastAPI WS)     │
                     │                                    │
                     │  ┌─ "streaming" mode ────────────┐│
                     │  │ QuestionInterpreter            ││
                     │  │ AnswerResolver (deterministic) ││
                     │  │ SphinxVoice (theatrical)       ││
                     │  │ ElevenLabs streaming TTS ──────┤│──► audio chunks
                     │  └───────────────────────────────┘│
                     │                                    │
                     │  ┌─ "personaplex" mode (exp.) ───┐│
                     │  │ fal.ai PersonaPlex WebSocket   ││
                     │  │ Persona prompt w/ char facts   ││──► audio + text
                     │  │ Answer signal extraction       ││
                     │  └───────────────────────────────┘│
                     └──────────────────────────────────┘
```

## Files

| File | Purpose |
|---|---|
| `__init__.py` | Package docstring |
| `client.py` | PersonaPlex fal.ai WebSocket client |
| `persona.py` | Persona prompt builder (embeds character facts, never the name) |
| `streaming.py` | ElevenLabs WebSocket streaming TTS |
| `ws_handler.py` | FastAPI WebSocket endpoint handler |
| `README.md` | This file |

## WebSocket Protocol

### Client → Server

```jsonc
// Set mode (optional, defaults to "streaming")
{"type": "config", "mode": "streaming"}  // or "personaplex"

// Send transcribed text (from browser STT)
{"type": "text", "text": "Is the person a scientist?"}

// Send a guess
{"type": "guess", "name": "Albert Einstein"}

// Send raw audio (personaplex mode only, PCM s16le 24kHz mono, base64)
{"type": "audio", "audio": "<base64>"}

// Keepalive
{"type": "ping"}
```

### Server → Client

```jsonc
// Connection established
{"type": "connected", "mode": "streaming", "session_id": "abc123"}

// Sphinx's text response
{"type": "sphinx_text", "text": "The sands of the Nile whisper yes..."}

// Audio chunk (stream as they arrive, play immediately)
{"type": "audio_chunk", "audio": "<base64>", "format": "mp3"}

// All audio sent
{"type": "audio_end"}

// Updated game state
{"type": "state", "session_id": "...", "state": "listening", ...}

// Error
{"type": "error", "message": "..."}
```

## Configuration

Add to `.env`:

```bash
# Enable the voice agent WebSocket endpoint
VOICE_AGENT_ENABLED=true

# Mode: "streaming" (deterministic) or "personaplex" (experimental)
VOICE_AGENT_MODE=streaming

# ElevenLabs streaming TTS (uses existing ELEVENLABS_* keys)
VOICE_AGENT_STREAMING_TTS=true

# PersonaPlex via fal.ai (only needed for "personaplex" mode)
FAL_API_KEY=your_fal_api_key_here
PERSONAPLEX_VOICE=NATM0
```

## How to test

### Streaming mode (recommended)

1. Set `VOICE_AGENT_ENABLED=true` in `.env`
2. Start the server: `uvicorn lesphinx.main:app --reload`
3. Connect via WebSocket (e.g., using websocat or browser JS):

```javascript
const ws = new WebSocket(`ws://localhost:8000/game/${sessionId}/voice`);
ws.onmessage = (e) => {
  const msg = JSON.parse(e.data);
  if (msg.type === 'audio_chunk') {
    // decode base64 MP3, feed to AudioContext for playback
  }
};
// After creating a game via POST /game/new:
ws.send(JSON.stringify({type: 'text', text: 'Is the person alive?'}));
```

### PersonaPlex mode (experimental)

1. Get a fal.ai API key from https://fal.ai
2. Set `FAL_API_KEY=...` and `VOICE_AGENT_MODE=personaplex` in `.env`
3. Connect via WebSocket and send `{"type": "config", "mode": "personaplex"}`
4. Send audio chunks: `{"type": "audio", "audio": "<base64 PCM s16le 24kHz>"}`

## Latency comparison

| Pipeline | STT | Logic | TTS | Total |
|---|---|---|---|---|
| **Current (REST)** | Browser STT (~0ms server) | Interpreter + Resolver (~200ms) | ElevenLabs batch (~1-2s) | **~2-4s** |
| **Streaming mode** | Browser STT (~0ms server) | Interpreter + Resolver (~200ms) | ElevenLabs streaming (~400ms to first chunk) | **~0.6-1.5s** |
| **PersonaPlex mode** | PersonaPlex (~50ms) | In-model (~0ms) | In-model (~170ms total) | **~170ms** |

## Limitations

1. **PersonaPlex mode is not fully deterministic**: Answers are generated by the LLM
   based on the persona prompt, not by the FactStore. They are *usually* correct
   but may occasionally diverge from what the deterministic pipeline would return.

2. **PersonaPlex requires fal.ai API key**: The model weights are open-source but
   require GPU infrastructure to self-host. The fal.ai hosted API is the easiest path.

3. **Audio format mismatch**: PersonaPlex uses PCM s16le 24kHz; the browser typically
   expects MP3 or WAV. The client must handle format conversion.

4. **No voice cloning yet**: PersonaPlex supports voice cloning via `voice_audio_url`
   but we use preset voices for simplicity.
