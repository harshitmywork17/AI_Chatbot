"""SQLAlchemy models for the 11-table AV device platform schema.

Requires the pgcrypto extension for gen_random_uuid():
    CREATE EXTENSION IF NOT EXISTS pgcrypto;
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )


def _created_at() -> Mapped[datetime]:
    return mapped_column(server_default=func.now())


def _updated_at() -> Mapped[datetime]:
    return mapped_column(server_default=func.now())


class RoomType(Base):
    __tablename__ = "room_types"
    __table_args__ = (
        CheckConstraint("jsonb_typeof(expected_device_classes) = 'array'"),
    )

    room_type_id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    expected_device_classes: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()


class Location(Base):
    """Hierarchical location tree: country -> state -> city -> site -> building."""

    __tablename__ = "locations"
    __table_args__ = (
        CheckConstraint("level IN ('country', 'state', 'city', 'site', 'building')"),
    )

    location_id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str | None] = mapped_column(String(50))
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("locations.location_id", ondelete="CASCADE")
    )
    level: Mapped[str] = mapped_column(String(20), nullable=False)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB)
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()


class Room(Base):
    __tablename__ = "rooms"
    __table_args__ = (UniqueConstraint("location_id", "room_number"),)

    room_id: Mapped[uuid.UUID] = _uuid_pk()
    room_number: Mapped[str] = mapped_column(String(50), nullable=False)
    room_name: Mapped[str | None] = mapped_column(String(255))
    room_type_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("room_types.room_type_id", ondelete="SET NULL")
    )
    location_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("locations.location_id", ondelete="RESTRICT"), nullable=False
    )
    floor: Mapped[str | None] = mapped_column(String(50))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()


class Device(Base):
    __tablename__ = "devices"
    __table_args__ = (
        CheckConstraint("manufacturer IN ('Neat', 'Poly', 'Crestron')"),
        CheckConstraint(
            "device_class IN ('video_bar', 'scheduler', 'board', 'phone', 'controller')"
        ),
        CheckConstraint("status IN ('online', 'offline', 'degraded', 'unknown')"),
        CheckConstraint("risk_score >= 0 AND risk_score <= 100"),
    )

    mac: Mapped[str] = mapped_column(String(17), primary_key=True)
    model: Mapped[str] = mapped_column(String(255), nullable=False)
    manufacturer: Mapped[str] = mapped_column(String(50), nullable=False)
    device_class: Mapped[str] = mapped_column(String(50), nullable=False)
    room_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("rooms.room_id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="unknown")
    ip_address: Mapped[str | None] = mapped_column(INET)
    hostname: Mapped[str | None] = mapped_column(String(255))
    serial_number: Mapped[str | None] = mapped_column(String(255), unique=True)
    last_seen: Mapped[datetime | None]
    firmware_version: Mapped[str | None] = mapped_column(String(100))
    risk_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    config_payload: Mapped[dict | None] = mapped_column(JSONB)
    baseline_drift: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    in_scope: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    removal_rationale: Mapped[str | None] = mapped_column(Text)
    removed_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()


class DeviceCapability(Base):
    __tablename__ = "device_capability"

    capability_id: Mapped[uuid.UUID] = _uuid_pk()
    model: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    manufacturer: Mapped[str] = mapped_column(String(50), nullable=False)
    can_query_status: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    can_query_config: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    can_query_firmware: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    can_reboot: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    can_reset_to_baseline: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    can_sleep_wake: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    can_set_config: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    access_model: Mapped[str | None] = mapped_column(String(50))
    mgmt_platform_name: Mapped[str | None] = mapped_column(String(100))
    api_endpoint_pattern: Mapped[str | None] = mapped_column(String(500))
    notes: Mapped[str | None] = mapped_column(Text)
    assessed_at: Mapped[datetime] = mapped_column(server_default=func.now())
    assessed_by: Mapped[str | None] = mapped_column(String(255))


class Baseline(Base):
    __tablename__ = "baselines"
    __table_args__ = (
        UniqueConstraint("device_class", "version"),
        Index(
            "ix_baselines_one_current_per_class",
            "device_class",
            unique=True,
            postgresql_where=text("is_current"),
        ),
    )

    baseline_id: Mapped[uuid.UUID] = _uuid_pk()
    device_class: Mapped[str] = mapped_column(String(50), nullable=False)
    config_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class FirmwarePolicy(Base):
    __tablename__ = "firmware_policy"

    policy_id: Mapped[uuid.UUID] = _uuid_pk()
    device_class: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str | None] = mapped_column(String(255))
    approved_minimum: Mapped[str] = mapped_column(String(100), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    effective_from: Mapped[datetime] = mapped_column(server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('drift', 'remediate', 'escalate', 'ticket', 'recovery', "
            "'baseline_capture')"
        ),
        CheckConstraint(
            "outcome IN ('success', 'failed', 'escalated', 'skipped', 'pending_approval')"
        ),
        CheckConstraint("ai_action IN ('remediate', 'escalate', 'hold')"),
        CheckConstraint("ai_confidence >= 0 AND ai_confidence <= 1"),
    )

    event_id: Mapped[uuid.UUID] = _uuid_pk()
    device_mac: Mapped[str] = mapped_column(
        ForeignKey("devices.mac", ondelete="RESTRICT"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    outcome: Mapped[str | None] = mapped_column(String(50))
    before_state: Mapped[dict | None] = mapped_column(JSONB)
    after_state: Mapped[dict | None] = mapped_column(JSONB)
    drift_fields: Mapped[dict | None] = mapped_column(JSONB)
    servicenow_ticket_id: Mapped[str | None] = mapped_column(String(100))
    baseline_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("baselines.baseline_id"))
    ai_decision_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    ai_action: Mapped[str | None] = mapped_column(String(20))
    ai_confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    initiated_by: Mapped[str] = mapped_column(String(100), nullable=False, server_default="system")
    remediation_duration_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class FirmwareInventory(Base):
    __tablename__ = "firmware_inventory"
    __table_args__ = (
        CheckConstraint("recommendation_priority IN ('critical', 'high', 'medium', 'low', 'none')"),
    )

    inventory_id: Mapped[uuid.UUID] = _uuid_pk()
    device_mac: Mapped[str] = mapped_column(
        ForeignKey("devices.mac", ondelete="RESTRICT"), nullable=False
    )
    firmware_version: Mapped[str] = mapped_column(String(100), nullable=False)
    approved_minimum: Mapped[str | None] = mapped_column(String(100))
    is_below_baseline: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    recommendation_priority: Mapped[str | None] = mapped_column(String(20))
    recommendation_notes: Mapped[str | None] = mapped_column(Text)
    scanned_at: Mapped[datetime] = mapped_column(server_default=func.now())


class ServiceNowTicket(Base):
    __tablename__ = "servicenow_tickets"
    __table_args__ = (
        CheckConstraint(
            "ticket_type IN ('self_heal_failure', 'no_control_capability', "
            "'firmware_drift', 'manual')"
        ),
    )

    ticket_id: Mapped[uuid.UUID] = _uuid_pk()
    servicenow_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    device_mac: Mapped[str | None] = mapped_column(ForeignKey("devices.mac", ondelete="SET NULL"))
    ticket_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, server_default="open")
    priority: Mapped[str | None] = mapped_column(String(20))
    short_description: Mapped[str | None] = mapped_column(Text)
    created_by_platform: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    opened_at: Mapped[datetime] = mapped_column(server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())
    closed_at: Mapped[datetime | None]


class ConnectorHealth(Base):
    __tablename__ = "connector_health"
    __table_args__ = (
        CheckConstraint("status IN ('healthy', 'degraded', 'down')"),
        CheckConstraint("circuit_breaker_state IN ('closed', 'open', 'half_open')"),
    )

    health_id: Mapped[uuid.UUID] = _uuid_pk()
    connector_name: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    circuit_breaker_state: Mapped[str | None] = mapped_column(String(20))
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    failure_reason: Mapped[str | None] = mapped_column(Text)
    last_success: Mapped[datetime | None]
    last_checked: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
