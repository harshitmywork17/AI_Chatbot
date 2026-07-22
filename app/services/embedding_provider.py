"""Embedding client factory: swap providers via EMBEDDING_PROVIDER without touching call sites.

To add a new provider: write one `_build_<name>` function below and add it to
`_EMBEDDING_BUILDERS`. Nothing else in the app needs to change.
"""

from typing import Callable

from llama_index.core.base.embeddings.base import BaseEmbedding

from app.core.config import Settings, get_settings

_DEFAULT_MODELS = {
    "local": "BAAI/bge-small-en-v1.5",
    "openai": "text-embedding-3-small",
}


def _build_local(settings: Settings, model: str) -> BaseEmbedding:
    from llama_index.embeddings.huggingface import HuggingFaceEmbedding

    return HuggingFaceEmbedding(model_name=model)


def _build_openai(settings: Settings, model: str) -> BaseEmbedding:
    from llama_index.embeddings.openai import OpenAIEmbedding

    return OpenAIEmbedding(model=model, api_key=settings.openai_api_key)


# Each builder imports its own package lazily, so installing only one provider's
# dependencies is enough to run the app.
_EMBEDDING_BUILDERS: dict[str, Callable[[Settings, str], BaseEmbedding]] = {
    "local": _build_local,
    "openai": _build_openai,
}


def _build_embed_model(settings: Settings) -> BaseEmbedding:
    try:
        builder = _EMBEDDING_BUILDERS[settings.embedding_provider]
    except KeyError:
        raise ValueError(f"Unsupported EMBEDDING_PROVIDER: {settings.embedding_provider!r}") from None

    model = settings.embedding_model or _DEFAULT_MODELS[settings.embedding_provider]
    return builder(settings, model)


class EmbeddingProvider:
    """Process-wide embedding client, built once from settings and reused."""

    _instance: "EmbeddingProvider | None" = None
    _embed_model: BaseEmbedding

    def __new__(cls) -> "EmbeddingProvider":
        # __new__ (not __init__) returns the cached instance, so repeated
        # EmbeddingProvider() calls reuse one loaded model per process.
        if cls._instance is None:
            instance = super().__new__(cls)
            instance._embed_model = _build_embed_model(get_settings())
            cls._instance = instance
        return cls._instance

    @property
    def embed_model(self) -> BaseEmbedding:
        return self._embed_model
