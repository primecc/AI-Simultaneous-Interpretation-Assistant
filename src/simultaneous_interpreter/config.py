from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI Simultaneous Interpretation Assistant"
    app_env: str = "development"
    local_asr_model: str = "tiny.en"
    source_language: str = "en"
    target_language: str = "zh"
    audio_chunk_seconds: float = 2.2
    asr_beam_size: int = 3
    asr_best_of: int = 3

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
