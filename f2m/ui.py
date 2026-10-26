"""Small presentation helpers: icons, badges, navigation, and template filters."""

from __future__ import annotations

from flask import current_app, request, session, url_for
from markupsafe import Markup, escape

from .timeutil import (
    now_local,
    pretty_date as _pretty_date,
    pretty_datetime as _pretty_datetime,
    pretty_time as _pretty_time,
    today_iso,
)
from .utils import DEFAULT_SERVICES

APP_VERSION = "2.0.0"

# Heroicon-style outline paths, kept inline so the app has no CDN dependency.
ICONS: dict[str, str] = {
    "dashboard": (
        '<rect x="3" y="3" width="7" height="7" rx="1.6"/>'
        '<rect x="14" y="3" width="7" height="7" rx="1.6"/>'
        '<rect x="3" y="14" width="7" height="7" rx="1.6"/>'
        '<rect x="14" y="14" width="7" height="7" rx="1.6"/>'
    ),
    "users": (
        '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/>'
        '<circle cx="9" cy="7" r="4"/>'
        '<path d="M22 21v-2a4 4 0 0 0-3-3.87"/>'
        '<path d="M16 3.13a4 4 0 0 1 0 7.75"/>'
    ),
    "user": (
        '<path d="M20 21a8 8 0 0 0-16 0"/>'
        '<circle cx="12" cy="8" r="4"/>'
    ),
    "calendar": (
        '<rect x="3" y="4" width="18" height="18" rx="2"/>'
        '<path d="M16 2v4M8 2v4M3 10h18"/>'
    ),
    "calendar-check": (
        '<rect x="3" y="4" width="18" height="18" rx="2"/>'
        '<path d="M16 2v4M8 2v4M3 10h18"/>'
        '<path d="m9 16 2 2 4-4"/>'
    ),
    "message": (
        '<path d="M21 15a4 4 0 0 1-4 4H8l-5 3V7a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4z"/>'
        '<path d="M8 9h8M8 13h5"/>'
    ),
    "chart": (
        '<path d="M3 3v18h18"/>'
        '<rect x="7" y="12" width="3" height="6" rx="1"/>'
        '<rect x="12" y="8" width="3" height="10" rx="1"/>'
        '<rect x="17" y="5" width="3" height="13" rx="1"/>'
    ),
    "truck": (
        '<path d="M10 17h4V5H2v12h3"/>'
        '<path d="M20 17h2v-4l-3-4h-5v8h2"/>'
        '<circle cx="7.5" cy="17.5" r="2.5"/>'
        '<circle cx="17.5" cy="17.5" r="2.5"/>'
    ),
    "clipboard": (
        '<rect x="8" y="2" width="8" height="4" rx="1"/>'
        '<path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/>'
        '<path d="M9 12h6M9 16h6"/>'
    ),
    "history": (
        '<path d="M3 12a9 9 0 1 0 3-6.7L3 8"/>'
        '<path d="M3 3v5h5"/>'
        '<path d="M12 7v5l3 2"/>'
    ),
    "bell": (
        '<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9"/>'
        '<path d="M13.7 21a2 2 0 0 1-3.4 0"/>'
    ),
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
    "edit": (
        '<path d="M12 20h9"/>'
        '<path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/>'
    ),
    "trash": (
        '<path d="M3 6h18M8 6V4h8v2M19 6l-1 15H6L5 6"/>'
        '<path d="M10 11v6M14 11v6"/>'
    ),
    "logout": (
        '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>'
        '<path d="m16 17 5-5-5-5M21 12H9"/>'
    ),
    "menu": '<path d="M4 6h16M4 12h16M4 18h16"/>',
    "close": '<path d="M18 6 6 18M6 6l12 12"/>',
    "download": '<path d="M12 3v12M7 10l5 5 5-5"/><path d="M4 21h16"/>',
    "chevron-left": '<path d="m15 18-6-6 6-6"/>',
    "chevron-right": '<path d="m9 6 6 6-6 6"/>',
    "arrow-right": '<path d="M5 12h14M13 6l6 6-6 6"/>',
    "check": '<path d="m5 12 4 4L19 6"/>',
    "alert": '<path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/><path d="M12 9v4M12 17h.01"/>',
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>',
    "lock": '<rect x="4" y="10" width="16" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/>',
    "filter": '<path d="M4 5h16l-6 7v6l-4 2v-8z"/>',
    "print": (
        '<path d="M6 9V3h12v6"/>'
        '<rect x="6" y="18" width="12" height="4"/>'
        '<path d="M6 14H4a2 2 0 0 1-2-2v-1a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v1a2 2 0 0 1-2 2h-2"/>'
    ),
    "wrench": (
        '<path d="M14.7 6.3a4 4 0 0 0-5.4 5.4L3 18l3 3 6.3-6.3a4 4 0 0 0 5.4-5.4l-2.3 2.3-2.6-2.6z"/>'
    ),
}


def icon(name: str, size: int = 18, css_class: str = "icon") -> Markup:
    body = ICONS.get(name, ICONS["info"])
    return Markup(
        f'<svg class="{css_class}" width="{size}" height="{size}" viewBox="0 0 24 24" '
        'fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" '
        f'stroke-linejoin="round" aria-hidden="true">{body}</svg>'
    )


STATUS_TONES = {
    "active": "success",
    "completed": "success",
    "resolved": "success",
    "acknowledged": "success",
    "recorded": "success",
    "scheduled": "info",
    "in progress": "progress",
    "in service": "progress",
    "pending": "warning",
    "cancelled": "muted",
    "inactive": "muted",
}


def status_badge(status: str | None) -> Markup:
    text = (status or "").strip() or "—"
    tone = STATUS_TONES.get(text.lower(), "muted")
    return Markup(f'<span class="badge badge-{tone}">{escape(text)}</span>')


NAV_GROUPS = [
    {
        "label": None,
        "items": [
            {"key": "dashboard", "endpoint": "main.dashboard", "label": "Dashboard", "icon": "dashboard"},
            {"key": "customers", "endpoint": "main.customers", "label": "Customer Records", "icon": "users"},
            {"key": "visits", "endpoint": "main.visits", "label": "Daily Visits", "icon": "calendar-check"},
            {"key": "feedback", "endpoint": "main.feedback", "label": "Feedback / Concern", "icon": "message"},
            {"key": "appointments", "endpoint": "main.appointments", "label": "Appointments", "icon": "calendar"},
            {"key": "reports", "endpoint": "main.reports", "label": "Report", "icon": "chart"},
        ],
    },
    {
        "label": "SERVICE MANAGEMENT",
        "items": [
            {"key": "vehicles", "endpoint": "main.vehicles", "label": "Vehicle Information", "icon": "truck"},
            {"key": "service_requests", "endpoint": "main.service_requests", "label": "Service Requests", "icon": "clipboard"},
            {"key": "service_history", "endpoint": "main.service_history", "label": "Service History", "icon": "history"},
            {"key": "notifications", "endpoint": "main.notifications", "label": "Notifications", "icon": "bell"},
        ],
    },
]

ENDPOINT_ACTIVE = {
    "main.dashboard": "dashboard",
    "main.customers": "customers",
    "main.customer_edit": "customers",
    "main.customer_delete": "customers",
    "main.visits": "visits",
    "main.feedback": "feedback",
    "main.feedback_edit": "feedback",
    "main.feedback_delete": "feedback",
    "main.appointments": "appointments",
    "main.appointment_edit": "appointments",
    "main.appointment_delete": "appointments",
    "main.reports": "reports",
    "main.report_export": "reports",
    "main.vehicles": "vehicles",
    "main.vehicle_edit": "vehicles",
    "main.vehicle_delete": "vehicles",
    "main.service_requests": "service_requests",
    "main.service_request_edit": "service_requests",
    "main.service_request_delete": "service_requests",
    "main.service_history": "service_history",
    "main.service_history_edit": "service_history",
    "main.service_history_delete": "service_history",
    "main.notifications": "notifications",
    "main.notification_edit": "notifications",
    "main.notification_delete": "notifications",
}


def page_url(page: int) -> str:
    """Build a pagination URL while preserving the current query string."""
    if not request.endpoint:
        return "#"
    args = request.args.to_dict(flat=True)
    args["page"] = str(page)
    view_args = request.view_args or {}
    try:
        return url_for(request.endpoint, **view_args, **args)
    except Exception:  # pragma: no cover - defensive fallback
        return url_for(request.endpoint, page=page)


def dash(value: object) -> str:
    text = ("" if value is None else str(value)).strip()
    return text if text and text != "-" else "—"


def initials(value: str | None) -> str:
    parts = [part for part in (value or "").split() if part]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def init_app(app) -> None:
    app.jinja_env.filters["pretty_date"] = _pretty_date
    app.jinja_env.filters["pretty_datetime"] = _pretty_datetime
    app.jinja_env.filters["pretty_time"] = _pretty_time
    app.jinja_env.filters["dash"] = dash
    app.jinja_env.filters["initials"] = initials
    app.jinja_env.globals["icon"] = icon
    app.jinja_env.globals["status_badge"] = status_badge
    app.jinja_env.globals["page_url"] = page_url

    @app.context_processor
    def inject_ui_globals():
        return {
            "nav_groups": NAV_GROUPS,
            "active_nav": ENDPOINT_ACTIVE.get(request.endpoint),
            "current_year": now_local().year,
            "today_pretty": _pretty_date(today_iso()),
            "today_iso": today_iso(),
            "current_user": session.get("user", current_app.config.get("ADMIN_USERNAME", "admin")),
            "app_version": APP_VERSION,
            "is_default_login": current_app.config.get("USING_DEFAULT_PASSWORD", False),
            "default_services": DEFAULT_SERVICES,
        }
