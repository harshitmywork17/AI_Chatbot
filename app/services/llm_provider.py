"""Singleton Groq LLM client (see feedback-prompts-and-singleton-conventions)."""

from llama_index.llms.groq import Groq

from app.core.config import get_settings


class GroqLLMProvider:
    """Process-wide Groq LLM client, built once and reused."""

    _instance: "GroqLLMProvider | None" = None
    _llm: Groq

    def __new__(cls) -> "GroqLLMProvider":
        if cls._instance is None:
            instance = super().__new__(cls)
            settings = get_settings()
            instance._llm = Groq(model=settings.groq_model, api_key=settings.groq_api_key)
            cls._instance = instance
        return cls._instance

    @property
    def llm(self) -> Groq:
        return self._llm
