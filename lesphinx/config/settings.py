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
    min_questions_before_guess: int = 5
    max_questions: int = 15
    max_guesses: int = 2
    auto_guess_confidence: float = 0.85
    hard_stop_turns: int = 20

    # Timeouts (seconds)
    stt_timeout: int = 15
    llm_timeout: int = 30
    tts_timeout: int = 20

    # Server
    host: str = "0.0.0.0"
    port: int = 8000


settings = Settings()
