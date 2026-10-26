"""SQLAlchemy models for the F2M Auto-Hub web application."""

from __future__ import annotations

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .timeutil import now_str

db = SQLAlchemy()


class Customer(db.Model):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    plate: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    model: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    address: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    technician: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    created_at: Mapped[str] = mapped_column(String(16), nullable=False, default=now_str)

    vehicles: Mapped[list[Vehicle]] = relationship(
        back_populates="customer", cascade="all, delete-orphan", order_by="Vehicle.id"
    )
    appointments: Mapped[list[Appointment]] = relationship(
        back_populates="customer", cascade="all, delete-orphan"
    )
    service_requests: Mapped[list[ServiceRequest]] = relationship(
        back_populates="customer", cascade="all, delete-orphan"
    )
    service_history: Mapped[list[ServiceHistory]] = relationship(
        back_populates="customer", cascade="all, delete-orphan"
    )
    feedback_concerns: Mapped[list[FeedbackConcern]] = relationship(
        back_populates="customer", cascade="all, delete-orphan"
    )
    notifications: Mapped[list[Notification]] = relationship(
        back_populates="customer", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Customer {self.id} {self.name!r}>"


class Vehicle(db.Model):
    __tablename__ = "vehicles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int | None] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), nullable=True, index=True
    )
    plate: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    technician: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="Active")
    created_at: Mapped[str] = mapped_column(String(16), nullable=False, default=now_str)

    customer: Mapped[Customer | None] = relationship(back_populates="vehicles")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Vehicle {self.id} {self.plate!r}>"


class Visit(db.Model):
    """Imported rows from the company's Daily Customer Record workbook."""

    __tablename__ = "visits"
    __table_args__ = (
        Index("ix_visits_date_name", "visit_date", "customer_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    visit_date: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    record_no: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    plate: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    model: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    customer_name: Mapped[str] = mapped_column(String(200), nullable=False)
    address: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    technician: Mapped[str] = mapped_column(String(120), nullable=False, default="")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Visit {self.visit_date} #{self.record_no} {self.customer_name!r}>"


class ServiceRequest(db.Model):
    __tablename__ = "service_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int | None] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), nullable=True, index=True
    )
    service: Mapped[str] = mapped_column(String(200), nullable=False)
    request_date: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="Pending", index=True)
    technician: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[str] = mapped_column(String(16), nullable=False, default=now_str)

    customer: Mapped[Customer | None] = relationship(back_populates="service_requests")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ServiceRequest {self.id} {self.service!r}>"


class Appointment(db.Model):
    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int | None] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), nullable=True, index=True
    )
    service: Mapped[str] = mapped_column(String(200), nullable=False)
    appointment_date: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    appointment_time: Mapped[str] = mapped_column(String(5), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="Scheduled", index=True)
    created_at: Mapped[str] = mapped_column(String(16), nullable=False, default=now_str)

    customer: Mapped[Customer | None] = relationship(back_populates="appointments")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Appointment {self.id} {self.appointment_date} {self.appointment_time}>"


class ServiceHistory(db.Model):
    __tablename__ = "service_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int | None] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), nullable=True, index=True
    )
    vehicle_id: Mapped[int | None] = mapped_column(
        ForeignKey("vehicles.id", ondelete="SET NULL"), nullable=True
    )
    service: Mapped[str] = mapped_column(String(200), nullable=False)
    service_date: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    technician: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="Completed")
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")

    customer: Mapped[Customer | None] = relationship(back_populates="service_history")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ServiceHistory {self.id} {self.service!r}>"


class FeedbackConcern(db.Model):
    __tablename__ = "feedback_concerns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int | None] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), nullable=True, index=True
    )
    concern: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="Pending", index=True)
    created_at: Mapped[str] = mapped_column(String(16), nullable=False, default=now_str)

    customer: Mapped[Customer | None] = relationship(back_populates="feedback_concerns")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<FeedbackConcern {self.id}>"


class Notification(db.Model):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int | None] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), nullable=True, index=True
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    notification_date: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="Pending", index=True)

    customer: Mapped[Customer | None] = relationship(back_populates="notifications")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Notification {self.id}>"


class SystemMeta(db.Model):
    """Small key/value table used to make first-run seeding idempotent."""

    __tablename__ = "system_meta"

    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
