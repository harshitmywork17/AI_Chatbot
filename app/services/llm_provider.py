"""LLM client factory: swap providers via LLM_PROVIDER without touching call sites.

To add a new provider: write one `_build_<name>` function below and add it to
`_LLM_BUILDERS`. Nothing else in the app needs to change.
"""

from typing import Callable

from llama_index.core.llms import LLM

from app.core.config import Settings, get_settings

_DEFAULT_MODELS = {
    "groq": "openai/gpt-oss-120b",
    "anthropic": "claude-sonnet-5",
}


def _build_groq(settings: Settings, model: str) -> LLM:
    from llama_index.llms.groq import Groq

    return Groq(model=model, api_key=settings.groq_api_key)


def _build_anthropic(settings: Settings, model: str) -> LLM:
    from llama_index.llms.anthropic import Anthropic

    return Anthropic(model=model, api_key=settings.anthropic_api_key)


# Each builder imports its own package lazily, so installing only one provider's
# dependencies is enough to run the app.
_LLM_BUILDERS: dict[str, Callable[[Settings, str], LLM]] = {
    "groq": _build_groq,
    "anthropic": _build_anthropic,
}


def _build_llm(settings: Settings) -> LLM:
    try:
        builder = _LLM_BUILDERS[settings.llm_provider]
    except KeyError:
        raise ValueError(f"Unsupported LLM_PROVIDER: {settings.llm_provider!r}") from None

    model = settings.llm_model or _DEFAULT_MODELS[settings.llm_provider]
    return builder(settings, model)


class LLMProvider:
    """Process-wide LLM client, built once from settings and reused."""

    _instance: "LLMProvider | None" = None
    _llm: LLM

    def __new__(cls) -> "LLMProvider":
        # __new__ (not __init__) returns the cached instance, so repeated
        # LLMProvider() calls reuse one client/HTTP session per process.
        if cls._instance is None:
            instance = super().__new__(cls)
            instance._llm = _build_llm(get_settings())
            cls._instance = instance
        return cls._instance

    @property
    def llm(self) -> LLM:
        return self._llm
