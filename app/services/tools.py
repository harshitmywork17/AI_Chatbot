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
from app.services.sql_guard import assert_select_only


def _to_json_safe(value: Any) -> Any:
    """Convert a single DB cell value into a JSON-serializable primitive."""
    if isinstance(value, (uuid.UUID, Decimal)):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def list_available_tables() -> dict[str, str]:
    """Return the registered table names and a one-line description of each."""
    return dict(TABLE_DESCRIPTIONS)


def get_table_schema(table_name: str) -> dict[str, Any]:
    """Return column definitions and a few sample rows for one registered table.

    Raises ValueError if `table_name` is not one of the registered tables, so
    the agent cannot probe arbitrary database objects.
    """
    if table_name not in TABLE_DESCRIPTIONS:
        raise ValueError(f"Unknown table '{table_name}'. Call list_available_tables first.")

    provider = DatabaseSessionProvider()
    inspector = inspect(provider.engine)
    columns = [
        {"name": column["name"], "type": str(column["type"]), "nullable": column["nullable"]}
        for column in inspector.get_columns(table_name)
    ]

    with provider.engine.connect() as connection:
        sample_rows = (
            connection.execute(
                text(
                    f'SELECT * FROM "{table_name}" LIMIT :limit'
                ),  # noqa: S608 - table_name whitelisted above
                {"limit": SAMPLE_ROWS_PER_TABLE},
            )
            .mappings()
            .all()
        )

    return {
        "table_name": table_name,
        "columns": columns,
        "sample_rows": [
            {key: _to_json_safe(value) for key, value in row.items()} for row in sample_rows
        ],
    }


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
            fn=list_available_tables,
            name="list_available_tables",
            description="List every registered table and a short description of what it holds.",
        ),
        FunctionTool.from_defaults(
            fn=get_table_schema,
            name="get_table_schema",
            description=(
                "Get column names/types and a few sample rows for one registered table. "
                "Call this before writing SQL that references the table."
            ),
        ),
        FunctionTool.from_defaults(
            fn=execute_sql_query,
            name="execute_sql_query",
            description=(
                "Run a single read-only SELECT statement against the database and return "
                "the resulting rows. Any non-SELECT statement is rejected."
            ),
        ),
    ]
    return tools
