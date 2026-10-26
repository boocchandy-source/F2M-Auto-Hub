"""Timezone-aware date helpers used across the application."""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

APP_TIMEZONE = os.environ.get("APP_TIMEZONE", "Asia/Manila").strip() or "Asia/Manila"

try:
    TZ = ZoneInfo(APP_TIMEZONE)
except Exception:  # pragma: no cover - only hit with an invalid APP_TIMEZONE
    APP_TIMEZONE = "UTC"
    TZ = ZoneInfo("UTC")


def now_local() -> datetime:
    """Current time in the application timezone."""
    return datetime.now(TZ)


def now_str() -> str:
    """Timestamp in the same format the desktop app used (YYYY-MM-DD HH:MM)."""
    return now_local().strftime("%Y-%m-%d %H:%M")


def today_iso() -> str:
    return now_local().strftime("%Y-%m-%d")


def tomorrow_iso() -> str:
    return (now_local() + timedelta(days=1)).strftime("%Y-%m-%d")


def pretty_date(value: str | None) -> str:
    if not value:
        return "—"
    text = str(value).strip()
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").strftime("%b %d, %Y")
    except ValueError:
        return text


def pretty_time(value: str | None) -> str:
    if not value:
        return "—"
    try:
        return datetime.strptime(str(value).strip(), "%H:%M").strftime("%I:%M %p").lstrip("0")
    except ValueError:
        return str(value)


def pretty_datetime(value: str | None) -> str:
    if not value:
        return "—"
    text = str(value).strip()
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).strftime("%b %d, %Y · %I:%M %p").replace(
                " · 12:00 AM", ""
            )
        except ValueError:
            continue
    return text


def report_range(report_type: str, reference: date) -> tuple[date, date]:
    """Return the inclusive date range for Daily / Weekly / Monthly reports."""
    kind = (report_type or "Daily").strip().lower()
    if kind == "weekly":
        start = reference - timedelta(days=reference.weekday())
        return start, start + timedelta(days=6)
    if kind == "monthly":
        start = reference.replace(day=1)
        next_month = (start + timedelta(days=32)).replace(day=1)
        return start, next_month - timedelta(days=1)
    return reference, reference
