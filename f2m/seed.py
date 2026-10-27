"""First-run data import and demo records.

The desktop app embedded the company's Daily Customer Record workbook inside the
Python file. The web version keeps that data in a small JSON file and imports it
once, using deduplication so restarts and redeploys never create duplicates.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from flask import current_app
from sqlalchemy import func, select

from .models import (
    Appointment,
    Customer,
    FeedbackConcern,
    Notification,
    ServiceHistory,
    ServiceRequest,
    SystemMeta,
    Vehicle,
    Visit,
    db,
)
from .timeutil import now_str, today_iso, tomorrow_iso

SEED_VERSION = "1"
DATA_FILE = Path(__file__).resolve().parent / "data" / "customer_records.json"


def seed_data_file() -> Path:
    """Return the workbook JSON path, honoring the ``SEED_DATA_FILE`` override.

    The company dataset contains customer names and plate numbers, so it is not
    committed to the repository. Deployments can mount it as a Render secret file
    and point this variable at the mounted path.
    """
    override = os.environ.get("SEED_DATA_FILE", "").strip()
    return Path(override).expanduser() if override else DATA_FILE


DEMO_CUSTOMERS = [
    ("MARIA L. SANTOS", "KCA 2147", "TOYOTA VIOS", "QUEZON, BUKIDNON", "JUN REYES"),
    ("JEROME P. CRUZ", "KBD 5832", "MITSUBISHI MONTERO", "MARAMAG, BUKIDNON", "MARK DELA CRUZ"),
    ("ANGELICA R. FLORES", "KCE 7319", "HONDA CITY", "VALENCIA CITY, BUKIDNON", "JUN REYES"),
    ("CARLO M. REYES", "KAG 9041", "TOYOTA HILUX", "QUEZON, BUKIDNON", "MARK DELA CRUZ"),
    ("ROSE ANN GARCIA", "KAA 6185", "FORD RANGER", "KIBAWE, BUKIDNON", "JUN REYES"),
    ("DANIEL T. NAVARRO", "KCL 4420", "ISUZU D-MAX", "MALAYBALAY CITY", "MARK DELA CRUZ"),
]


def _load_records() -> tuple[list[list[str]], bool]:
    """Load the workbook rows and report whether a usable file was read."""
    path = seed_data_file()
    if not path.exists():
        current_app.logger.warning(
            "Customer record data file not found: %s. The app will start without "
            "imported visits. Set SEED_DATA_FILE to a mounted JSON file to import "
            "them later.",
            path,
        )
        return [], False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        current_app.logger.error("Could not read %s: %s", path, exc)
        return [], False
    if not isinstance(payload, list):
        current_app.logger.error("Customer record file %s is not a JSON array.", path)
        return [], False
    return payload, True


def _text(value, limit: int) -> str:
    return str(value or "").strip()[:limit]


def _import_visits(records: list[list[str]]) -> int:
    # The source workbook can contain several tables for one date, so the same
    # record number may legitimately appear more than once. Deduplicate on the
    # complete row instead of on (date, record_no).
    existing = {
        tuple(str(value or "").strip() for value in row)
        for row in db.session.execute(
            select(
                Visit.visit_date,
                Visit.record_no,
                Visit.plate,
                Visit.model,
                Visit.customer_name,
                Visit.address,
                Visit.technician,
            )
        ).all()
    }
    rows: list[Visit] = []
    for record in records:
        if not isinstance(record, (list, tuple)) or len(record) < 7:
            continue
        visit_date = str(record[0] or "").strip()[:10]
        record_no = str(record[1] or "").strip()
        if not visit_date or not record_no.isdigit():
            continue
        values = (
            visit_date,
            record_no,
            _text(record[2], 50),
            _text(record[3], 120),
            _text(record[4], 200),
            _text(record[5], 255),
            _text(record[6], 120),
        )
        if values in existing:
            continue
        rows.append(
            Visit(
                visit_date=values[0],
                record_no=values[1],
                plate=values[2],
                model=values[3],
                customer_name=values[4],
                address=values[5],
                technician=values[6],
            )
        )
        existing.add(values)
    if rows:
        db.session.add_all(rows)
        db.session.commit()
    return len(rows)


def _customer_key(name, plate, address) -> tuple[str, str, str]:
    return (
        _text(name, 200).upper(),
        _text(plate, 50).upper(),
        _text(address, 255).upper(),
    )


def _import_customers(records: list[list[str]]) -> int:
    existing = {
        _customer_key(row[0], row[1], row[2])
        for row in db.session.execute(
            select(Customer.name, Customer.plate, Customer.address)
        ).all()
    }
    rows: list[Customer] = []
    for record in records:
        if not isinstance(record, (list, tuple)) or len(record) < 7:
            continue
        record_no = str(record[1] or "").strip()
        name = _text(record[4], 200)
        if not record_no.isdigit() or not name:
            continue
        key = _customer_key(name, record[2], record[5])
        if key in existing:
            continue
        rows.append(
            Customer(
                name=name,
                plate=_text(record[2], 50),
                model=_text(record[3], 120),
                address=_text(record[5], 255),
                technician=_text(record[6], 120),
                created_at=now_str(),
            )
        )
        existing.add(key)
    if rows:
        db.session.add_all(rows)
        db.session.commit()
    return len(rows)


def _import_vehicles() -> int:
    existing = {
        (row[0], row[1] or "N/A", row[2] or "")
        for row in db.session.execute(
            select(Vehicle.customer_id, Vehicle.plate, Vehicle.model)
        ).all()
    }
    added = 0
    for customer in db.session.scalars(select(Customer).order_by(Customer.id)).all():
        plate = (customer.plate or "").strip()
        model = (customer.model or "").strip()
        if not plate and not model:
            continue
        key = (customer.id, plate or "N/A", model)
        if key in existing:
            continue
        db.session.add(
            Vehicle(
                customer_id=customer.id,
                plate=plate or "N/A",
                model=model,
                technician=customer.technician or "",
                status="Active",
                created_at=customer.created_at or now_str(),
            )
        )
        existing.add(key)
        added += 1
    if added:
        db.session.commit()
    return added


def _find_demo_customer(name: str) -> Customer | None:
    return db.session.scalar(
        select(Customer)
        .where(func.lower(func.trim(Customer.name)) == name.strip().lower())
        .order_by(Customer.id.asc())
        .limit(1)
    )


def _seed_demo_records() -> dict[str, int]:
    stats = {
        "demo_customers": 0,
        "demo_appointments": 0,
        "demo_requests": 0,
        "demo_feedback": 0,
        "demo_history": 0,
        "demo_notifications": 0,
        "demo_visits": 0,
    }
    demo_ids: dict[str, int] = {}
    for name, plate, model, address, technician in DEMO_CUSTOMERS:
        customer = _find_demo_customer(name)
        if customer is None:
            customer = Customer(
                name=name,
                plate=plate,
                model=model,
                address=address,
                technician=technician,
                created_at=now_str(),
            )
            db.session.add(customer)
            db.session.flush()
            db.session.add(
                Vehicle(
                    customer_id=customer.id,
                    plate=plate,
                    model=model,
                    technician=technician,
                    status="Active",
                    created_at=now_str(),
                )
            )
            stats["demo_customers"] += 1
        demo_ids[name] = customer.id
    db.session.commit()

    today = today_iso()
    tomorrow = tomorrow_iso()
    demo_appointments = [
        ("MARIA L. SANTOS", "Tire Change", today, "09:00", "Scheduled"),
        ("JEROME P. CRUZ", "Wheel Alignment", today, "10:30", "Scheduled"),
        ("ANGELICA R. FLORES", "Tire Rotation", today, "13:00", "Scheduled"),
        ("CARLO M. REYES", "Oil Change", tomorrow, "09:30", "Scheduled"),
    ]
    for name, service, appointment_date, appointment_time, status in demo_appointments:
        customer_id = demo_ids[name]
        exists = db.session.scalar(
            select(Appointment.id).where(
                Appointment.customer_id == customer_id,
                Appointment.service == service,
                Appointment.appointment_date == appointment_date,
                Appointment.appointment_time == appointment_time,
            )
        )
        if not exists:
            db.session.add(
                Appointment(
                    customer_id=customer_id,
                    service=service,
                    appointment_date=appointment_date,
                    appointment_time=appointment_time,
                    status=status,
                    created_at=now_str(),
                )
            )
            stats["demo_appointments"] += 1

    demo_requests = [
        ("ROSE ANN GARCIA", "Brake Inspection", today, "Pending", "JUN REYES", "Customer requested brake inspection."),
        ("DANIEL T. NAVARRO", "Tire Replacement", today, "In Progress", "MARK DELA CRUZ", "Checking tire size and availability."),
    ]
    for name, service, request_date, status, technician, notes in demo_requests:
        customer_id = demo_ids[name]
        exists = db.session.scalar(
            select(ServiceRequest.id).where(
                ServiceRequest.customer_id == customer_id,
                ServiceRequest.service == service,
                ServiceRequest.request_date == request_date,
            )
        )
        if not exists:
            db.session.add(
                ServiceRequest(
                    customer_id=customer_id,
                    service=service,
                    request_date=request_date,
                    status=status,
                    technician=technician,
                    notes=notes,
                    created_at=now_str(),
                )
            )
            stats["demo_requests"] += 1

    demo_feedback = [
        ("MARIA L. SANTOS", "Customer asked for an update on tire availability."),
        ("ANGELICA R. FLORES", "Customer requested an earlier service schedule."),
    ]
    for name, concern in demo_feedback:
        customer_id = demo_ids[name]
        exists = db.session.scalar(
            select(FeedbackConcern.id).where(
                FeedbackConcern.customer_id == customer_id,
                FeedbackConcern.concern == concern,
            )
        )
        if not exists:
            db.session.add(
                FeedbackConcern(
                    customer_id=customer_id,
                    concern=concern,
                    status="Pending",
                    created_at=now_str(),
                )
            )
            stats["demo_feedback"] += 1

    demo_history = [
        ("JEROME P. CRUZ", "Wheel Alignment", today, "MARK DELA CRUZ", "Completed", "Alignment completed successfully."),
        ("CARLO M. REYES", "Oil Change", _days_ago(7), "JUN REYES", "Completed", "Regular maintenance service."),
    ]
    for name, service, service_date, technician, status, notes in demo_history:
        customer_id = demo_ids[name]
        vehicle_id = db.session.scalar(
            select(Vehicle.id)
            .where(Vehicle.customer_id == customer_id)
            .order_by(Vehicle.id.asc())
            .limit(1)
        )
        if not vehicle_id:
            continue
        exists = db.session.scalar(
            select(ServiceHistory.id).where(
                ServiceHistory.customer_id == customer_id,
                ServiceHistory.service == service,
                ServiceHistory.service_date == service_date,
            )
        )
        if not exists:
            db.session.add(
                ServiceHistory(
                    customer_id=customer_id,
                    vehicle_id=vehicle_id,
                    service=service,
                    service_date=service_date,
                    technician=technician,
                    status=status,
                    notes=notes,
                )
            )
            stats["demo_history"] += 1

    demo_notifications = [
        ("MARIA L. SANTOS", "Your tire change appointment is scheduled for today at 09:00."),
        ("JEROME P. CRUZ", "Your vehicle is currently in service for wheel alignment."),
        ("ANGELICA R. FLORES", "Your tire rotation appointment is scheduled for today at 13:00."),
        ("CARLO M. REYES", "Reminder: your oil change appointment is scheduled for tomorrow at 09:30."),
        ("ROSE ANN GARCIA", "Your brake inspection request has been received and is pending."),
    ]
    for name, message in demo_notifications:
        customer_id = demo_ids[name]
        exists = db.session.scalar(
            select(Notification.id).where(
                Notification.customer_id == customer_id,
                Notification.message == message,
            )
        )
        if not exists:
            db.session.add(
                Notification(
                    customer_id=customer_id,
                    message=message,
                    notification_date=now_str(),
                    status="Pending",
                )
            )
            stats["demo_notifications"] += 1

    demo_visits = [
        (today, "1001", "KCA 2147", "TOYOTA VIOS", "MARIA L. SANTOS", "QUEZON, BUKIDNON", "JUN REYES"),
        (today, "1002", "KBD 5832", "MITSUBISHI MONTERO", "JEROME P. CRUZ", "MARAMAG, BUKIDNON", "MARK DELA CRUZ"),
        (today, "1003", "KCE 7319", "HONDA CITY", "ANGELICA R. FLORES", "VALENCIA CITY, BUKIDNON", "JUN REYES"),
        (today, "1004", "KAG 9041", "TOYOTA HILUX", "CARLO M. REYES", "QUEZON, BUKIDNON", "MARK DELA CRUZ"),
    ]
    for visit in demo_visits:
        exists = db.session.scalar(
            select(Visit.id).where(Visit.visit_date == visit[0], Visit.record_no == visit[1])
        )
        if not exists:
            db.session.add(
                Visit(
                    visit_date=visit[0],
                    record_no=visit[1],
                    plate=visit[2],
                    model=visit[3],
                    customer_name=visit[4],
                    address=visit[5],
                    technician=visit[6],
                )
            )
            stats["demo_visits"] += 1

    db.session.commit()
    return stats


def _days_ago(days: int) -> str:
    from datetime import timedelta

    from .timeutil import now_local

    return (now_local() - timedelta(days=days)).strftime("%Y-%m-%d")


def seed_database(force: bool = False) -> dict[str, int | bool]:
    """Create the source records once. Safe to call on every startup.

    The workbook marker is only written when a data file was actually read. This
    matters for privacy-preserving deployments: if the private JSON is supplied
    later (for example as a Render secret file), the next start or
    ``flask --app wsgi seed-db --force`` will still import it.
    """
    meta = db.session.get(SystemMeta, "seed_version")
    if meta and meta.value == SEED_VERSION and not force:
        return {"skipped": True}

    records, data_available = _load_records()
    stats: dict[str, int | bool] = {
        "visits": _import_visits(records),
        "customers": _import_customers(records),
    }
    stats["vehicles"] = _import_vehicles()

    if current_app.config.get("SEED_DEMO_DATA", True):
        stats.update(_seed_demo_records())

    if data_available:
        meta = db.session.get(SystemMeta, "seed_version")
        if meta is None:
            db.session.add(SystemMeta(key="seed_version", value=SEED_VERSION))
        else:
            meta.value = SEED_VERSION
    else:
        stats["data_file_missing"] = True

    db.session.commit()

    current_app.logger.info(
        "Database seed complete: %s visits, %s customers, %s vehicles added.",
        stats["visits"],
        stats["customers"],
        stats["vehicles"],
    )
    if not data_available:
        current_app.logger.warning(
            "The customer record import is incomplete because no readable data "
            "file was found. Set SEED_DATA_FILE and restart to import it."
        )
    return stats
