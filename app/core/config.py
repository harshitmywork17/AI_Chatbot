"""Environment-driven application settings."""

from functools import lru_cache

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LLM_PROVIDERS = frozenset({"groq", "anthropic"})
EMBEDDING_PROVIDERS = frozenset({"local", "openai"})


class Settings(BaseSettings):
    """Typed settings loaded from environment variables / .env file.

    LLM_PROVIDER and EMBEDDING_PROVIDER pick which backend app.services.llm_provider
    and app.services.embedding_provider construct; only that provider's API key is
    required, so switching providers is a config change, not a code change.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = Field(..., alias="DATABASE_URL")
    log_level: str = Field("INFO", alias="LOG_LEVEL")

    llm_provider: str = Field("groq", alias="LLM_PROVIDER")
    llm_model: str | None = Field(None, alias="LLM_MODEL")
    groq_api_key: str | None = Field(None, alias="GROQ_API_KEY")
    anthropic_api_key: str | None = Field(None, alias="ANTHROPIC_API_KEY")

    embedding_provider: str = Field("local", alias="EMBEDDING_PROVIDER")
    embedding_model: str | None = Field(None, alias="EMBEDDING_MODEL")
    openai_api_key: str | None = Field(None, alias="OPENAI_API_KEY")

    @field_validator("llm_provider", "embedding_provider", mode="before")
    @classmethod
    def _normalize_provider_name(cls, value: object) -> object:
        # Env vars are commonly written upper/mixed case (e.g. "GROQ"); provider
        # names are case-insensitive identifiers, not user-facing text.
        return value.strip().lower() if isinstance(value, str) else value

    @model_validator(mode="after")
    def _validate_provider_credentials(self) -> "Settings":
        if self.llm_provider not in LLM_PROVIDERS:
            raise ValueError(f"LLM_PROVIDER must be one of {sorted(LLM_PROVIDERS)}, got {self.llm_provider!r}")
        if self.embedding_provider not in EMBEDDING_PROVIDERS:
            raise ValueError(
                f"EMBEDDING_PROVIDER must be one of {sorted(EMBEDDING_PROVIDERS)}, got {self.embedding_provider!r}"
            )
        if self.llm_provider == "groq" and not self.groq_api_key:
            raise ValueError("GROQ_API_KEY is required when LLM_PROVIDER=groq")
        if self.llm_provider == "anthropic" and not self.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is required when LLM_PROVIDER=anthropic")
        if self.embedding_provider == "openai" and not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required when EMBEDDING_PROVIDER=openai")
        return self


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide cached Settings instance."""
    return Settings()
