"""Seeding logic: creates the schema and populates it with dummy data.

Invoked via the thin `app/seed.py` entrypoint (python -m app.seed).
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import DatabaseSessionProvider
from app.models.av_platform import (
    Base,
    Baseline,
    ConnectorHealth,
    Device,
    DeviceCapability,
    Event,
    FirmwareInventory,
    FirmwarePolicy,
    Location,
    Room,
    RoomType,
    ServiceNowTicket,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)

_NOW = datetime.now(timezone.utc)


def _seed_locations(session: Session) -> dict[str, Location]:
    usa = Location(name="USA", code="US", level="country")
    session.add(usa)
    session.flush()

    idaho = Location(name="Idaho", code="ID", level="state", parent_id=usa.location_id)
    session.add(idaho)
    session.flush()

    boise = Location(name="Boise", level="city", parent_id=idaho.location_id)
    session.add(boise)
    session.flush()

    site = Location(
        name="Boise HQ",
        code="BOI-01",
        level="site",
        parent_id=boise.location_id,
        metadata_={"region": "AMER", "address": "800 W Chinden Blvd, Boise, ID"},
    )
    session.add(site)
    session.flush()

    main = Location(
        name="Main", code="MAIN", level="building", parent_id=site.location_id,
        metadata_={"floors": 3},
    )
    annex = Location(
        name="Annex", code="ANNEX", level="building", parent_id=site.location_id,
        metadata_={"floors": 1},
    )
    session.add_all([main, annex])
    session.flush()

    return {"Main": main, "Annex": annex}


def _seed_room_types(session: Session) -> dict[str, RoomType]:
    room_types = [
        RoomType(
            name="Huddle Room",
            description="Small 2-4 person room with a single video bar.",
            expected_device_classes=["video_bar", "scheduler"],
        ),
        RoomType(
            name="Standard Conference Room",
            description="Mid-size room with a video bar, scheduler, and phone.",
            expected_device_classes=["video_bar", "scheduler", "phone"],
        ),
        RoomType(
            name="Executive Boardroom",
            description="Large room with a board, controller, and dual video bars.",
            expected_device_classes=["video_bar", "board", "controller"],
        ),
    ]
    session.add_all(room_types)
    session.flush()
    return {room_type.name: room_type for room_type in room_types}


def _seed_rooms(
    session: Session, buildings: dict[str, Location], room_types: dict[str, RoomType]
) -> dict[str, Room]:
    rooms = [
        Room(
            room_number="EXEC-1",
            room_name="Executive Suite",
            location_id=buildings["Main"].location_id,
            room_type_id=room_types["Executive Boardroom"].room_type_id,
            floor="3",
        ),
        Room(
            room_number="101",
            location_id=buildings["Main"].location_id,
            room_type_id=room_types["Standard Conference Room"].room_type_id,
            floor="1",
        ),
        Room(
            room_number="205",
            location_id=buildings["Main"].location_id,
            room_type_id=room_types["Standard Conference Room"].room_type_id,
            floor="2",
        ),
        Room(
            room_number="HUD-A",
            room_name="Huddle A",
            location_id=buildings["Annex"].location_id,
            room_type_id=room_types["Huddle Room"].room_type_id,
            floor="1",
        ),
        Room(
            room_number="HUD-B",
            room_name="Huddle B",
            location_id=buildings["Annex"].location_id,
            room_type_id=room_types["Huddle Room"].room_type_id,
            floor="1",
        ),
        Room(
            room_number="AUD-1",
            room_name="Auditorium",
            location_id=buildings["Main"].location_id,
            room_type_id=room_types["Executive Boardroom"].room_type_id,
            floor="1",
        ),
    ]
    session.add_all(rooms)
    session.flush()
    return {room.room_number: room for room in rooms}


def _seed_devices(session: Session, rooms: dict[str, Room]) -> list[Device]:
    # (mac, model, manufacturer, device_class, room_name, status, firmware, risk_score, drift)
    device_specs = [
        (
            "00:1A:2B:00:00:01",
            "Neat Bar Gen 2",
            "Neat",
            "video_bar",
            "Executive Suite",
            "online",
            "1.8.2",
            12.5,
            False,
        ),
        (
            "00:1A:2B:00:00:02",
            "Neat Board",
            "Neat",
            "board",
            "Executive Suite",
            "online",
            "1.8.2",
            8.0,
            False,
        ),
        (
            "00:1A:2B:00:00:03",
            "Neat Pad",
            "Neat",
            "controller",
            "Executive Suite",
            "online",
            "2.1.0",
            5.0,
            False,
        ),
        (
            "00:1A:2B:00:00:04",
            "Poly Studio X50",
            "Poly",
            "video_bar",
            "Room 101",
            "online",
            "1.8.0",
            22.0,
            True,
        ),
        (
            "00:1A:2B:00:00:05",
            "Poly TC8",
            "Poly",
            "scheduler",
            "Room 101",
            "online",
            "3.4.1",
            4.0,
            False,
        ),
        (
            "00:1A:2B:00:00:06",
            "Poly Trio",
            "Poly",
            "phone",
            "Room 101",
            "offline",
            "5.9.2",
            45.0,
            False,
        ),
        (
            "00:1A:2B:00:00:07",
            "Poly Studio X30",
            "Poly",
            "video_bar",
            "Room 205",
            "online",
            "1.8.0",
            30.5,
            True,
        ),
        (
            "00:1A:2B:00:00:08",
            "Poly TC8",
            "Poly",
            "scheduler",
            "Room 205",
            "online",
            "3.4.1",
            6.0,
            False,
        ),
        (
            "00:1A:2B:00:00:09",
            "Poly Trio",
            "Poly",
            "phone",
            "Room 205",
            "degraded",
            "5.9.0",
            60.0,
            False,
        ),
        (
            "00:1A:2B:00:00:0A",
            "Neat Bar Gen 2",
            "Neat",
            "video_bar",
            "Huddle A",
            "online",
            "1.8.0",
            18.0,
            False,
        ),
        (
            "00:1A:2B:00:00:0B",
            "Neat Pad",
            "Neat",
            "scheduler",
            "Huddle A",
            "online",
            "2.1.0",
            3.0,
            False,
        ),
        (
            "00:1A:2B:00:00:0C",
            "Neat Bar Gen 2",
            "Neat",
            "video_bar",
            "Huddle B",
            "online",
            "1.8.2",
            10.0,
            False,
        ),
        (
            "00:1A:2B:00:00:0D",
            "Neat Pad",
            "Neat",
            "scheduler",
            "Huddle B",
            "unknown",
            "2.0.5",
            70.0,
            False,
        ),
        (
            "00:1A:2B:00:00:0E",
            "Crestron Mercury",
            "Crestron",
            "video_bar",
            "Auditorium",
            "online",
            "2.4.0",
            15.0,
            False,
        ),
        (
            "00:1A:2B:00:00:0F",
            "Crestron UC-Engine",
            "Crestron",
            "controller",
            "Auditorium",
            "online",
            "4.2.1",
            9.0,
            False,
        ),
    ]
    room_number_by_label = {
        "Executive Suite": "EXEC-1",
        "Room 101": "101",
        "Room 205": "205",
        "Huddle A": "HUD-A",
        "Huddle B": "HUD-B",
        "Auditorium": "AUD-1",
    }
    devices = [
        Device(
            mac=mac,
            model=model,
            manufacturer=manufacturer,
            device_class=device_class,
            room_id=rooms[room_number_by_label[room_label]].room_id,
            status=status,
            firmware_version=firmware,
            risk_score=risk_score,
            baseline_drift=drift,
            last_seen=_NOW - timedelta(minutes=5),
        )
        for mac, model, manufacturer, device_class, room_label, status, firmware, risk_score, drift in device_specs
    ]
    session.add_all(devices)
    session.flush()
    return devices


def _seed_device_capabilities(session: Session, devices: list[Device]) -> None:
    access_model_by_manufacturer = {
        "Neat": "neat_pulse",
        "Poly": "poly_lens",
        "Crestron": "xio_cloud",
    }
    seen_models: set[str] = set()
    capabilities = []
    for device in devices:
        if device.model in seen_models:
            continue
        seen_models.add(device.model)
        capabilities.append(
            DeviceCapability(
                model=device.model,
                manufacturer=device.manufacturer,
                can_query_status=True,
                can_query_config=True,
                can_query_firmware=True,
                can_reboot=device.device_class in ("video_bar", "controller"),
                can_reset_to_baseline=device.device_class == "video_bar",
                can_sleep_wake=device.device_class == "video_bar",
                can_set_config=device.device_class in ("video_bar", "controller"),
                access_model=access_model_by_manufacturer[device.manufacturer],
                mgmt_platform_name=access_model_by_manufacturer[device.manufacturer],
                assessed_by="poc-seed",
            )
        )
    session.add_all(capabilities)


def _seed_baselines(session: Session) -> dict[str, Baseline]:
    baselines = [
        Baseline(
            device_class="video_bar",
            config_payload={"volume": 50, "auto_answer": False, "resolution": "1080p"},
            version=1,
            is_current=True,
            created_by="poc-seed",
        ),
        Baseline(
            device_class="board",
            config_payload={"brightness": 70, "auto_answer": False},
            version=1,
            is_current=True,
            created_by="poc-seed",
        ),
    ]
    session.add_all(baselines)
    session.flush()
    return {baseline.device_class: baseline for baseline in baselines}


def _seed_firmware_policy(session: Session) -> None:
    session.add(
        FirmwarePolicy(
            device_class="video_bar",
            model=None,
            approved_minimum="1.8.2",
            notes="Minimum firmware approved after Q2 security patch.",
            created_by="poc-seed",
        )
    )


def _seed_events(session: Session, devices: list[Device], baselines: dict[str, Baseline]) -> None:
    drifted_macs = [device.mac for device in devices if device.baseline_drift]

    events = []
    for mac in drifted_macs:
        events.append(
            Event(
                device_mac=mac,
                event_type="drift",
                outcome=None,
                before_state={"volume": 50},
                after_state={"volume": 80},
                drift_fields={"volume": {"expected": 50, "actual": 80}},
                baseline_id=baselines["video_bar"].baseline_id,
                ai_action="remediate",
                ai_confidence=0.91,
                initiated_by="drift_scanner",
            )
        )

    remediation_macs = [device.mac for device in devices if device.device_class == "video_bar"][:5]
    for mac in remediation_macs:
        events.append(
            Event(
                device_mac=mac,
                event_type="remediate",
                outcome="success",
                before_state={"volume": 80},
                after_state={"volume": 50},
                baseline_id=baselines["video_bar"].baseline_id,
                ai_action="remediate",
                ai_confidence=0.95,
                initiated_by="self_heal_worker",
                remediation_duration_ms=1200,
            )
        )
    session.add_all(events)


def _seed_firmware_inventory(session: Session, devices: list[Device]) -> None:
    below_baseline_devices = [d for d in devices if d.firmware_version == "1.8.0"][:3]
    inventory_rows = [
        FirmwareInventory(
            device_mac=device.mac,
            firmware_version=device.firmware_version,
            approved_minimum="1.8.2",
            is_below_baseline=True,
            recommendation_priority="high",
            recommendation_notes="Upgrade to 1.8.2 to close known drift-detection gap.",
        )
        for device in below_baseline_devices
    ]
    session.add_all(inventory_rows)


def _seed_tickets(session: Session, devices: list[Device]) -> None:
    ticket_devices = devices[:4]
    tickets = [
        ServiceNowTicket(
            servicenow_id="INC0012345",
            device_mac=ticket_devices[0].mac,
            ticket_type="self_heal_failure",
            status="open",
            priority="high",
            short_description="Auto-heal failed to restore baseline volume level.",
        ),
        ServiceNowTicket(
            servicenow_id="INC0012346",
            device_mac=ticket_devices[1].mac,
            ticket_type="firmware_drift",
            status="open",
            priority="medium",
            short_description="Device running below approved firmware minimum.",
        ),
        ServiceNowTicket(
            servicenow_id="INC0012347",
            device_mac=ticket_devices[2].mac,
            ticket_type="no_control_capability",
            status="closed",
            priority="low",
            short_description="Device lacked config API access, resolved via manual reset.",
            closed_at=_NOW - timedelta(days=2),
        ),
        ServiceNowTicket(
            servicenow_id="INC0012348",
            device_mac=ticket_devices[3].mac,
            ticket_type="manual",
            status="closed",
            priority="low",
            short_description="Manual firmware upgrade requested by site technician.",
            closed_at=_NOW - timedelta(days=5),
        ),
    ]
    session.add_all(tickets)


def _seed_connector_health(session: Session) -> None:
    connectors = [
        ConnectorHealth(
            connector_name="neat_pulse",
            status="healthy",
            circuit_breaker_state="closed",
            failure_count=0,
            last_success=_NOW,
            last_checked=_NOW,
        ),
        ConnectorHealth(
            connector_name="poly_lens",
            status="degraded",
            circuit_breaker_state="half_open",
            failure_count=3,
            failure_reason="Intermittent 503 responses from Poly Lens API.",
            last_success=_NOW - timedelta(hours=1),
            last_checked=_NOW,
        ),
        ConnectorHealth(
            connector_name="xio_cloud",
            status="healthy",
            circuit_breaker_state="closed",
            failure_count=0,
            last_success=_NOW,
            last_checked=_NOW,
        ),
    ]
    session.add_all(connectors)


def seed_database() -> None:
    """Create the schema (if missing) and populate it with dummy data.

    No-ops if the `locations` table already has rows, so the script is safe to
    run more than once.
    """
    provider = DatabaseSessionProvider()
    with provider.engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
    Base.metadata.create_all(provider.engine)

    with provider.session() as session:
        if session.query(Location).first() is not None:
            logger.info("Database already seeded, skipping.")
            return

        buildings = _seed_locations(session)
        room_types = _seed_room_types(session)
        rooms = _seed_rooms(session, buildings, room_types)
        devices = _seed_devices(session, rooms)
        _seed_device_capabilities(session, devices)
        baselines = _seed_baselines(session)
        _seed_firmware_policy(session)
        _seed_events(session, devices, baselines)
        _seed_firmware_inventory(session, devices)
        _seed_tickets(session, devices)
        _seed_connector_health(session)

    logger.info("Seed complete: 1 site, 6 rooms, 15 devices, dummy events/tickets seeded.")
