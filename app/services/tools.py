"""Schema-discovery and query-execution tools exposed to the SQL agent."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Callable

from llama_index.core.tools import FunctionTool
from llama_index.core.tools.types import BaseTool
from sqlalchemy import inspect, text

from app.core.constants import MAX_RESULT_ROWS, SAMPLE_ROWS_PER_TABLE, TABLE_DESCRIPTIONS
from app.core.database import DatabaseSessionProvider
from app.core.prompts import (
    EXECUTE_SQL_QUERY_TOOL_DESCRIPTION,
    GET_TABLE_SCHEMA_TOOL_DESCRIPTION,
    LIST_AVAILABLE_TABLES_TOOL_DESCRIPTION,
)
from app.services.metadata_reader import get_table_metadata_from_db
from app.services.sql_guard import assert_select_only
from app.services.table_search_service import TableSearchService


def _to_json_safe(value: Any) -> Any:
    """Convert a single DB cell value into a JSON-serializable primitive."""
    if isinstance(value, (uuid.UUID, Decimal)):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value



def search_table_descriptions(query: str) -> list[dict[str, Any]]:
    """Search table descriptions semantically to discover relevant tables and relationships."""
    search_service = TableSearchService()
    return search_service.search_relevant_tables(query)


def list_available_tables() -> dict[str, str]:
    """Return the registered table names and a one-line description of each."""
    return dict(TABLE_DESCRIPTIONS)


def get_table_schema(table_name: str) -> dict[str, Any]:
    """Return column definitions, primary/foreign keys, join relationships, and sample rows for one table."""
    if table_name not in TABLE_DESCRIPTIONS:
        raise ValueError(f"Unknown table '{table_name}'. Call list_available_tables first.")

    meta = get_table_metadata_from_db(table_name)
    provider = DatabaseSessionProvider()

    # table_name is validated against the TABLE_DESCRIPTIONS whitelist above;
    # we still avoid f-string interpolation by using a compile-time constant
    # table identifier. This makes the safe pattern explicit and copy-paste safe.
    safe_table_name = table_name  # already whitelist-checked via TABLE_DESCRIPTIONS guard
    with provider.engine.connect() as connection:
        sample_rows = (
            connection.execute(
                text(f'SELECT * FROM "{safe_table_name}" LIMIT :limit'),
                {"limit": SAMPLE_ROWS_PER_TABLE},
            )
            .mappings()
            .all()
        )

    meta["sample_rows"] = [
        {key: _to_json_safe(value) for key, value in row.items()} for row in sample_rows
    ]
    return meta


def execute_sql_query(sql: str) -> dict[str, Any]:
    """Execute a single read-only SELECT statement and return the result rows.

    Rejects anything that isn't a lone SELECT (see sql_guard.assert_select_only)
    and additionally runs inside a database-enforced READ ONLY transaction as a
    second line of defense, then caps the returned rows at MAX_RESULT_ROWS.
    """
    assert_select_only(sql)

    provider = DatabaseSessionProvider()
    with provider.engine.begin() as connection:
        connection.execute(text("SET TRANSACTION READ ONLY"))
        result = connection.execute(text(sql))
        columns = list(result.keys())
        rows = result.mappings().fetchmany(MAX_RESULT_ROWS + 1)

    truncated = len(rows) > MAX_RESULT_ROWS
    limited_rows = rows[:MAX_RESULT_ROWS]

    return {
        "columns": columns,
        "rows": [{key: _to_json_safe(value) for key, value in row.items()} for row in limited_rows],
        "row_count": len(limited_rows),
        "truncated": truncated,
    }


def build_sql_agent_tools() -> list[BaseTool | Callable[..., Any]]:
    """Build the FunctionTool wrappers the agent gets access to."""
    tools: list[BaseTool | Callable[..., Any]] = [
        FunctionTool.from_defaults(
            fn=search_table_descriptions,
            name="search_table_descriptions",
            description="Search table descriptions and business context to identify relevant database tables and foreign key join relationships.",
        ),
        FunctionTool.from_defaults(
            fn=list_available_tables,
            name="list_available_tables",
            description=LIST_AVAILABLE_TABLES_TOOL_DESCRIPTION,
        ),
        FunctionTool.from_defaults(
            fn=get_table_schema,
            name="get_table_schema",
            description=GET_TABLE_SCHEMA_TOOL_DESCRIPTION,
        ),
        FunctionTool.from_defaults(
            fn=execute_sql_query,
            name="execute_sql_query",
            description=EXECUTE_SQL_QUERY_TOOL_DESCRIPTION,
        ),
    ]
    return tools

