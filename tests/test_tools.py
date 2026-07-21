import uuid
from datetime import datetime
from decimal import Decimal

import pytest

from app.core.constants import TABLE_DESCRIPTIONS
from app.services.sql_guard import UnsafeSqlQueryError
from app.services.tools import (
    _to_json_safe,
    execute_sql_query,
    get_table_schema,
    list_available_tables,
)


def test_list_available_tables_returns_all_registered_tables():
    tables = list_available_tables()
    assert set(tables.keys()) == set(TABLE_DESCRIPTIONS.keys())
    assert all(isinstance(description, str) and description for description in tables.values())


def test_get_table_schema_rejects_unknown_table():
    with pytest.raises(ValueError, match="Unknown table"):
        get_table_schema("not_a_real_table")


def test_execute_sql_query_rejects_unsafe_sql_before_touching_the_database():
    with pytest.raises(UnsafeSqlQueryError):
        execute_sql_query('DROP TABLE "devices"')


@pytest.mark.parametrize(
    "value,expected",
    [
        (uuid.UUID("12345678-1234-5678-1234-567812345678"), "12345678-1234-5678-1234-567812345678"),
        (Decimal("12.50"), "12.50"),
        (datetime(2026, 1, 1, 12, 30), "2026-01-01T12:30:00"),
        (42, 42),
        ("plain string", "plain string"),
        (None, None),
    ],
)
def test_to_json_safe_converts_non_json_native_types(value, expected):
    assert _to_json_safe(value) == expected
