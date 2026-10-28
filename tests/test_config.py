"""Configuration helper tests, including Render's Postgres URL formats."""

from __future__ import annotations

from f2m import _normalize_database_url


def test_normalizes_libpq_postgres_urls():
    assert (
        _normalize_database_url("postgres://user:pass@db.example/f2m")
        == "postgresql+psycopg://user:pass@db.example/f2m"
    )
    assert (
        _normalize_database_url("postgresql://user:pass@db.example/f2m")
        == "postgresql+psycopg://user:pass@db.example/f2m"
    )


def test_leaves_other_database_urls_untouched():
    assert _normalize_database_url("sqlite:///instance/test.db") == "sqlite:///instance/test.db"
    assert (
        _normalize_database_url("postgresql+psycopg://user:pass@db.example/f2m")
        == "postgresql+psycopg://user:pass@db.example/f2m"
    )


def test_rewrites_legacy_psycopg2_urls_to_psycopg3():
    assert (
        _normalize_database_url("postgresql+psycopg2://user:pass@db.example/f2m")
        == "postgresql+psycopg://user:pass@db.example/f2m"
    )
