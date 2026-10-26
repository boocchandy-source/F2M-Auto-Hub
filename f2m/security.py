"""Session security: CSRF protection and hardened response headers."""

from __future__ import annotations

import hmac
import secrets

from flask import abort, current_app, request, session
from markupsafe import Markup, escape


def csrf_token() -> str:
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token


def csrf_field() -> Markup:
    return Markup(
        f'<input type="hidden" name="_csrf_token" value="{escape(csrf_token())}">'
    )


def init_app(app) -> None:
    app.jinja_env.globals["csrf_token"] = csrf_token
    app.jinja_env.globals["csrf_field"] = csrf_field

    @app.before_request
    def protect_from_csrf():
        if not current_app.config.get("CSRF_ENABLED", True):
            return None
        if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
            return None
        expected = session.get("_csrf_token")
        provided = request.form.get("_csrf_token") or request.headers.get("X-CSRF-Token")
        if not expected or not provided or not hmac.compare_digest(str(expected), str(provided)):
            abort(
                400,
                description=(
                    "This form expired or its security token is invalid. "
                    "Go back, refresh the page, and try again."
                ),
            )
        return None

    @app.after_request
    def set_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault(
            "Permissions-Policy", "camera=(), microphone=(), geolocation=()"
        )
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; "
            "img-src 'self' data:; "
            "style-src 'self'; "
            "script-src 'self'; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "base-uri 'self'; "
            "form-action 'self'; "
            "frame-ancestors 'none'; "
            "object-src 'none'",
        )
        if request.endpoint != "static":
            response.headers.setdefault("Cache-Control", "no-store")
        if current_app.config.get("SESSION_COOKIE_SECURE"):
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return response
