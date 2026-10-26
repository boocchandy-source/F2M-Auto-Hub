"""Shared pytest fixtures for the F2M Auto-Hub web application."""

from __future__ import annotations

import pytest

from f2m import auth, create_app
from f2m.models import db
from tests.helpers import TEST_PASSWORD, TEST_USERNAME, csrf_token, login


@pytest.fixture(autouse=True)
def reset_login_attempts():
    auth._FAILED_ATTEMPTS.clear()
    yield
    auth._FAILED_ATTEMPTS.clear()


@pytest.fixture()
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
            "BOOTSTRAP_DATABASE": False,
            "SEED_DATA": False,
            "SEED_DEMO_DATA": False,
            "SESSION_COOKIE_SECURE": False,
            "CSRF_ENABLED": True,
            "SECRET_KEY": "test-secret-key",
            "ADMIN_USERNAME": TEST_USERNAME,
            "ADMIN_PASSWORD": TEST_PASSWORD,
            "ADMIN_PASSWORD_HASH": "",
            "USING_DEFAULT_PASSWORD": False,
        }
    )
    with app.app_context():
        db.create_all()
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def authed_client(app, client):
    response = login(client)
    assert response.status_code == 302
    return client


@pytest.fixture()
def page_token(authed_client):
    def _token(path: str = "/customers") -> str:
        return csrf_token(authed_client.get(path))

    return _token
