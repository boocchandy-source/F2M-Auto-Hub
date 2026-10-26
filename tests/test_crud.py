"""CRUD route tests for customers, vehicles, and service workflows."""

from __future__ import annotations

from sqlalchemy import func, select

from f2m.models import (
    Appointment,
    Customer,
    FeedbackConcern,
    Notification,
    ServiceHistory,
    ServiceRequest,
    Vehicle,
    db,
)
from f2m.timeutil import today_iso
from tests.helpers import csrf_token


def _create_customer(client, token: str, **overrides):
    data = {
        "_csrf_token": token,
        "name": "Test Customer",
        "plate": "TST 123",
        "model": "Toyota Vios",
        "address": "Quezon, Bukidnon",
        "technician": "Jun Reyes",
    }
    data.update(overrides)
    return client.post("/customers", data=data, follow_redirects=True)


def _customer_id(app, name: str = "Test Customer") -> int:
    with app.app_context():
        return db.session.scalar(select(Customer.id).where(Customer.name == name))


def test_customer_create_creates_linked_vehicle(app, authed_client, page_token):
    response = _create_customer(authed_client, page_token())
    assert response.status_code == 200
    assert b"Test Customer" in response.data

    with app.app_context():
        customer = db.session.scalar(
            select(Customer).where(Customer.name == "Test Customer")
        )
        assert customer is not None
        assert customer.plate == "TST 123"
        assert customer.technician == "Jun Reyes"
        vehicle = db.session.scalar(
            select(Vehicle).where(Vehicle.customer_id == customer.id)
        )
        assert vehicle is not None
        assert vehicle.plate == "TST 123"
        assert vehicle.model == "Toyota Vios"


def test_customer_validation_and_search(app, authed_client, page_token):
    token = page_token()
    missing_name = authed_client.post(
        "/customers", data={"_csrf_token": token, "name": ""}, follow_redirects=True
    )
    assert b"Customer name is required" in missing_name.data

    _create_customer(authed_client, token, name="Searchable Person")
    found = authed_client.get("/customers?q=Searchable")
    assert b"Searchable Person" in found.data
    not_found = authed_client.get("/customers?q=NoSuchCustomer")
    assert b"No matching customers" in not_found.data


def test_customer_edit_updates_vehicle(app, authed_client, page_token):
    _create_customer(authed_client, page_token())
    customer_id = _customer_id(app)

    response = authed_client.post(
        f"/customers/{customer_id}/edit",
        data={
            "_csrf_token": page_token(f"/customers/{customer_id}/edit"),
            "name": "Updated Customer",
            "plate": "UPD 456",
            "model": "Honda City",
            "address": "Valencia City",
            "technician": "Mark Dela Cruz",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Updated Customer" in response.data

    with app.app_context():
        customer = db.session.get(Customer, customer_id)
        assert customer.name == "Updated Customer"
        vehicle = db.session.scalar(
            select(Vehicle).where(Vehicle.customer_id == customer_id)
        )
        assert vehicle.plate == "UPD 456"
        assert vehicle.model == "Honda City"


def test_vehicle_create_and_duplicate_guard(app, authed_client, page_token):
    _create_customer(authed_client, page_token(), name="No Plate Customer", plate="")
    customer_id = _customer_id(app, "No Plate Customer")
    token = page_token("/vehicles")

    response = authed_client.post(
        "/vehicles",
        data={
            "_csrf_token": token,
            "customer_id": str(customer_id),
            "plate": "NEW 789",
            "model": "Ford Ranger",
            "technician": "Jun Reyes",
            "status": "Active",
        },
        follow_redirects=True,
    )
    assert b"NEW 789" in response.data

    duplicate = authed_client.post(
        "/vehicles",
        data={
            "_csrf_token": token,
            "customer_id": str(customer_id),
            "plate": "NEW 789",
            "model": "Ford Ranger",
        },
        follow_redirects=True,
    )
    assert b"already registered" in duplicate.data

    with app.app_context():
        assert (
            db.session.scalar(
                select(func.count(Vehicle.id)).where(Vehicle.plate == "NEW 789")
            )
            == 1
        )


def test_completed_service_request_creates_history(app, authed_client, page_token):
    _create_customer(authed_client, page_token())
    customer_id = _customer_id(app)

    response = authed_client.post(
        "/service-requests",
        data={
            "_csrf_token": page_token("/service-requests"),
            "customer_id": str(customer_id),
            "service": "Tire Replacement",
            "request_date": today_iso(),
            "status": "Completed",
            "technician": "Jun Reyes",
            "notes": "Replaced two front tires.",
        },
        follow_redirects=True,
    )
    assert b"Service request saved" in response.data

    with app.app_context():
        request = db.session.scalar(
            select(ServiceRequest).where(ServiceRequest.customer_id == customer_id)
        )
        assert request is not None
        assert request.status == "Completed"
        history = db.session.scalar(
            select(ServiceHistory).where(ServiceHistory.customer_id == customer_id)
        )
        assert history is not None
        assert history.service == "Tire Replacement"
        assert history.status == "Completed"


def test_appointment_create_and_duplicate_guard(app, authed_client, page_token):
    _create_customer(authed_client, page_token())
    customer_id = _customer_id(app)
    token = page_token("/appointments")
    payload = {
        "_csrf_token": token,
        "customer_id": str(customer_id),
        "service": "Wheel Alignment",
        "appointment_date": today_iso(),
        "appointment_time": "10:30",
    }

    first = authed_client.post("/appointments", data=payload, follow_redirects=True)
    assert b"Appointment scheduled" in first.data

    second = authed_client.post("/appointments", data=payload, follow_redirects=True)
    assert b"identical appointment" in second.data

    with app.app_context():
        assert (
            db.session.scalar(
                select(func.count(Appointment.id)).where(
                    Appointment.customer_id == customer_id
                )
            )
            == 1
        )


def test_feedback_and_notification_create(app, authed_client, page_token):
    _create_customer(authed_client, page_token())
    customer_id = _customer_id(app)

    feedback = authed_client.post(
        "/feedback",
        data={
            "_csrf_token": page_token("/feedback"),
            "customer_id": str(customer_id),
            "concern": "Customer requested an earlier service schedule.",
        },
        follow_redirects=True,
    )
    assert b"Feedback / concern saved" in feedback.data

    notification = authed_client.post(
        "/notifications",
        data={
            "_csrf_token": page_token("/notifications"),
            "customer_id": str(customer_id),
            "message": "Your vehicle is ready for pickup.",
        },
        follow_redirects=True,
    )
    assert b"Notification log saved" in notification.data

    with app.app_context():
        concern = db.session.scalar(
            select(FeedbackConcern).where(FeedbackConcern.customer_id == customer_id)
        )
        notice = db.session.scalar(
            select(Notification).where(Notification.customer_id == customer_id)
        )
        assert concern is not None and concern.status == "Pending"
        assert notice is not None and notice.status == "Pending"


def test_customer_delete_cascades_related_records(app, authed_client, page_token):
    _create_customer(authed_client, page_token())
    customer_id = _customer_id(app)
    today = today_iso()

    authed_client.post(
        "/service-requests",
        data={
            "_csrf_token": page_token("/service-requests"),
            "customer_id": str(customer_id),
            "service": "Brake Inspection",
            "request_date": today,
            "status": "Completed",
            "technician": "Mark Dela Cruz",
            "notes": "",
        },
    )
    authed_client.post(
        "/feedback",
        data={
            "_csrf_token": page_token("/feedback"),
            "customer_id": str(customer_id),
            "concern": "Follow-up needed.",
        },
    )
    authed_client.post(
        "/notifications",
        data={
            "_csrf_token": page_token("/notifications"),
            "customer_id": str(customer_id),
            "message": "Follow-up reminder.",
        },
    )

    response = authed_client.post(
        f"/customers/{customer_id}/delete",
        data={"_csrf_token": csrf_token(authed_client.get("/customers"))},
        follow_redirects=True,
    )
    assert b"and related records were deleted" in response.data

    with app.app_context():
        assert db.session.get(Customer, customer_id) is None
        for model in (Vehicle, ServiceRequest, ServiceHistory, FeedbackConcern, Notification):
            assert db.session.scalar(select(func.count(model.id))) == 0
