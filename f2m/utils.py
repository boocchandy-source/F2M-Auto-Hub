"""Validation, lookup, and small domain helpers."""

from __future__ import annotations

from datetime import datetime
from urllib.parse import urlsplit

from flask import request
from sqlalchemy import func, select

from .models import Customer, ServiceHistory, Vehicle, db

APPOINTMENT_STATUSES = ["Scheduled", "In Service", "Completed", "Cancelled"]
REQUEST_STATUSES = ["Pending", "In Progress", "Completed", "Cancelled"]
CONCERN_STATUSES = ["Pending", "In Progress", "Resolved"]
NOTIFICATION_STATUSES = ["Pending", "Recorded", "Acknowledged"]
VEHICLE_STATUSES = ["Active", "In Service", "Inactive"]
HISTORY_STATUSES = ["Completed", "In Progress", "Cancelled"]

DEFAULT_SERVICES = [
    "Tire Change",
    "Tire Rotation",
    "Tire Replacement",
    "Wheel Alignment",
    "Wheel Balancing",
    "Oil Change",
    "Brake Inspection",
    "Engine Tune-Up",
    "Battery Replacement",
    "Aircon Cleaning",
    "General Inspection",
]


def clean(value: str | None, max_length: int | None = None) -> str:
    text = (value or "").strip()
    # Strip control characters that would break Excel exports or layout.
    text = "".join(ch for ch in text if ch >= " " or ch in "\n\t").strip()
    if max_length is not None:
        text = text[:max_length]
    return text


def parse_int(value: str | int | None) -> int | None:
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def valid_date(value: str | None) -> bool:
    try:
        datetime.strptime((value or "").strip(), "%Y-%m-%d")
        return True
    except (TypeError, ValueError):
        return False


def valid_time(value: str | None) -> bool:
    try:
        datetime.strptime((value or "").strip(), "%H:%M")
        return True
    except (TypeError, ValueError):
        return False


def safe_redirect_target(value: str | None) -> str | None:
    """Only allow same-site relative redirect targets."""
    if not value:
        return None
    target = value.strip()
    if not target or "\n" in target or "\r" in target or "\\" in target:
        return None
    parts = urlsplit(target)
    if parts.scheme or parts.netloc or not parts.path.startswith("/") or parts.path.startswith("//"):
        return None
    return target


def page_number() -> int:
    try:
        page = int(request.args.get("page", "1"))
    except (TypeError, ValueError):
        page = 1
    return max(1, page)


def like_query(value: str) -> str:
    return f"%{value.strip()}%"


def all_customers() -> list[Customer]:
    return list(db.session.scalars(select(Customer).order_by(Customer.name.asc())).all())


def customer_or_none(customer_id: int | None) -> Customer | None:
    if not customer_id:
        return None
    return db.session.get(Customer, customer_id)


def first_vehicle_id(customer_id: int) -> int | None:
    return db.session.scalar(
        select(Vehicle.id).where(Vehicle.customer_id == customer_id).order_by(Vehicle.id.asc()).limit(1)
    )


def customer_is_duplicate(name: str, plate: str, exclude_id: int | None = None) -> bool:
    stmt = select(Customer.id).where(
        func.lower(func.trim(Customer.name)) == name.strip().lower(),
        func.upper(func.trim(func.coalesce(Customer.plate, ""))) == plate.strip().upper(),
    )
    if exclude_id:
        stmt = stmt.where(Customer.id != exclude_id)
    return db.session.scalar(stmt.limit(1)) is not None


def plate_is_duplicate(plate: str, exclude_id: int | None = None) -> bool:
    stmt = select(Vehicle.id).where(
        func.upper(func.trim(Vehicle.plate)) == plate.strip().upper()
    )
    if exclude_id:
        stmt = stmt.where(Vehicle.id != exclude_id)
    return db.session.scalar(stmt.limit(1)) is not None


def add_history_if_missing(
    customer_id: int,
    service: str,
    service_date: str,
    technician: str = "",
    notes: str = "",
    status: str = "Completed",
) -> ServiceHistory | None:
    """Mirror the desktop app: completed requests create a history row once."""
    existing = db.session.scalar(
        select(ServiceHistory.id).where(
            ServiceHistory.customer_id == customer_id,
            ServiceHistory.service == service,
            ServiceHistory.service_date == service_date,
        )
    )
    if existing:
        return None
    row = ServiceHistory(
        customer_id=customer_id,
        vehicle_id=first_vehicle_id(customer_id),
        service=service,
        service_date=service_date,
        technician=technician,
        status=status,
        notes=notes,
    )
    db.session.add(row)
    return row


def choice_or_default(value: str | None, choices: list[str], default: str) -> str:
    cleaned = clean(value, 30)
    return cleaned if cleaned in choices else default


def status_choices_with_current(choices: list[str], current: str | None) -> list[str]:
    values = list(choices)
    if current and current not in values:
        values.append(current)
    return values
