"""Small HTTP helpers shared by the test modules."""

from __future__ import annotations

import re

TEST_USERNAME = "admin"
TEST_PASSWORD = "test-password-123"


def csrf_token(response) -> str:
    html = response.get_data(as_text=True)
    match = re.search(r'name="_csrf_token" value="([^"]+)"', html)
    assert match, "Expected a CSRF token in the response"
    return match.group(1)


def login(client, username: str = TEST_USERNAME, password: str = TEST_PASSWORD):
    token = csrf_token(client.get("/login"))
    return client.post(
        "/login",
        data={"_csrf_token": token, "username": username, "password": password},
    )
