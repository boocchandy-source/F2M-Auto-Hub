"""Authentication, session, CSRF, and response-header tests."""

from __future__ import annotations

from f2m import auth
from f2m.models import db
from tests.helpers import csrf_token, login


def test_health_check_is_public(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok", "service": "f2m-autohub"}


def test_protected_page_redirects_to_login(client):
    response = client.get("/customers")
    assert response.status_code == 302
    assert "/login?next=" in response.headers["Location"]


def test_login_page_renders(client):
    response = client.get("/login")
    assert response.status_code == 200
    assert b"Sign in to continue" in response.data


def test_bad_credentials_are_rejected(client):
    response = login(client, password="wrong-password")
    assert response.status_code == 200
    assert b"Incorrect username or password" in response.data


def test_successful_login_and_logout(client):
    response = login(client)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")

    dashboard = client.get("/")
    assert dashboard.status_code == 200
    assert b"Management overview" in dashboard.data

    token = csrf_token(dashboard)
    logout = client.post("/logout", data={"_csrf_token": token})
    assert logout.status_code == 302
    assert "/login" in logout.headers["Location"]
    assert client.get("/").status_code == 302


def test_login_next_respects_local_redirect(client):
    token = csrf_token(client.get("/login"))
    response = client.post(
        "/login",
        data={
            "_csrf_token": token,
            "username": "admin",
            "password": "test-password-123",
            "next": "/customers?q=test",
        },
    )
    assert response.status_code == 302
    assert response.headers["Location"] == "/customers?q=test"


def test_login_next_rejects_external_redirect(client):
    token = csrf_token(client.get("/login"))
    response = client.post(
        "/login",
        data={
            "_csrf_token": token,
            "username": "admin",
            "password": "test-password-123",
            "next": "//evil.example/steal",
        },
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")


def test_csrf_rejects_login_without_token(client):
    response = client.post(
        "/login", data={"username": "admin", "password": "test-password-123"}
    )
    assert response.status_code == 400
    assert b"security token is invalid" in response.data


def test_csrf_rejects_authenticated_write_without_token(app, authed_client):
    response = authed_client.post("/customers", data={"name": "No Token"})
    assert response.status_code == 400
    with app.app_context():
        from f2m.models import Customer

        assert db.session.query(Customer).count() == 0


def test_csrf_rejects_forged_token(authed_client):
    authed_client.get("/customers")
    response = authed_client.post(
        "/customers", data={"_csrf_token": "forged", "name": "Forged"}
    )
    assert response.status_code == 400


def test_login_rate_limit(client):
    token = csrf_token(client.get("/login"))
    for _ in range(auth._MAX_ATTEMPTS):
        response = client.post(
            "/login",
            data={"_csrf_token": token, "username": "admin", "password": "wrong"},
        )
        assert response.status_code == 200

    blocked = client.post(
        "/login",
        data={"_csrf_token": token, "username": "admin", "password": "test-password-123"},
    )
    assert blocked.status_code == 429
    assert blocked.headers["Retry-After"] == str(auth._LOCK_SECONDS)


def test_security_headers(authed_client):
    response = authed_client.get("/")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "same-origin"
    assert "default-src 'self'" in response.headers["Content-Security-Policy"]
    assert response.headers["Cache-Control"] == "no-store"
    assert "Strict-Transport-Security" not in response.headers
