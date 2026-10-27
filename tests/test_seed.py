"""Tests for the first-run workbook import."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import func, select

from f2m.models import Customer, SystemMeta, Vehicle, Visit, db
from f2m.seed import DATA_FILE, seed_database

SYNTHETIC_RECORDS = [
    ["2026-01-01", "1", "AAA 1111", "TOYOTA VIOS", "ALPHA CUSTOMER", "CITY A", "TECH ONE"],
    ["2026-01-01", "2", "BBB 2222", "HONDA CITY", "BETA CUSTOMER", "CITY B", "TECH TWO"],
    ["2026-01-02", "3", "CCC 3333", "FORD RANGER", "GAMMA CUSTOMER", "CITY C", "TECH ONE"],
    # Same customer and vehicle as the first row; only the visit is new.
    ["2026-01-02", "4", "AAA 1111", "TOYOTA VIOS", "ALPHA CUSTOMER", "CITY A", "TECH ONE"],
]


@pytest.fixture()
def seed_file(tmp_path, monkeypatch):
    path = tmp_path / "customer_records.json"
    path.write_text(json.dumps(SYNTHETIC_RECORDS), encoding="utf-8")
    monkeypatch.setenv("SEED_DATA_FILE", str(path))
    return path


def test_seed_imports_workbook_once(app, seed_file):
    app.config["SEED_DEMO_DATA"] = False
    with app.app_context():
        first = seed_database()
        assert not first.get("skipped")
        assert first["visits"] == 4
        assert first["customers"] == 3
        assert first["vehicles"] == 3
        assert "data_file_missing" not in first

        counts = {
            "visits": db.session.scalar(select(func.count(Visit.id))),
            "customers": db.session.scalar(select(func.count(Customer.id))),
            "vehicles": db.session.scalar(select(func.count(Vehicle.id))),
        }
        assert counts == {"visits": 4, "customers": 3, "vehicles": 3}

        second = seed_database()
        assert second == {"skipped": True}
        assert db.session.scalar(select(func.count(Visit.id))) == counts["visits"]
        assert db.session.scalar(select(func.count(Customer.id))) == counts["customers"]
        assert db.session.scalar(select(func.count(Vehicle.id))) == counts["vehicles"]

        meta = db.session.get(SystemMeta, "seed_version")
        assert meta is not None
        assert meta.value == "1"


def test_missing_workbook_does_not_mark_seed_version(app, tmp_path, monkeypatch):
    app.config["SEED_DEMO_DATA"] = False
    missing_path = tmp_path / "not-yet-mounted" / "customer_records.json"
    monkeypatch.setenv("SEED_DATA_FILE", str(missing_path))

    with app.app_context():
        first = seed_database()
        assert first["visits"] == 0
        assert first["customers"] == 0
        assert first["vehicles"] == 0
        assert first["data_file_missing"] is True
        assert db.session.get(SystemMeta, "seed_version") is None

        # Mounting the file later must be enough to import on the next run.
        missing_path.parent.mkdir(parents=True)
        missing_path.write_text(json.dumps(SYNTHETIC_RECORDS), encoding="utf-8")

        second = seed_database()
        assert second["visits"] == 4
        assert second["customers"] == 3
        assert second["vehicles"] == 3
        assert "data_file_missing" not in second
        assert db.session.get(SystemMeta, "seed_version").value == "1"


def test_force_reimport_is_still_idempotent(app, seed_file):
    app.config["SEED_DEMO_DATA"] = False
    with app.app_context():
        seed_database()
        forced = seed_database(force=True)
        assert forced["visits"] == 0
        assert forced["customers"] == 0
        assert forced["vehicles"] == 0
        assert db.session.scalar(select(func.count(Visit.id))) == 4


@pytest.mark.skipif(
    not DATA_FILE.exists(),
    reason="Private customer_records.json is not present in this checkout.",
)
def test_real_workbook_import(app):
    """Optional check for the private local dataset (skipped in public CI)."""
    app.config["SEED_DEMO_DATA"] = False
    with app.app_context():
        stats = seed_database()
        assert stats["visits"] == 1221
        assert stats["customers"] == 1122
        assert stats["vehicles"] == 1113
