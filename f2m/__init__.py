"""F2M Auto-Hub web application factory.

The original project was a Tkinter desktop program.  This package is a
feature-compatible Flask port that can run on Render (or any WSGI host) while
retaining the daily customer record import, service management workflows, and
Excel reporting of the desktop version.
"""

from __future__ import annotations

import logging
import os
import secrets
import sqlite3
import time
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, session, url_for
from sqlalchemy import event
from sqlalchemy.engine import Engine
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

# Load local .env values before importing modules that read the environment at
# import time (timeutil reads APP_TIMEZONE when it is first imported).
load_dotenv()

from . import auth, security, ui, views  # noqa: E402
from .models import db  # noqa: E402
from .seed import seed_database  # noqa: E402
from .timeutil import now_local  # noqa: E402

__all__ = ["create_app", "db"]

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_PASSWORD = "admin123"


# ---------------------------------------------------------------------------
# Configuration helpers
# ---------------------------------------------------------------------------


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _normalize_database_url(raw_url: str) -> str:
    """Render exposes libpq URLs; SQLAlchemy needs an explicit psycopg driver."""
    url = raw_url.strip()
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    if url.startswith("postgresql+psycopg://") or url.startswith("postgresql+psycopg2://"):
        return url
    return url


def _database_uri(app: Flask) -> tuple[str, bool]:
    raw_url = os.environ.get("DATABASE_URL", "").strip()
    if raw_url:
        return _normalize_database_url(raw_url), raw_url.startswith("sqlite")

    data_dir = Path(os.environ.get("DATA_DIR", str(Path(app.instance_path)))).expanduser()
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:  # pragma: no cover - only on a misconfigured disk
        app.logger.error("Cannot create data directory %s: %s", data_dir, exc)
        raise
    sqlite_path = (data_dir / "f2m_autohub.db").resolve()
    return f"sqlite:///{sqlite_path.as_posix()}", True


def _configure_app(app: Flask) -> None:
    database_url, is_sqlite = _database_uri(app)
    is_render = bool(os.environ.get("RENDER"))

    secret_key = os.environ.get("SECRET_KEY", "").strip()
    if not secret_key:
        secret_key = secrets.token_hex(32)
        app.logger.warning(
            "SECRET_KEY is not set. A temporary key was generated; sessions will "
            "reset when the process restarts. Set SECRET_KEY before deploying."
        )

    admin_username = os.environ.get("ADMIN_USERNAME", "admin").strip() or "admin"
    admin_password = os.environ.get("ADMIN_PASSWORD", "")
    admin_password_hash = os.environ.get("ADMIN_PASSWORD_HASH", "").strip()
    using_default_password = not admin_password and not admin_password_hash
    if using_default_password:
        admin_password = DEFAULT_PASSWORD
        if is_render:
            app.logger.warning(
                "ADMIN_PASSWORD is not set. The default password is active. "
                "Set ADMIN_PASSWORD in the Render dashboard immediately."
            )

    secure_cookie = _env_bool("SESSION_COOKIE_SECURE", is_render)

    app.config.update(
        SECRET_KEY=secret_key,
        SQLALCHEMY_DATABASE_URI=database_url,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS=(
            {
                "pool_pre_ping": True,
                "connect_args": {"check_same_thread": False, "timeout": 30},
            }
            if is_sqlite
            else {
                "pool_pre_ping": True,
                "pool_recycle": 280,
                "pool_size": 5,
                "max_overflow": 5,
                "connect_args": {"connect_timeout": 10},
            }
        ),
        ADMIN_USERNAME=admin_username,
        ADMIN_PASSWORD=admin_password,
        ADMIN_PASSWORD_HASH=admin_password_hash,
        USING_DEFAULT_PASSWORD=using_default_password,
        SESSION_COOKIE_NAME="f2m_session",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=secure_cookie,
        PERMANENT_SESSION_LIFETIME=timedelta(hours=12),
        SESSION_REFRESH_EACH_REQUEST=True,
        MAX_CONTENT_LENGTH=4 * 1024 * 1024,
        PER_PAGE=20,
        SEED_DATA=_env_bool("SEED_DATA", True),
        SEED_DEMO_DATA=_env_bool("SEED_DEMO_DATA", True),
        CSRF_ENABLED=True,
        BOOTSTRAP_DATABASE=True,
        SEND_FILE_MAX_AGE_DEFAULT=3600 if not app.debug else 0,
    )

    if _env_bool("TRUST_PROXY_HEADERS", is_render):
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    if app.config["ADMIN_PASSWORD_HASH"]:
        app.config["ADMIN_PASSWORD"] = ""


@event.listens_for(Engine, "connect")
def _sqlite_pragmas(dbapi_connection, _connection_record) -> None:
    """Useful SQLite defaults for a small single-instance deployment."""
    if not isinstance(dbapi_connection, sqlite3.Connection):
        return
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        try:
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
        except sqlite3.DatabaseError:
            # In-memory databases and read-only files do not support WAL.
            pass
    finally:
        cursor.close()


# ---------------------------------------------------------------------------
# Startup: tables + idempotent seed
# ---------------------------------------------------------------------------


def _bootstrap_database(app: Flask) -> None:
    if not app.config.get("BOOTSTRAP_DATABASE", True):
        return

    attempts = 5
    for attempt in range(1, attempts + 1):
        try:
            with app.app_context():
                db.create_all()
                if app.config.get("SEED_DATA", True):
                    stats = seed_database()
                    if stats.get("skipped"):
                        app.logger.info("Database already seeded; skipping import.")
                    else:
                        app.logger.info("Seed summary: %s", stats)
            return
        except Exception as exc:  # pragma: no cover - depends on hosting DB
            app.logger.warning(
                "Database bootstrap attempt %s/%s failed: %s", attempt, attempts, exc
            )
            try:
                with app.app_context():
                    db.session.rollback()
            except Exception:
                pass
            if attempt == attempts:
                app.logger.exception("Database bootstrap failed permanently.")
                raise
            time.sleep(min(2 ** attempt, 10))


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)

    # Logging is configured before _configure_app so warnings are visible.
    app.logger.setLevel(logging.INFO)
    if not app.logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("[%(asctime)s] %(levelname)s in %(module)s: %(message)s")
        )
        app.logger.addHandler(handler)

    _configure_app(app)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    ui.init_app(app)

    # Authentication guard is registered before CSRF so unauthenticated page
    # requests are redirected to the login page instead of failing validation.
    @app.before_request
    def require_login():
        public_endpoints = {
            "auth.login",
            "main.healthz",
            "main.favicon",
            "static",
        }
        if request.endpoint in public_endpoints:
            return None
        if session.get("auth"):
            return None
        next_url = request.full_path if request.query_string else request.path
        return redirect(url_for("auth.login", next=next_url))

    security.init_app(app)

    app.register_blueprint(auth.bp)
    app.register_blueprint(views.bp)

    @app.context_processor
    def inject_time():
        return {"now": now_local()}

    @app.errorhandler(HTTPException)
    def handle_http_error(error: HTTPException):
        if error.code == 404:
            title = "Page not found"
            message = "The page you are looking for does not exist or may have been moved."
        elif error.code == 400:
            title = "Request could not be processed"
            message = error.description or "The form request was invalid. Please try again."
        elif error.code == 403:
            title = "Access denied"
            message = "You do not have permission to open this page."
        elif error.code == 405:
            title = "Method not allowed"
            message = "This action is not available from the address you used."
        elif error.code == 413:
            title = "File is too large"
            message = "The submitted data is larger than the 4 MB limit."
        else:
            title = error.name
            message = error.description or "Something went wrong while processing the request."
        return (
            render_template(
                "error.html",
                code=error.code,
                title=title,
                message=message,
                signed_in=bool(session.get("auth")),
            ),
            error.code,
        )

    @app.errorhandler(500)
    def handle_server_error(error):  # pragma: no cover - tested manually
        try:
            db.session.rollback()
        except Exception:
            pass
        app.logger.exception("Unhandled server error: %s", error)
        return (
            render_template(
                "error.html",
                code=500,
                title="Something went wrong",
                message=(
                    "The server could not complete that request. Please try again. "
                    "If the problem continues, contact the administrator."
                ),
                signed_in=bool(session.get("auth")),
            ),
            500,
        )

    @app.cli.command("init-db")
    def init_db_command():
        """Create missing tables without importing data."""
        with app.app_context():
            db.create_all()
        print("Database tables are ready.")

    @app.cli.command("seed-db")
    def seed_db_command():
        """Import the daily customer record workbook once."""
        with app.app_context():
            db.create_all()
            stats = seed_database()
        print(f"Seed complete: {stats}")

    @app.cli.command("reset-data")
    def reset_data_command():
        """Drop every table, recreate them, and re-import the workbook."""
        with app.app_context():
            db.drop_all()
            db.create_all()
            stats = seed_database(force=True)
        print(f"Data reset complete: {stats}")

    _bootstrap_database(app)

    return app
