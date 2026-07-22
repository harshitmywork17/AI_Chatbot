"""Semantic Table Discovery & Relationship Resolution Service.

Performs true vector embedding semantic search (dense vector embeddings + cosine similarity)
over DB-loaded table descriptions to identify candidate tables, then resolves Foreign Key
join relationships for multi-table queries.
"""

import json
import logging
import math
from typing import Any, Dict, List, Set

from sqlalchemy import text

from app.core.database import DatabaseSessionProvider
from app.services.metadata_reader import ensure_table_descriptions_table, fetch_all_db_table_metadata

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

_log = logging.getLogger(__name__)


def _cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """Compute cosine similarity between query embedding vector and table description embedding vector."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    if HAS_NUMPY:
        a = np.array(vec_a, dtype=float)
        b = np.array(vec_b, dtype=float)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))

    dot_product = sum(x * y for x, y in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(x * x for x in vec_a))
    norm_b = math.sqrt(sum(y * y for y in vec_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot_product / (norm_a * norm_b)


def _token_similarity_fallback(query: str, text: str) -> float:
    """Fallback similarity score when vector embedding model is unavailable."""
    query_words = set(query.lower().split())
    text_words = set(text.lower().split())
    if not query_words or not text_words:
        return 0.0
    intersection = query_words.intersection(text_words)
    return len(intersection) / math.sqrt(len(query_words) * len(text_words))


def save_embedding_to_db(table_name: str, description: str, embedding: List[float]) -> None:
    """Persist generated vector embedding into the PostgreSQL table_descriptions table.

    Tries to store the embedding as a native pgvector type first. Falls back to
    a JSON-encoded TEXT column when pgvector is not available. Each attempt uses
    its own transaction so an aborted connection from the first attempt does not
    poison the fallback attempt.
    """
    if not table_name or not embedding:
        return

    provider = DatabaseSessionProvider()
    ensure_table_descriptions_table()

    upsert_sql = text("""
        INSERT INTO table_descriptions (table_name, description, embedding)
        VALUES (:t, :d, :e)
        ON CONFLICT (table_name) DO UPDATE
        SET description = EXCLUDED.description, embedding = EXCLUDED.embedding
    """)

    # First attempt: native pgvector string representation e.g. "[0.1, 0.2, ...]"
    try:
        with provider.engine.begin() as conn:
            conn.execute(upsert_sql, {"t": table_name, "d": description, "e": str(embedding)})
        return
    except Exception as exc:
        _log.warning(
            "pgvector upsert failed for table '%s', retrying with JSON fallback: %s", table_name, exc
        )

    # Second attempt: JSON-encoded text fallback (fresh connection — previous transaction is gone)
    try:
        with provider.engine.begin() as conn:
            conn.execute(upsert_sql, {"t": table_name, "d": description, "e": json.dumps(embedding)})
    except Exception as exc:
        _log.error("Failed to persist embedding for table '%s': %s", table_name, exc)


class TableSearchService:
    """Singleton service for semantic table discovery using pgvector persisted embeddings."""

    _instance: "TableSearchService | None" = None

    def __new__(cls) -> "TableSearchService":
        if cls._instance is None:
            instance = super().__new__(cls)
            # Instance-level state — not class-level to avoid shared mutable defaults
            instance._embed_model: Any = None
            instance._embedding_cache: Dict[str, List[float]] = {}
            try:
                from llama_index.core import Settings
                instance._embed_model = Settings.embed_model
            except Exception as exc:
                _log.warning("Embedding model not available — falling back to token similarity: %s", exc)
            cls._instance = instance
        return cls._instance

    def _get_embedding(self, text_content: str) -> List[float]:
        """Return a cached or freshly generated dense vector embedding for the input text."""
        if text_content in self._embedding_cache:
            return self._embedding_cache[text_content]

        if self._embed_model is not None:
            try:
                vec = self._embed_model.get_text_embedding(text_content)
                if vec:
                    self._embedding_cache[text_content] = vec
                return vec
            except Exception as exc:
                _log.warning("Embedding generation failed for text (first 60 chars: '%s'): %s",
                             text_content[:60], exc)
        return []

    def search_relevant_tables(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """Perform semantic search over DB table descriptions and resolve FK target tables.

        Args:
            query: Natural-language user query to match against table descriptions.
            top_k: Number of top candidate tables to select before FK resolution.

        Returns:
            List of table metadata dicts for candidate tables plus their FK targets.
        """
        all_metadata = fetch_all_db_table_metadata()
        if not all_metadata:
            return []

        query_vector = self._get_embedding(query)

        # Score every table by vector cosine similarity (or token overlap as fallback)
        scored_tables = []
        for meta in all_metadata:
            searchable_text = (
                f"Table {meta['table_name']}: {meta['description']}. Columns: "
                + ", ".join([f"{c['name']} ({c['description']})" for c in meta["columns"]])
            )

            # Use DB-persisted embedding if available, otherwise generate + persist
            stored_emb = meta.get("stored_embedding")
            if stored_emb and isinstance(stored_emb, list):
                table_vector = stored_emb
            elif stored_emb and isinstance(stored_emb, str) and stored_emb.startswith("["):
                try:
                    table_vector = json.loads(stored_emb)
                except Exception:
                    table_vector = self._get_embedding(searchable_text)
                    save_embedding_to_db(meta["table_name"], meta["description"], table_vector)
            else:
                table_vector = self._get_embedding(searchable_text)
                if table_vector:
                    save_embedding_to_db(meta["table_name"], meta["description"], table_vector)

            if query_vector and table_vector:
                score = _cosine_similarity(query_vector, table_vector)
            else:
                score = _token_similarity_fallback(query, searchable_text)

            scored_tables.append((score, meta))

        # Sort descending by similarity score
        scored_tables.sort(key=lambda x: x[0], reverse=True)

        # Select top_k candidates
        candidate_metas = [item[1] for item in scored_tables[:top_k]]
        candidate_names: Set[str] = {m["table_name"] for m in candidate_metas}

        # Expand to include FK join target tables (e.g. devices -> rooms -> sites)
        resolved_names: Set[str] = set(candidate_names)
        for meta in candidate_metas:
            for rel in meta.get("relationships", []):
                target = rel.get("target_table")
                if target:
                    resolved_names.add(target)

        # Build final list preserving all resolved table metadata
        meta_lookup = {m["table_name"]: m for m in all_metadata}
        return [meta_lookup[name] for name in sorted(resolved_names) if name in meta_lookup]
