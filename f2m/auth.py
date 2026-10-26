"""Administrator authentication with rate limiting and safe redirects."""

from __future__ import annotations

import hmac
import secrets
import threading
import time

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash

from .utils import safe_redirect_target

bp = Blueprint("auth", __name__)

_ATTEMPT_LOCK = threading.Lock()
_FAILED_ATTEMPTS: dict[str, list[float]] = {}
_MAX_ATTEMPTS = 8
_WINDOW_SECONDS = 10 * 60
_LOCK_SECONDS = 5 * 60


def _client_key() -> str:
    return request.remote_addr or "unknown"


def _recent_failures(key: str) -> list[float]:
    cutoff = time.monotonic() - _WINDOW_SECONDS
    attempts = _FAILED_ATTEMPTS.get(key, [])
    attempts = [stamp for stamp in attempts if stamp >= cutoff]
    if attempts:
        _FAILED_ATTEMPTS[key] = attempts
    else:
        _FAILED_ATTEMPTS.pop(key, None)
    return attempts


def _is_locked(key: str) -> bool:
    attempts = _recent_failures(key)
    return len(attempts) >= _MAX_ATTEMPTS and (time.monotonic() - attempts[-1]) < _LOCK_SECONDS


def _record_failure(key: str) -> None:
    with _ATTEMPT_LOCK:
        _FAILED_ATTEMPTS.setdefault(key, []).append(time.monotonic())


def _clear_failures(key: str) -> None:
    with _ATTEMPT_LOCK:
        _FAILED_ATTEMPTS.pop(key, None)


def _password_matches(password: str) -> bool:
    password_hash = current_app.config.get("ADMIN_PASSWORD_HASH", "")
    if password_hash:
        try:
            return check_password_hash(password_hash, password)
        except ValueError:
            current_app.logger.error("ADMIN_PASSWORD_HASH is not a valid Werkzeug hash.")
            return False
    expected = current_app.config.get("ADMIN_PASSWORD", "")
    return hmac.compare_digest(password, expected)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("auth"):
        return redirect(url_for("main.dashboard"))

    next_url = safe_redirect_target(request.values.get("next")) or ""
    error = None

    if request.method == "POST":
        key = _client_key()
        if _is_locked(key):
            error = "Too many failed attempts. Please wait a few minutes before trying again."
            response = render_template(
                "login.html",
                next_url=next_url,
                error=error,
                show_demo_hint=current_app.config.get("USING_DEFAULT_PASSWORD", False),
            )
            return response, 429, {"Retry-After": str(_LOCK_SECONDS)}

        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        expected_username = current_app.config.get("ADMIN_USERNAME", "admin")

        username_ok = hmac.compare_digest(username, expected_username)
        password_ok = _password_matches(password)

        if username_ok and password_ok:
            _clear_failures(key)
            session.clear()
            session["auth"] = True
            session["user"] = expected_username
            session["_csrf_token"] = secrets.token_urlsafe(32)
            session.permanent = True
            flash(f"Welcome back, {expected_username}.", "success")
            return redirect(next_url or url_for("main.dashboard"))

        _record_failure(key)
        current_app.logger.warning("Failed login attempt from %s", key)
        error = "Incorrect username or password. Please try again."

    return render_template(
        "login.html",
        next_url=next_url,
        error=error,
        show_demo_hint=current_app.config.get("USING_DEFAULT_PASSWORD", False),
    )


@bp.post("/logout")
def logout():
    session.clear()
    flash("You have been signed out.", "info")
    return redirect(url_for("auth.login"))
