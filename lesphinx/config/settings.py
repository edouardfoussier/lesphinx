from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    # Mistral
    mistral_api_key: str = ""
    mistral_model: str = "mistral-large-latest"
    intent_classifier_model: str = "mistral-small-latest"

    # ElevenLabs TTS
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "pNInz6obpgDQGcFmaJgB"  # "Adam" deep voice
    elevenlabs_model: str = "eleven_flash_v2_5"

    # Game rules
    max_questions: int = 20
    max_guesses: int = 3
    max_hints: int = 3
    hard_stop_turns: int = 25
    hint_every_n_questions: int = 7
    auto_hints: bool = False

    # Game engine mode: "hybrid" (deterministic + LLM layers) or "full_llm" (single LLM call)
    game_engine_mode: str = "hybrid"

    # SphinxVoice mode: "template" (fast), "llm" (rich), "auto" (try llm, fallback template)
    sphinx_voice_mode: str = "auto"
    sphinx_voice_llm_timeout: float = 3.0

    # Timeouts (seconds)
    llm_timeout: int = 30
    tts_timeout: int = 20

    # Voice Agent (real-time voice mode)
    voice_agent_enabled: bool = False
    voice_agent_mode: str = "streaming"  # "streaming" (deterministic) or "personaplex" (experimental)
    voice_agent_streaming_tts: bool = True  # use ElevenLabs WebSocket streaming for lower latency

    # fal.ai PersonaPlex (experimental full-duplex voice)
    fal_api_key: str = ""
    personaplex_model: str = "fal-ai/personaplex/realtime"
    personaplex_voice: str = "NATM0"  # Male natural voice (options: NATM0-3, NATF0-3, VARM0-4, VARF0-4)

    # Server
    host: str = "0.0.0.0"
    port: int = 8000


settings = Settings()
