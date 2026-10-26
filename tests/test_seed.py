"""Tests for the first-run workbook import."""

from __future__ import annotations

from sqlalchemy import func, select

from f2m.models import Customer, SystemMeta, Vehicle, Visit, db
from f2m.seed import seed_database


def test_seed_imports_workbook_once(app):
    app.config["SEED_DEMO_DATA"] = False
    with app.app_context():
        first = seed_database()
        assert not first.get("skipped")
        assert first["visits"] == 1221
        assert first["customers"] == 1122
        assert first["vehicles"] == 1113

        counts = {
            "visits": db.session.scalar(select(func.count(Visit.id))),
            "customers": db.session.scalar(select(func.count(Customer.id))),
            "vehicles": db.session.scalar(select(func.count(Vehicle.id))),
        }
        assert counts == {"visits": 1221, "customers": 1122, "vehicles": 1113}

        second = seed_database()
        assert second == {"skipped": True}
        assert db.session.scalar(select(func.count(Visit.id))) == counts["visits"]
        assert db.session.scalar(select(func.count(Customer.id))) == counts["customers"]
        assert db.session.scalar(select(func.count(Vehicle.id))) == counts["vehicles"]

        meta = db.session.get(SystemMeta, "seed_version")
        assert meta is not None
        assert meta.value == "1"
