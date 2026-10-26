"""All page routes for the F2M Auto-Hub web application."""

from __future__ import annotations

from datetime import datetime
from io import BytesIO

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import joinedload

from .export import build_report_workbook
from .models import (
    Appointment,
    Customer,
    FeedbackConcern,
    Notification,
    ServiceHistory,
    ServiceRequest,
    Vehicle,
    Visit,
    db,
)
from .timeutil import now_str, pretty_date, report_range, today_iso
from .utils import (
    APPOINTMENT_STATUSES,
    CONCERN_STATUSES,
    HISTORY_STATUSES,
    NOTIFICATION_STATUSES,
    REQUEST_STATUSES,
    VEHICLE_STATUSES,
    add_history_if_missing,
    all_customers,
    choice_or_default,
    clean,
    customer_is_duplicate,
    first_vehicle_id,
    like_query,
    page_number,
    parse_int,
    plate_is_duplicate,
    safe_redirect_target,
    valid_date,
    valid_time,
)

bp = Blueprint("main", __name__)

PER_PAGE = 20
VISIT_PER_PAGE = 50


def _count(statement) -> int:
    return db.session.scalar(statement) or 0


def _per_page(default: int = PER_PAGE) -> int:
    return int(current_app.config.get("PER_PAGE", default))


def _paginate(statement, per_page: int | None = None):
    return db.paginate(
        statement,
        page=page_number(),
        per_page=per_page or _per_page(),
        error_out=False,
    )


def _customer_or_404(customer_id: int) -> Customer:
    return db.get_or_404(Customer, customer_id)


def _customer_name(customer: Customer | None) -> str:
    return customer.name if customer else "Unknown"


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


@bp.get("/")
def dashboard():
    today = today_iso()
    counts = {
        "customers": _count(select(func.count(Customer.id))),
        "vehicles": _count(select(func.count(Vehicle.id))),
        "requests": _count(
            select(func.count(ServiceRequest.id)).where(
                ServiceRequest.status.in_(["Pending", "In Progress"])
            )
        ),
        "appointments": _count(
            select(func.count(Appointment.id)).where(Appointment.status == "Scheduled")
        ),
        "concerns": _count(
            select(func.count(FeedbackConcern.id)).where(FeedbackConcern.status != "Resolved")
        ),
    }

    recent_requests = db.session.scalars(
        select(ServiceRequest)
        .options(joinedload(ServiceRequest.customer))
        .order_by(ServiceRequest.id.desc())
        .limit(8)
    ).all()
    todays_appointments = db.session.scalars(
        select(Appointment)
        .options(joinedload(Appointment.customer))
        .where(Appointment.appointment_date == today)
        .order_by(Appointment.appointment_time.asc())
    ).all()
    recent_concerns = db.session.scalars(
        select(FeedbackConcern)
        .options(joinedload(FeedbackConcern.customer))
        .where(FeedbackConcern.status != "Resolved")
        .order_by(FeedbackConcern.id.desc())
        .limit(5)
    ).all()
    recent_notifications = db.session.scalars(
        select(Notification)
        .options(joinedload(Notification.customer))
        .where(Notification.status == "Pending")
        .order_by(Notification.id.desc())
        .limit(5)
    ).all()

    return render_template(
        "dashboard.html",
        counts=counts,
        recent_requests=recent_requests,
        todays_appointments=todays_appointments,
        recent_concerns=recent_concerns,
        recent_notifications=recent_notifications,
        today=today,
    )


# ---------------------------------------------------------------------------
# Customer records
# ---------------------------------------------------------------------------


@bp.route("/customers", methods=["GET", "POST"])
def customers():
    if request.method == "POST":
        return _customer_create()

    q = clean(request.args.get("q"), 120)
    statement = select(Customer).order_by(Customer.id.desc())
    if q:
        like = like_query(q)
        statement = statement.where(
            or_(
                Customer.name.ilike(like),
                Customer.plate.ilike(like),
                Customer.model.ilike(like),
                Customer.address.ilike(like),
                Customer.technician.ilike(like),
            )
        )
    pagination = _paginate(statement)
    return render_template(
        "customers/index.html",
        customers=pagination.items,
        pagination=pagination,
        q=q,
        next_url=safe_redirect_target(request.args.get("next")) or "",
        status_choices=[],
    )


def _customer_form() -> dict[str, str]:
    return {
        "name": clean(request.form.get("name"), 200),
        "plate": clean(request.form.get("plate"), 50),
        "model": clean(request.form.get("model"), 120),
        "address": clean(request.form.get("address"), 255),
        "technician": clean(request.form.get("technician"), 120),
    }


def _customer_create():
    form = _customer_form()
    next_url = safe_redirect_target(request.form.get("next"))
    fallback = url_for("main.customers", next=next_url) if next_url else url_for("main.customers")

    if not form["name"]:
        flash("Customer name is required.", "error")
        return redirect(fallback)
    if customer_is_duplicate(form["name"], form["plate"]):
        flash(
            "A customer with the same name and plate number already exists. "
            "Search for the existing record instead of creating a duplicate.",
            "warning",
        )
        return redirect(fallback)

    now = now_str()
    customer = Customer(
        name=form["name"],
        plate=form["plate"],
        model=form["model"],
        address=form["address"],
        technician=form["technician"],
        created_at=now,
    )
    db.session.add(customer)
    db.session.flush()
    if form["plate"] or form["model"]:
        db.session.add(
            Vehicle(
                customer_id=customer.id,
                plate=form["plate"] or "N/A",
                model=form["model"],
                technician=form["technician"],
                status="Active",
                created_at=now,
            )
        )
    db.session.commit()
    flash(f"Customer “{customer.name}” was added.", "success")
    return redirect(next_url or url_for("main.customers"))


@bp.route("/customers/<int:customer_id>/edit", methods=["GET", "POST"])
def customer_edit(customer_id: int):
    customer = _customer_or_404(customer_id)
    if request.method == "POST":
        form = _customer_form()
        errors: dict[str, str] = {}
        if not form["name"]:
            errors["name"] = "Customer name is required."
        elif customer_is_duplicate(form["name"], form["plate"], exclude_id=customer.id):
            errors["name"] = "Another customer with the same name and plate already exists."
        if errors:
            for message in errors.values():
                flash(message, "error")
            return render_template(
                "customers/form.html", customer=customer, form=form, errors=errors
            ), 422

        customer.name = form["name"]
        customer.plate = form["plate"]
        customer.model = form["model"]
        customer.address = form["address"]
        customer.technician = form["technician"]

        vehicle = customer.vehicles[0] if customer.vehicles else None
        if vehicle:
            vehicle.plate = form["plate"] or "N/A"
            vehicle.model = form["model"]
            vehicle.technician = form["technician"]
        elif form["plate"] or form["model"]:
            db.session.add(
                Vehicle(
                    customer_id=customer.id,
                    plate=form["plate"] or "N/A",
                    model=form["model"],
                    technician=form["technician"],
                    status="Active",
                    created_at=now_str(),
                )
            )
        db.session.commit()
        flash(f"Customer “{customer.name}” was updated.", "success")
        return redirect(url_for("main.customers"))

    form = {
        "name": customer.name,
        "plate": customer.plate,
        "model": customer.model,
        "address": customer.address,
        "technician": customer.technician,
    }
    return render_template("customers/form.html", customer=customer, form=form, errors={})


@bp.post("/customers/<int:customer_id>/delete")
def customer_delete(customer_id: int):
    customer = _customer_or_404(customer_id)
    name = customer.name
    db.session.delete(customer)
    db.session.commit()
    flash(f"Customer “{name}” and related records were deleted.", "success")
    return redirect(url_for("main.customers"))


# ---------------------------------------------------------------------------
# Vehicles
# ---------------------------------------------------------------------------


@bp.route("/vehicles", methods=["GET", "POST"])
def vehicles():
    if request.method == "POST":
        customer_id = parse_int(request.form.get("customer_id"))
        customer = db.session.get(Customer, customer_id) if customer_id else None
        plate = clean(request.form.get("plate"), 50)
        if not customer or not plate:
            flash("Customer and plate number are required.", "error")
            return redirect(url_for("main.vehicles"))
        if plate_is_duplicate(plate):
            flash("This plate number is already registered. Check the existing vehicle first.", "warning")
            return redirect(url_for("main.vehicles"))
        db.session.add(
            Vehicle(
                customer_id=customer.id,
                plate=plate,
                model=clean(request.form.get("model"), 120),
                technician=clean(request.form.get("technician"), 120),
                status=choice_or_default(request.form.get("status"), VEHICLE_STATUSES, "Active"),
                created_at=now_str(),
            )
        )
        db.session.commit()
        flash(f"Vehicle {plate} was added for {customer.name}.", "success")
        return redirect(url_for("main.vehicles"))

    q = clean(request.args.get("q"), 120)
    statement = (
        select(Vehicle)
        .options(joinedload(Vehicle.customer))
        .order_by(Vehicle.id.desc())
    )
    if q:
        like = like_query(q)
        statement = statement.join(
            Customer, Vehicle.customer_id == Customer.id, isouter=True
        ).where(
            or_(
                Vehicle.plate.ilike(like),
                Vehicle.model.ilike(like),
                Vehicle.technician.ilike(like),
                Vehicle.status.ilike(like),
                Customer.name.ilike(like),
            )
        )
    pagination = _paginate(statement)
    return render_template(
        "vehicles/index.html",
        vehicles=pagination.items,
        pagination=pagination,
        q=q,
        customers=all_customers(),
        status_choices=VEHICLE_STATUSES,
    )


@bp.route("/vehicles/<int:vehicle_id>/edit", methods=["GET", "POST"])
def vehicle_edit(vehicle_id: int):
    vehicle = db.get_or_404(Vehicle, vehicle_id)
    if request.method == "POST":
        customer_id = parse_int(request.form.get("customer_id"))
        customer = db.session.get(Customer, customer_id) if customer_id else None
        plate = clean(request.form.get("plate"), 50)
        form = {
            "customer_id": request.form.get("customer_id", ""),
            "plate": plate,
            "model": clean(request.form.get("model"), 120),
            "technician": clean(request.form.get("technician"), 120),
            "status": choice_or_default(request.form.get("status"), VEHICLE_STATUSES, "Active"),
        }
        errors: dict[str, str] = {}
        if not customer:
            errors["customer_id"] = "Select a valid customer."
        if not plate:
            errors["plate"] = "Plate number is required."
        elif plate_is_duplicate(plate, exclude_id=vehicle.id):
            errors["plate"] = "This plate number is already registered."
        if errors:
            for message in errors.values():
                flash(message, "error")
            return render_template(
                "vehicles/form.html",
                vehicle=vehicle,
                customers=all_customers(),
                form=form,
                errors=errors,
                status_choices=VEHICLE_STATUSES,
            ), 422

        vehicle.customer_id = customer.id
        vehicle.plate = plate
        vehicle.model = form["model"]
        vehicle.technician = form["technician"]
        vehicle.status = form["status"]
        db.session.commit()
        flash(f"Vehicle {vehicle.plate} was updated.", "success")
        return redirect(url_for("main.vehicles"))

    form = {
        "customer_id": str(vehicle.customer_id or ""),
        "plate": vehicle.plate,
        "model": vehicle.model,
        "technician": vehicle.technician,
        "status": vehicle.status,
    }
    return render_template(
        "vehicles/form.html",
        vehicle=vehicle,
        customers=all_customers(),
        form=form,
        errors={},
        status_choices=VEHICLE_STATUSES,
    )


@bp.post("/vehicles/<int:vehicle_id>/delete")
def vehicle_delete(vehicle_id: int):
    vehicle = db.get_or_404(Vehicle, vehicle_id)
    plate = vehicle.plate
    db.session.delete(vehicle)
    db.session.commit()
    flash(f"Vehicle {plate} was deleted.", "success")
    return redirect(url_for("main.vehicles"))


# ---------------------------------------------------------------------------
# Service requests
# ---------------------------------------------------------------------------


@bp.route("/service-requests", methods=["GET", "POST"])
def service_requests():
    if request.method == "POST":
        customer_id = parse_int(request.form.get("customer_id"))
        customer = db.session.get(Customer, customer_id) if customer_id else None
        service = clean(request.form.get("service"), 200)
        request_date = clean(request.form.get("request_date"), 10)
        status = choice_or_default(request.form.get("status"), REQUEST_STATUSES, "Pending")
        technician = clean(request.form.get("technician"), 120)
        notes = clean(request.form.get("notes"), 2000)
        if not customer or not service or not valid_date(request_date):
            flash("Customer, service, and a valid date are required.", "error")
            return redirect(url_for("main.service_requests"))
        db.session.add(
            ServiceRequest(
                customer_id=customer.id,
                service=service,
                request_date=request_date,
                status=status,
                technician=technician,
                notes=notes,
                created_at=now_str(),
            )
        )
        if status == "Completed":
            add_history_if_missing(customer.id, service, request_date, technician, notes)
        db.session.commit()
        flash("Service request saved.", "success")
        return redirect(url_for("main.service_requests"))

    q = clean(request.args.get("q"), 120)
    statement = (
        select(ServiceRequest)
        .options(joinedload(ServiceRequest.customer))
        .order_by(ServiceRequest.id.desc())
    )
    if q:
        like = like_query(q)
        statement = statement.join(
            Customer, ServiceRequest.customer_id == Customer.id, isouter=True
        ).where(
            or_(
                ServiceRequest.service.ilike(like),
                ServiceRequest.status.ilike(like),
                ServiceRequest.technician.ilike(like),
                ServiceRequest.notes.ilike(like),
                Customer.name.ilike(like),
            )
        )
    pagination = _paginate(statement)
    return render_template(
        "service_requests/index.html",
        requests=pagination.items,
        pagination=pagination,
        q=q,
        customers=all_customers(),
        status_choices=REQUEST_STATUSES,
        today=today_iso(),
    )


@bp.route("/service-requests/<int:request_id>/edit", methods=["GET", "POST"])
def service_request_edit(request_id: int):
    service_request = db.get_or_404(ServiceRequest, request_id)
    if request.method == "POST":
        customer_id = parse_int(request.form.get("customer_id"))
        customer = db.session.get(Customer, customer_id) if customer_id else None
        form = {
            "customer_id": request.form.get("customer_id", ""),
            "service": clean(request.form.get("service"), 200),
            "request_date": clean(request.form.get("request_date"), 10),
            "status": choice_or_default(request.form.get("status"), REQUEST_STATUSES, "Pending"),
            "technician": clean(request.form.get("technician"), 120),
            "notes": clean(request.form.get("notes"), 2000),
        }
        errors: dict[str, str] = {}
        if not customer:
            errors["customer_id"] = "Select a valid customer."
        if not form["service"]:
            errors["service"] = "Service is required."
        if not valid_date(form["request_date"]):
            errors["request_date"] = "Use a valid date (YYYY-MM-DD)."
        if errors:
            for message in errors.values():
                flash(message, "error")
            return render_template(
                "service_requests/form.html",
                service_request=service_request,
                customers=all_customers(),
                form=form,
                errors=errors,
                status_choices=REQUEST_STATUSES,
            ), 422

        service_request.customer_id = customer.id
        service_request.service = form["service"]
        service_request.request_date = form["request_date"]
        service_request.status = form["status"]
        service_request.technician = form["technician"]
        service_request.notes = form["notes"]
        if form["status"] == "Completed":
            add_history_if_missing(
                customer.id,
                form["service"],
                form["request_date"],
                form["technician"],
                form["notes"],
            )
        db.session.commit()
        flash("Service request updated.", "success")
        return redirect(url_for("main.service_requests"))

    form = {
        "customer_id": str(service_request.customer_id or ""),
        "service": service_request.service,
        "request_date": service_request.request_date,
        "status": service_request.status,
        "technician": service_request.technician,
        "notes": service_request.notes,
    }
    return render_template(
        "service_requests/form.html",
        service_request=service_request,
        customers=all_customers(),
        form=form,
        errors={},
        status_choices=REQUEST_STATUSES,
    )


@bp.post("/service-requests/<int:request_id>/delete")
def service_request_delete(request_id: int):
    service_request = db.get_or_404(ServiceRequest, request_id)
    db.session.delete(service_request)
    db.session.commit()
    flash("Service request deleted.", "success")
    return redirect(url_for("main.service_requests"))


# ---------------------------------------------------------------------------
# Appointments
# ---------------------------------------------------------------------------


@bp.route("/appointments", methods=["GET", "POST"])
def appointments():
    if request.method == "POST":
        customer_id = parse_int(request.form.get("customer_id"))
        customer = db.session.get(Customer, customer_id) if customer_id else None
        service = clean(request.form.get("service"), 200)
        appointment_date = clean(request.form.get("appointment_date"), 10)
        appointment_time = clean(request.form.get("appointment_time"), 5)
        if (
            not customer
            or not service
            or not valid_date(appointment_date)
            or not valid_time(appointment_time)
        ):
            flash(
                "Select a customer and enter a service, a valid date (YYYY-MM-DD), "
                "and a time (HH:MM).",
                "error",
            )
            return redirect(url_for("main.appointments"))
        duplicate = db.session.scalar(
            select(Appointment.id).where(
                Appointment.customer_id == customer.id,
                Appointment.service == service,
                Appointment.appointment_date == appointment_date,
                Appointment.appointment_time == appointment_time,
            )
        )
        if duplicate:
            flash("An identical appointment is already scheduled.", "warning")
            return redirect(url_for("main.appointments"))
        db.session.add(
            Appointment(
                customer_id=customer.id,
                service=service,
                appointment_date=appointment_date,
                appointment_time=appointment_time,
                status="Scheduled",
                created_at=now_str(),
            )
        )
        db.session.commit()
        flash("Appointment scheduled.", "success")
        return redirect(url_for("main.appointments"))

    q = clean(request.args.get("q"), 120)
    statement = (
        select(Appointment)
        .options(joinedload(Appointment.customer))
        .order_by(Appointment.appointment_date.desc(), Appointment.appointment_time.desc())
    )
    if q:
        like = like_query(q)
        statement = statement.join(
            Customer, Appointment.customer_id == Customer.id, isouter=True
        ).where(
            or_(
                Appointment.service.ilike(like),
                Appointment.status.ilike(like),
                Appointment.appointment_date.ilike(like),
                Customer.name.ilike(like),
            )
        )
    pagination = _paginate(statement)
    return render_template(
        "appointments/index.html",
        appointments=pagination.items,
        pagination=pagination,
        q=q,
        customers=all_customers(),
        today=today_iso(),
    )


@bp.route("/appointments/<int:appointment_id>/edit", methods=["GET", "POST"])
def appointment_edit(appointment_id: int):
    appointment = db.get_or_404(Appointment, appointment_id)
    if request.method == "POST":
        customer_id = parse_int(request.form.get("customer_id"))
        customer = db.session.get(Customer, customer_id) if customer_id else None
        form = {
            "customer_id": request.form.get("customer_id", ""),
            "service": clean(request.form.get("service"), 200),
            "appointment_date": clean(request.form.get("appointment_date"), 10),
            "appointment_time": clean(request.form.get("appointment_time"), 5),
            "status": choice_or_default(request.form.get("status"), APPOINTMENT_STATUSES, "Scheduled"),
        }
        errors: dict[str, str] = {}
        if not customer:
            errors["customer_id"] = "Select a valid customer."
        if not form["service"]:
            errors["service"] = "Service is required."
        if not valid_date(form["appointment_date"]):
            errors["appointment_date"] = "Use a valid date (YYYY-MM-DD)."
        if not valid_time(form["appointment_time"]):
            errors["appointment_time"] = "Use a valid time (HH:MM)."
        if errors:
            for message in errors.values():
                flash(message, "error")
            return render_template(
                "appointments/form.html",
                appointment=appointment,
                customers=all_customers(),
                form=form,
                errors=errors,
                status_choices=APPOINTMENT_STATUSES,
            ), 422

        appointment.customer_id = customer.id
        appointment.service = form["service"]
        appointment.appointment_date = form["appointment_date"]
        appointment.appointment_time = form["appointment_time"]
        appointment.status = form["status"]
        db.session.commit()
        flash("Appointment updated.", "success")
        return redirect(url_for("main.appointments"))

    form = {
        "customer_id": str(appointment.customer_id or ""),
        "service": appointment.service,
        "appointment_date": appointment.appointment_date,
        "appointment_time": appointment.appointment_time,
        "status": appointment.status,
    }
    return render_template(
        "appointments/form.html",
        appointment=appointment,
        customers=all_customers(),
        form=form,
        errors={},
        status_choices=APPOINTMENT_STATUSES,
    )


@bp.post("/appointments/<int:appointment_id>/delete")
def appointment_delete(appointment_id: int):
    appointment = db.get_or_404(Appointment, appointment_id)
    db.session.delete(appointment)
    db.session.commit()
    flash("Appointment deleted.", "success")
    return redirect(url_for("main.appointments"))


# ---------------------------------------------------------------------------
# Service history
# ---------------------------------------------------------------------------


@bp.route("/service-history", methods=["GET", "POST"])
def service_history():
    if request.method == "POST":
        customer_id = parse_int(request.form.get("customer_id"))
        customer = db.session.get(Customer, customer_id) if customer_id else None
        service = clean(request.form.get("service"), 200)
        service_date = clean(request.form.get("service_date"), 10)
        technician = clean(request.form.get("technician"), 120)
        notes = clean(request.form.get("notes"), 2000)
        if not customer or not service or not valid_date(service_date):
            flash("Customer, service, and a valid date are required.", "error")
            return redirect(url_for("main.service_history"))
        db.session.add(
            ServiceHistory(
                customer_id=customer.id,
                vehicle_id=first_vehicle_id(customer.id),
                service=service,
                service_date=service_date,
                technician=technician,
                status="Completed",
                notes=notes,
            )
        )
        db.session.commit()
        flash("Service history record added.", "success")
        return redirect(url_for("main.service_history"))

    q = clean(request.args.get("q"), 120)
    statement = (
        select(ServiceHistory)
        .options(joinedload(ServiceHistory.customer))
        .order_by(ServiceHistory.service_date.desc(), ServiceHistory.id.desc())
    )
    if q:
        like = like_query(q)
        statement = statement.join(
            Customer, ServiceHistory.customer_id == Customer.id, isouter=True
        ).where(
            or_(
                ServiceHistory.service.ilike(like),
                ServiceHistory.technician.ilike(like),
                ServiceHistory.status.ilike(like),
                ServiceHistory.notes.ilike(like),
                Customer.name.ilike(like),
            )
        )
    pagination = _paginate(statement)
    return render_template(
        "service_history/index.html",
        history=pagination.items,
        pagination=pagination,
        q=q,
        customers=all_customers(),
        today=today_iso(),
    )


@bp.route("/service-history/<int:history_id>/edit", methods=["GET", "POST"])
def service_history_edit(history_id: int):
    record = db.get_or_404(ServiceHistory, history_id)
    if request.method == "POST":
        customer_id = parse_int(request.form.get("customer_id"))
        customer = db.session.get(Customer, customer_id) if customer_id else None
        form = {
            "customer_id": request.form.get("customer_id", ""),
            "service": clean(request.form.get("service"), 200),
            "service_date": clean(request.form.get("service_date"), 10),
            "technician": clean(request.form.get("technician"), 120),
            "status": choice_or_default(request.form.get("status"), HISTORY_STATUSES, "Completed"),
            "notes": clean(request.form.get("notes"), 2000),
        }
        errors: dict[str, str] = {}
        if not customer:
            errors["customer_id"] = "Select a valid customer."
        if not form["service"]:
            errors["service"] = "Service is required."
        if not valid_date(form["service_date"]):
            errors["service_date"] = "Use a valid date (YYYY-MM-DD)."
        if errors:
            for message in errors.values():
                flash(message, "error")
            return render_template(
                "service_history/form.html",
                record=record,
                customers=all_customers(),
                form=form,
                errors=errors,
                status_choices=HISTORY_STATUSES,
            ), 422

        record.customer_id = customer.id
        record.vehicle_id = first_vehicle_id(customer.id)
        record.service = form["service"]
        record.service_date = form["service_date"]
        record.technician = form["technician"]
        record.status = form["status"]
        record.notes = form["notes"]
        db.session.commit()
        flash("Service history record updated.", "success")
        return redirect(url_for("main.service_history"))

    form = {
        "customer_id": str(record.customer_id or ""),
        "service": record.service,
        "service_date": record.service_date,
        "technician": record.technician,
        "status": record.status,
        "notes": record.notes,
    }
    return render_template(
        "service_history/form.html",
        record=record,
        customers=all_customers(),
        form=form,
        errors={},
        status_choices=HISTORY_STATUSES,
    )


@bp.post("/service-history/<int:history_id>/delete")
def service_history_delete(history_id: int):
    record = db.get_or_404(ServiceHistory, history_id)
    db.session.delete(record)
    db.session.commit()
    flash("Service history record deleted.", "success")
    return redirect(url_for("main.service_history"))


# ---------------------------------------------------------------------------
# Feedback / concerns
# ---------------------------------------------------------------------------


@bp.route("/feedback", methods=["GET", "POST"])
def feedback():
    if request.method == "POST":
        customer_id = parse_int(request.form.get("customer_id"))
        customer = db.session.get(Customer, customer_id) if customer_id else None
        concern = clean(request.form.get("concern"), 2000)
        if not customer or not concern:
            flash("Select a customer and enter the concern.", "error")
            return redirect(url_for("main.feedback"))
        db.session.add(
            FeedbackConcern(
                customer_id=customer.id,
                concern=concern,
                status="Pending",
                created_at=now_str(),
            )
        )
        db.session.commit()
        flash("Feedback / concern saved.", "success")
        return redirect(url_for("main.feedback"))

    q = clean(request.args.get("q"), 120)
    statement = (
        select(FeedbackConcern)
        .options(joinedload(FeedbackConcern.customer))
        .order_by(FeedbackConcern.id.desc())
    )
    if q:
        like = like_query(q)
        statement = statement.join(
            Customer, FeedbackConcern.customer_id == Customer.id, isouter=True
        ).where(
            or_(
                FeedbackConcern.concern.ilike(like),
                FeedbackConcern.status.ilike(like),
                Customer.name.ilike(like),
            )
        )
    pagination = _paginate(statement)
    return render_template(
        "feedback/index.html",
        concerns=pagination.items,
        pagination=pagination,
        q=q,
        customers=all_customers(),
        status_choices=CONCERN_STATUSES,
    )


@bp.route("/feedback/<int:concern_id>/edit", methods=["GET", "POST"])
def feedback_edit(concern_id: int):
    concern = db.get_or_404(FeedbackConcern, concern_id)
    if request.method == "POST":
        customer_id = parse_int(request.form.get("customer_id"))
        customer = db.session.get(Customer, customer_id) if customer_id else None
        form = {
            "customer_id": request.form.get("customer_id", ""),
            "concern": clean(request.form.get("concern"), 2000),
            "status": choice_or_default(request.form.get("status"), CONCERN_STATUSES, "Pending"),
        }
        errors: dict[str, str] = {}
        if not customer:
            errors["customer_id"] = "Select a valid customer."
        if not form["concern"]:
            errors["concern"] = "Feedback / concern is required."
        if errors:
            for message in errors.values():
                flash(message, "error")
            return render_template(
                "feedback/form.html",
                concern=concern,
                customers=all_customers(),
                form=form,
                errors=errors,
                status_choices=CONCERN_STATUSES,
            ), 422

        concern.customer_id = customer.id
        concern.concern = form["concern"]
        concern.status = form["status"]
        db.session.commit()
        flash("Feedback / concern updated.", "success")
        return redirect(url_for("main.feedback"))

    form = {
        "customer_id": str(concern.customer_id or ""),
        "concern": concern.concern,
        "status": concern.status,
    }
    return render_template(
        "feedback/form.html",
        concern=concern,
        customers=all_customers(),
        form=form,
        errors={},
        status_choices=CONCERN_STATUSES,
    )


@bp.post("/feedback/<int:concern_id>/delete")
def feedback_delete(concern_id: int):
    concern = db.get_or_404(FeedbackConcern, concern_id)
    db.session.delete(concern)
    db.session.commit()
    flash("Feedback / concern deleted.", "success")
    return redirect(url_for("main.feedback"))


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------


@bp.route("/notifications", methods=["GET", "POST"])
def notifications():
    if request.method == "POST":
        customer_id = parse_int(request.form.get("customer_id"))
        customer = db.session.get(Customer, customer_id) if customer_id else None
        message = clean(request.form.get("message"), 2000)
        if not customer or not message:
            flash("Select a customer and enter a message.", "error")
            return redirect(url_for("main.notifications"))
        db.session.add(
            Notification(
                customer_id=customer.id,
                message=message,
                notification_date=now_str(),
                status="Pending",
            )
        )
        db.session.commit()
        flash("Notification log saved.", "success")
        return redirect(url_for("main.notifications"))

    q = clean(request.args.get("q"), 120)
    statement = (
        select(Notification)
        .options(joinedload(Notification.customer))
        .order_by(Notification.id.desc())
    )
    if q:
        like = like_query(q)
        statement = statement.join(
            Customer, Notification.customer_id == Customer.id, isouter=True
        ).where(
            or_(
                Notification.message.ilike(like),
                Notification.status.ilike(like),
                Customer.name.ilike(like),
            )
        )
    pagination = _paginate(statement)
    return render_template(
        "notifications/index.html",
        notifications=pagination.items,
        pagination=pagination,
        q=q,
        customers=all_customers(),
        status_choices=NOTIFICATION_STATUSES,
    )


@bp.route("/notifications/<int:notification_id>/edit", methods=["GET", "POST"])
def notification_edit(notification_id: int):
    notification = db.get_or_404(Notification, notification_id)
    if request.method == "POST":
        customer_id = parse_int(request.form.get("customer_id"))
        customer = db.session.get(Customer, customer_id) if customer_id else None
        form = {
            "customer_id": request.form.get("customer_id", ""),
            "message": clean(request.form.get("message"), 2000),
            "status": choice_or_default(
                request.form.get("status"), NOTIFICATION_STATUSES, "Pending"
            ),
        }
        errors: dict[str, str] = {}
        if not customer:
            errors["customer_id"] = "Select a valid customer."
        if not form["message"]:
            errors["message"] = "Message is required."
        if errors:
            for message in errors.values():
                flash(message, "error")
            return render_template(
                "notifications/form.html",
                notification=notification,
                customers=all_customers(),
                form=form,
                errors=errors,
                status_choices=NOTIFICATION_STATUSES,
            ), 422

        notification.customer_id = customer.id
        notification.message = form["message"]
        notification.status = form["status"]
        db.session.commit()
        flash("Notification updated.", "success")
        return redirect(url_for("main.notifications"))

    form = {
        "customer_id": str(notification.customer_id or ""),
        "message": notification.message,
        "status": notification.status,
    }
    return render_template(
        "notifications/form.html",
        notification=notification,
        customers=all_customers(),
        form=form,
        errors={},
        status_choices=NOTIFICATION_STATUSES,
    )


@bp.post("/notifications/<int:notification_id>/delete")
def notification_delete(notification_id: int):
    notification = db.get_or_404(Notification, notification_id)
    db.session.delete(notification)
    db.session.commit()
    flash("Notification deleted.", "success")
    return redirect(url_for("main.notifications"))


# ---------------------------------------------------------------------------
# Daily visits
# ---------------------------------------------------------------------------


@bp.get("/visits")
def visits():
    dates = list(
        db.session.scalars(
            select(Visit.visit_date).distinct().order_by(Visit.visit_date.desc())
        ).all()
    )
    requested = clean(request.args.get("date"), 10)
    if requested in dates:
        selected_date = requested
    elif today_iso() in dates:
        selected_date = today_iso()
    elif dates:
        selected_date = dates[0]
    else:
        selected_date = requested or today_iso()

    q = clean(request.args.get("q"), 120)
    base_statement = select(Visit).where(Visit.visit_date == selected_date)
    if q:
        like = like_query(q)
        base_statement = base_statement.where(
            or_(
                Visit.customer_name.ilike(like),
                Visit.plate.ilike(like),
                Visit.model.ilike(like),
                Visit.address.ilike(like),
                Visit.technician.ilike(like),
                Visit.record_no.ilike(like),
            )
        )
    statement = base_statement.order_by(Visit.id.asc())
    pagination = _paginate(statement, per_page=VISIT_PER_PAGE)

    total_visits = _count(
        select(func.count(Visit.id)).where(Visit.visit_date == selected_date)
    )
    unique_plates = _count(
        select(func.count(func.distinct(Visit.plate))).where(Visit.visit_date == selected_date)
    )
    unique_customers = _count(
        select(func.count(func.distinct(Visit.customer_name))).where(
            Visit.visit_date == selected_date
        )
    )

    return render_template(
        "visits/index.html",
        visits=pagination.items,
        pagination=pagination,
        dates=dates,
        selected_date=selected_date,
        q=q,
        total_visits=total_visits,
        unique_plates=unique_plates,
        unique_customers=unique_customers,
    )


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


def _parse_report_args() -> tuple[str, str, datetime.date]:
    report_type = (request.args.get("type") or "Daily").strip().title()
    if report_type not in {"Daily", "Weekly", "Monthly"}:
        report_type = "Daily"
    reference_text = (request.args.get("date") or today_iso()).strip()
    if not valid_date(reference_text):
        reference_text = today_iso()
    reference = datetime.strptime(reference_text, "%Y-%m-%d").date()
    return report_type, reference_text, reference


def _report_data(report_type: str, reference) -> dict:
    start, end = report_range(report_type, reference)
    start_iso, end_iso = start.isoformat(), end.isoformat()

    visits = db.session.scalars(
        select(Visit)
        .where(Visit.visit_date.between(start_iso, end_iso))
        .order_by(Visit.visit_date.asc(), Visit.id.asc())
    ).all()
    customers = db.session.scalars(select(Customer).order_by(Customer.name.asc())).all()
    appointments = db.session.scalars(
        select(Appointment)
        .options(joinedload(Appointment.customer))
        .where(Appointment.appointment_date.between(start_iso, end_iso))
        .order_by(Appointment.appointment_date.asc(), Appointment.appointment_time.asc())
    ).all()
    requests = db.session.scalars(
        select(ServiceRequest)
        .options(joinedload(ServiceRequest.customer))
        .where(ServiceRequest.request_date.between(start_iso, end_iso))
        .order_by(ServiceRequest.request_date.asc(), ServiceRequest.id.asc())
    ).all()
    history = db.session.scalars(
        select(ServiceHistory)
        .options(joinedload(ServiceHistory.customer))
        .where(ServiceHistory.service_date.between(start_iso, end_iso))
        .order_by(ServiceHistory.service_date.asc(), ServiceHistory.id.asc())
    ).all()
    concerns = db.session.scalars(
        select(FeedbackConcern)
        .options(joinedload(FeedbackConcern.customer))
        .where(func.substr(FeedbackConcern.created_at, 1, 10).between(start_iso, end_iso))
        .order_by(FeedbackConcern.created_at.desc())
    ).all()
    notifications = db.session.scalars(
        select(Notification)
        .options(joinedload(Notification.customer))
        .where(func.substr(Notification.notification_date, 1, 10).between(start_iso, end_iso))
        .order_by(Notification.notification_date.desc())
    ).all()

    return {
        "start": start,
        "end": end,
        "visits": visits,
        "customers": customers,
        "appointments": appointments,
        "requests": requests,
        "history": history,
        "concerns": concerns,
        "notifications": notifications,
        "counts": {
            "visits": len(visits),
            "customers": len(customers),
            "appointments": len(appointments),
            "requests": len(requests),
            "history": len(history),
            "concerns": len(concerns),
            "notifications": len(notifications),
        },
    }


@bp.get("/reports")
def reports():
    report_type, reference_text, reference = _parse_report_args()
    data = _report_data(report_type, reference)
    return render_template(
        "reports/index.html",
        report_type=report_type,
        reference_text=reference_text,
        start=data["start"],
        end=data["end"],
        visits=data["visits"],
        counts=data["counts"],
        period_label=f"{pretty_date(data['start'].isoformat())} – {pretty_date(data['end'].isoformat())}",
        export_url=url_for(
            "main.report_export", type=report_type, date=reference_text
        ),
    )


@bp.get("/reports/export")
def report_export():
    report_type, reference_text, reference = _parse_report_args()
    data = _report_data(report_type, reference)
    buffer: BytesIO = build_report_workbook(
        report_type,
        data["start"],
        data["end"],
        data["visits"],
        data["customers"],
        data["appointments"],
        data["requests"],
        data["history"],
        data["concerns"],
        data["notifications"],
    )
    filename = (
        f"F2M_AutoHub_{report_type}_{data['start'].isoformat()}_to_{data['end'].isoformat()}.xlsx"
    )
    return send_file(
        buffer,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        max_age=0,
    )


# ---------------------------------------------------------------------------
# Health and misc
# ---------------------------------------------------------------------------


@bp.get("/healthz")
def healthz():
    try:
        db.session.execute(text("SELECT 1"))
    except Exception:  # pragma: no cover - only on database outage
        current_app.logger.exception("Health check failed")
        return jsonify(status="error", service="f2m-autohub"), 503
    return jsonify(status="ok", service="f2m-autohub")


@bp.get("/favicon.ico")
def favicon():
    return redirect(url_for("static", filename="img/favicon.svg"))
