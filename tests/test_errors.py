"""Error page and route-guard tests."""

from __future__ import annotations


def test_authenticated_404_uses_branded_error_page(authed_client):
    response = authed_client.get("/this-page-does-not-exist")
    assert response.status_code == 404
    assert b"Page not found" in response.data
    assert b"F2M Auto-Hub" in response.data
    assert b'class="sidebar"' in response.data


def test_method_not_allowed_page(authed_client, page_token):
    response = authed_client.post(
        "/healthz", data={"_csrf_token": page_token("/")}
    )
    assert response.status_code == 405
    assert b"Method not allowed" in response.data


def test_unknown_path_redirects_anonymous_users_to_login(client):
    response = client.get("/this-page-does-not-exist")
    assert response.status_code == 302
    assert "/login?next=" in response.headers["Location"]
