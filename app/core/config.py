"""Environment-driven application settings."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed settings loaded from environment variables / .env file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = Field(..., alias="DATABASE_URL")
    groq_api_key: str = Field(..., alias="GROQ_API_KEY")
    groq_model: str = Field("llama-3.3-70b-versatile", alias="GROQ_MODEL")
    log_level: str = Field("INFO", alias="LOG_LEVEL")


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide cached Settings instance."""
    return Settings()
