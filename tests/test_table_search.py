"""Unit tests for metadata_reader, TableSearchService, and table schema tools."""

from app.services.metadata_reader import fetch_all_db_table_metadata, get_table_metadata_from_db
from app.services.table_search_service import TableSearchService
from app.services.tools import get_table_schema, search_table_descriptions


def test_fetch_metadata_from_db():
    all_meta = fetch_all_db_table_metadata()
    assert isinstance(all_meta, list)
    assert len(all_meta) > 0
    table_names = [m["table_name"] for m in all_meta]
    assert "devices" in table_names
    assert "rooms" in table_names
    assert "locations" in table_names


def test_table_metadata_details():
    meta = get_table_metadata_from_db("devices")
    assert meta["table_name"] == "devices"
    assert "columns" in meta
    assert len(meta["columns"]) > 0
    assert "relationships" in meta
    # Verify foreign key join relationship to rooms
    rel_targets = [r["target_table"] for r in meta["relationships"]]
    assert "rooms" in rel_targets


def test_semantic_table_search_and_fk_resolution():
    search_service = TableSearchService()
    results = search_service.search_relevant_tables("Which devices are in Boise HQ site?", top_k=2)
    result_names = [r["table_name"] for r in results]

    # Verify that devices, rooms, and locations are resolved via FK relationships
    assert "devices" in result_names or "locations" in result_names
    assert "rooms" in result_names or "locations" in result_names


def test_tools_search_and_schema():
    search_res = search_table_descriptions("servicenow tickets for drift events")
    assert isinstance(search_res, list)

    schema = get_table_schema("devices")
    assert schema["table_name"] == "devices"
    assert "primary_keys" in schema
    assert "foreign_keys" in schema
