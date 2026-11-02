from datetime import date, timedelta

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from itsdangerous import BadSignature, URLSafeSerializer

from .. import booking_rules as rules
from .. import db
from ..forms import BookingForm
from ..models import Booking
from ..sms import send_confirmation, sms_enabled

main = Blueprint("main", __name__)


def _serializer():
    return URLSafeSerializer(current_app.config["SECRET_KEY"], salt="booking-ticket")


def booking_days():
    """Days a customer can pick, starting today."""
    today = rules.today_local()
    return [today + timedelta(days=i) for i in range(current_app.config["BOOKING_WINDOW_DAYS"] + 1)]


def first_open_day(car_type, wash_type):
    for day in booking_days()[:7]:
        if any(s["free"] for s in rules.available_slots(day, car_type, wash_type)):
            return day
    return rules.today_local()


def validate_booking_rules(form, exclude_id=None, customer=True):
    """Checks that need the database or the clock. Adds errors to the form; returns True if OK."""
    ok = True
    if customer and form.date.data:
        if form.date.data < rules.today_local() or form.date.data > rules.last_bookable_date():
            form.date.errors.append(
                f"Pick a day between today and {rules.nice_date(rules.last_bookable_date())}."
            )
            ok = False
    if ok and form.date.data and form.time.data:
        problem = rules.check_slot(
            form.date.data, form.time.data, form.car_type.data, form.wash_type.data,
            exclude_id=exclude_id, allow_past=not customer,
        )
        if problem:
            form.time.errors.append(problem)
            ok = False
    return ok


@main.route("/", methods=["GET", "POST"])
def index():
    form = BookingForm()
    if request.method == "GET" and not form.date.data:
        form.date.data = first_open_day(form.car_type.data, form.wash_type.data)

    if form.validate_on_submit() and validate_booking_rules(form):
        booking = Booking(
            name=form.name.data,
            contact_number=form.contact_number.data,
            car_plate=form.car_plate.data,
            car_type=form.car_type.data,
            wash_type=form.wash_type.data,
            date=form.date.data,
            time=form.time.data,
            status=rules.PENDING,
        )
        db.session.add(booking)
        db.session.commit()
        sent = send_confirmation(booking)
        token = _serializer().dumps(booking.id)
        return redirect(url_for("main.booked", token=token, sms=int(sent)))

    slots = []
    if form.date.data and form.car_type.data in rules.CAR_TYPES and form.wash_type.data in rules.WASH_TYPES:
        slots = rules.available_slots(form.date.data, form.car_type.data, form.wash_type.data)
    return render_template(
        "index.html",
        form=form,
        days=booking_days(),
        slots=slots,
        selected_time=form.time.raw_data[0] if form.time.raw_data else "",
    ), (422 if request.method == "POST" else 200)


@main.route("/slots")
def slots():
    """htmx partial: start times for the chosen day, car and wash."""
    try:
        day = date.fromisoformat(request.args.get("date", ""))
    except ValueError:
        day = rules.today_local()
    car_type = request.args.get("car_type", "Sedan")
    wash_type = request.args.get("wash_type", "Exterior")
    if car_type not in rules.CAR_TYPES or wash_type not in rules.WASH_TYPES:
        abort(400)
    return render_template(
        "partials/_slots.html",
        slots=rules.available_slots(day, car_type, wash_type),
        selected_time=request.args.get("time", ""),
        day=day,
        duration=rules.duration_for(car_type, wash_type),
    )


@main.route("/booked/<token>")
def booked(token):
    try:
        booking_id = _serializer().loads(token)
    except BadSignature:
        abort(404)
    booking = db.session.get(Booking, booking_id) or abort(404)
    return render_template(
        "booked.html",
        booking=booking,
        sms_sent=request.args.get("sms") == "1",
        sms_on=sms_enabled(),
    )
