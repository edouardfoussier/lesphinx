from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    # Mistral
    mistral_api_key: str = ""
    mistral_model: str = "mistral-large-latest"

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

    # SphinxVoice mode: "template" (fast), "llm" (rich), "auto" (template + llm if latency ok)
    sphinx_voice_mode: str = "auto"
    sphinx_voice_llm_timeout: float = 1.5

    # Timeouts (seconds)
    llm_timeout: int = 30
    tts_timeout: int = 20

    # Server
    host: str = "0.0.0.0"
    port: int = 8000


settings = Settings()
