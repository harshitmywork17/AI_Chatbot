"""Project-wide named constants. See naming.md / architecture.md conventions."""

from types import MappingProxyType

# --- SQL execution guardrails --------------------------------------------

MAX_RESULT_ROWS = 100
SAMPLE_ROWS_PER_TABLE = 3

# Any of these tokens appearing in a submitted query blocks execution.
FORBIDDEN_SQL_KEYWORDS = (
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "ALTER",
    "TRUNCATE",
    "CREATE",
    "GRANT",
    "REVOKE",
    "MERGE",
    "CALL",
    "EXECUTE",
)

# --- Table registry (name -> human-readable description) ----------------
# Read by the list_available_tables tool so the agent can discover the
# schema without needing raw information_schema access.

TABLE_DESCRIPTIONS = MappingProxyType(
    {
        "sites": "Physical sites and campus details.",
        "room_types": "Template room configurations and expected hardware.",
        "rooms": "Physical conference rooms associated with a site and room type.",
        "devices": "Central AV device hardware instances managed by the platform.",
        "device_capability": "Capability assessment matrix per device model.",
        "baselines": "Golden baseline configurations per device class.",
        "firmware_policy": "Minimum approved firmware levels per device class/model.",
        "events": "Append-only logs for self-healing audits, drifts, and recoveries.",
        "firmware_inventory": "Device scan snapshot history recording firmware versions.",
        "servicenow_tickets": "Incidents created in ServiceNow for device issues.",
        "connector_health": "State logging for third-party connector health checks.",
    }
)
