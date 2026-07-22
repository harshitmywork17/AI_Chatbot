"""Dynamic PostgreSQL Table Metadata Reader.

Reads table descriptions, column semantics, primary key (PK) & foreign key (FK) definitions,
and explicit join relationships directly from PostgreSQL database metadata and table registry.
"""

import logging
from typing import Any, Dict, List

from sqlalchemy import inspect, text

from app.core.constants import TABLE_DESCRIPTIONS
from app.core.database import DatabaseSessionProvider

_log = logging.getLogger(__name__)

# Explicit Foreign Key Join Relationships map between tables
KNOWN_RELATIONSHIPS: Dict[str, List[Dict[str, str]]] = {
    "devices": [
        {"from_column": "room_id", "target_table": "rooms", "target_column": "id", "relationship": "located in room"},
    ],
    "rooms": [
        {"from_column": "site_id", "target_table": "sites", "target_column": "id", "relationship": "located at physical site"},
        {"from_column": "room_type_id", "target_table": "room_types", "target_column": "id", "relationship": "uses room template config"},
    ],
    "events": [
        {"from_column": "device_id", "target_table": "devices", "target_column": "id", "relationship": "event applies to device"},
    ],
    "firmware_inventory": [
        {"from_column": "device_id", "target_table": "devices", "target_column": "id", "relationship": "firmware snapshot of device"},
    ],
    "servicenow_tickets": [
        {"from_column": "device_id", "target_table": "devices", "target_column": "id", "relationship": "ticket associated with device"},
    ],
}


def ensure_table_descriptions_table() -> None:
    """Ensure table_descriptions table exists in PostgreSQL with pgvector / vector support.

    Tries to enable the pgvector extension and create the table with a native
    ``vector`` column. Falls back to a plain ``text`` column when the extension
    is not installed, logging a warning so the degradation is visible.
    """
    provider = DatabaseSessionProvider()
    try:
        with provider.engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS table_descriptions (
                    table_name VARCHAR(255) PRIMARY KEY,
                    description TEXT NOT NULL,
                    embedding vector
                )
            """))
    except Exception as exc:
        _log.warning(
            "pgvector extension not available — falling back to TEXT column for embeddings: %s", exc
        )
        with provider.engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS table_descriptions (
                    table_name VARCHAR(255) PRIMARY KEY,
                    description TEXT NOT NULL,
                    embedding text
                )
            """))


def get_table_metadata_from_db(table_name: str) -> Dict[str, Any]:
    """Fetch column schemas, PKs, FKs, stored vector embeddings, and relationships for a table.

    Args:
        table_name: Name of the PostgreSQL table to inspect.

    Returns:
        A dict containing table_name, description, columns, primary_keys,
        foreign_keys, relationships, and stored_embedding.

    Raises:
        ValueError: If the table does not exist in the database.
    """
    provider = DatabaseSessionProvider()
    inspector = inspect(provider.engine)

    # Verify table existence in DB
    existing_tables = inspector.get_table_names()
    if table_name not in existing_tables:
        raise ValueError(f"Table '{table_name}' does not exist in the database.")

    # 1. Fetch Columns
    raw_columns = inspector.get_columns(table_name)
    columns = [
        {
            "name": col["name"],
            "type": str(col["type"]),
            "nullable": col["nullable"],
            "description": f"Column {col['name']} of type {col['type']}",
        }
        for col in raw_columns
    ]

    # 2. Fetch Primary Key(s)
    pk_constraint = inspector.get_pk_constraint(table_name)
    primary_keys = pk_constraint.get("constrained_columns", [])

    # 3. Fetch Foreign Key(s)
    raw_fks = inspector.get_foreign_keys(table_name)
    foreign_keys = [
        {
            "constrained_columns": fk.get("constrained_columns", []),
            "referred_table": fk.get("referred_table", ""),
            "referred_columns": fk.get("referred_columns", []),
        }
        for fk in raw_fks
    ]

    # 4. Fetch explicit join relationships from registry
    relationships = KNOWN_RELATIONSHIPS.get(table_name, [])

    # 5. Fetch description + stored vector embedding from table_descriptions
    db_description = TABLE_DESCRIPTIONS.get(table_name, f"Database table {table_name}.")
    stored_embedding = None

    if "table_descriptions" in existing_tables:
        with provider.engine.connect() as conn:
            row = conn.execute(
                text("SELECT description, embedding FROM table_descriptions WHERE table_name = :t"),
                {"t": table_name},
            ).first()
            if row:
                if row[0]:
                    db_description = row[0]
                if row[1]:
                    stored_embedding = row[1]

    return {
        "table_name": table_name,
        "description": db_description,
        "columns": columns,
        "primary_keys": primary_keys,
        "foreign_keys": foreign_keys,
        "relationships": relationships,
        "stored_embedding": stored_embedding,
    }


def fetch_all_db_table_metadata() -> List[Dict[str, Any]]:
    """Fetch metadata for all registered tables in PostgreSQL."""
    provider = DatabaseSessionProvider()
    inspector = inspect(provider.engine)
    db_tables = inspector.get_table_names()

    # Prefer registered tables; fall back to all non-system tables
    target_tables = [t for t in TABLE_DESCRIPTIONS.keys() if t in db_tables]
    if not target_tables:
        target_tables = [t for t in db_tables if not t.startswith("pg_")]

    all_metadata = []
    for table_name in target_tables:
        try:
            meta = get_table_metadata_from_db(table_name)
            all_metadata.append(meta)
        except Exception as exc:
            _log.warning("Skipping table '%s' — metadata fetch failed: %s", table_name, exc)
            continue
    return all_metadata
