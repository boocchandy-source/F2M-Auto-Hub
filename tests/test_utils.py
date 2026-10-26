"""Validation helper tests."""

from __future__ import annotations

import pytest

from f2m.utils import safe_redirect_target, valid_date, valid_time


@pytest.mark.parametrize(
    "target",
    [
        "/customers",
        "/reports?type=Weekly&date=2026-10-26",
        "/visits?date=2026-04-23&page=2",
    ],
)
def test_safe_redirect_allows_local_paths(target):
    assert safe_redirect_target(target) == target


@pytest.mark.parametrize(
    "target",
    [
        "https://evil.example",
        "//evil.example/path",
        "/\\evil.example/path",
        "\\\\evil.example",
        "javascript:alert(1)",
        "customers",
        "",
        None,
    ],
)
def test_safe_redirect_rejects_external_or_relative_targets(target):
    assert safe_redirect_target(target) is None


def test_validation_helpers():
    assert valid_date("2026-10-26")
    assert not valid_date("2026-02-30")
    assert not valid_date("26-10-2026")
    assert valid_time("09:30")
    assert not valid_time("24:00")
    assert not valid_time("not-a-time")
