from datetime import date, datetime, timedelta
from urllib.parse import urlsplit

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import func, or_
from werkzeug.security import check_password_hash, generate_password_hash

from .. import booking_rules as rules
from .. import db, login_manager
from ..forms import AdminBookingForm, LoginForm, RegisterForm
from ..models import Admin, Booking
from .main import validate_booking_rules

admin = Blueprint("admin", __name__)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(Admin, int(user_id))


def _safe_next(default_endpoint="admin.calendar_view"):
    target = request.values.get("next", "")
    parts = urlsplit(target)
    if target.startswith("/") and not target.startswith("//") and not parts.netloc and not parts.scheme:
        return target
    return url_for(default_endpoint)


def _is_htmx():
    return request.headers.get("HX-Request") == "true"


# ---------- accounts ----------

@admin.route("/")
def home():
    return redirect(url_for("admin.calendar_view"))


@admin.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("admin.calendar_view"))
    if Admin.query.count() == 0:
        flash("No staff accounts yet. Create the first one to get started.", "info")
        return redirect(url_for("admin.register"))

    form = LoginForm()
    if form.validate_on_submit():
        user = Admin.query.filter_by(username=form.username.data).first()
        if user and check_password_hash(user.password, form.password.data):
            login_user(user, remember=form.remember.data)
            return redirect(_safe_next())
        form.password.errors.append("That username and password don't match.")
    return render_template("login.html", form=form)


@admin.route("/register", methods=["GET", "POST"])
def register():
    first_account = Admin.query.count() == 0
    if not first_account and not current_user.is_authenticated:
        flash("Ask an existing staff member to add your account.", "info")
        return redirect(url_for("admin.login"))

    form = RegisterForm()
    if form.validate_on_submit():
        user = Admin(
            username=form.username.data,
            password=generate_password_hash(form.password.data),
        )
        db.session.add(user)
        db.session.commit()
        if first_account:
            login_user(user)
            flash(f"Welcome, {user.username}. This is the booking calendar.", "success")
            return redirect(url_for("admin.calendar_view"))
        flash(f"Staff account {user.username} added. They can log in now.", "success")
        return redirect(url_for("admin.staff"))

    template = "register.html" if first_account else "staff_add.html"
    return render_template(template, form=form)


@admin.route("/staff")
@login_required
def staff():
    return render_template("staff.html", staff=Admin.query.order_by(Admin.username).all())


@admin.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("You're logged out.", "info")
    return redirect(url_for("admin.login"))


# ---------- booking list ----------

WHEN_FILTERS = {
    "upcoming": "Today onwards",
    "today": "Today",
    "past": "Past",
    "all": "All dates",
}


@admin.route("/dashboard")
@login_required
def dashboard():
    today = rules.today_local()
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "")
    when = request.args.get("when", "upcoming")
    if when not in WHEN_FILTERS:
        when = "upcoming"
    on_date = request.args.get("on", "")
    try:
        on_date = date.fromisoformat(on_date) if on_date else None
    except ValueError:
        on_date = None

    query = Booking.query
    if q:
        like = f"%{q}%"
        query = query.filter(or_(
            Booking.name.ilike(like),
            Booking.car_plate.ilike(like),
            Booking.contact_number.ilike(like),
        ))
    if status in rules.STATUSES:
        query = query.filter(Booking.status == status)
    if on_date:
        query = query.filter(Booking.date == on_date)
    elif when == "today":
        query = query.filter(Booking.date == today)
    elif when == "upcoming":
        query = query.filter(Booking.date >= today)
    elif when == "past":
        query = query.filter(Booking.date < today)

    newest_first = when in ("past", "all") and not on_date
    if newest_first:
        query = query.order_by(Booking.date.desc(), Booking.time.desc())
    else:
        query = query.order_by(Booking.date.asc(), Booking.time.asc())

    page = request.args.get("page", 1, type=int)
    bookings = query.paginate(page=page, per_page=current_app.config["ADMIN_PAGE_SIZE"], error_out=False)

    # Today's numbers
    by_status = dict(
        db.session.query(Booking.status, func.count()).filter(Booking.date == today).group_by(Booking.status).all()
    )
    by_car = dict(
        db.session.query(Booking.car_type, func.count())
        .filter(Booking.date == today, Booking.status.in_(rules.BLOCKING_STATUSES))
        .group_by(Booking.car_type).all()
    )
    next_up = (
        Booking.query.filter(
            Booking.date == today,
            Booking.status == rules.PENDING,
            Booking.time >= (rules.now_local() - timedelta(minutes=30)).time(),
        ).order_by(Booking.time).first()
    )

    filters_active = bool(q or status or on_date or when != "upcoming")
    return render_template(
        "admin.html",
        bookings=bookings,
        q=q,
        status=status,
        when=when,
        on_date=on_date,
        when_filters=WHEN_FILTERS,
        filters_active=filters_active,
        by_status=by_status,
        by_car=by_car,
        today_total=sum(by_status.values()),
        next_up=next_up,
        today=today,
    )


# ---------- create / edit / delete ----------

@admin.route("/booking/add", methods=["GET", "POST"])
@login_required
def add_booking():
    form = AdminBookingForm()
    if request.method == "GET":
        if request.args.get("date"):
            try:
                form.date.data = date.fromisoformat(request.args["date"])
            except ValueError:
                pass
        if request.args.get("time"):
            try:
                form.time.data = datetime.strptime(request.args["time"], "%H:%M").time()
            except ValueError:
                pass
        form.date.data = form.date.data or rules.today_local()

    if form.validate_on_submit() and validate_booking_rules(form, customer=False):
        booking = Booking()
        form.populate_obj(booking)
        db.session.add(booking)
        db.session.commit()
        flash(f"Booking for {booking.car_plate} added.", "success")
        return redirect(_safe_next("admin.dashboard"))
    return render_template("booking_form.html", form=form, booking=None)


@admin.route("/booking/edit/<int:booking_id>", methods=["GET", "POST"])
@login_required
def edit_booking(booking_id):
    booking = db.session.get(Booking, booking_id) or abort(404)
    form = AdminBookingForm(obj=booking)

    if form.validate_on_submit():
        blocking = form.status.data in rules.BLOCKING_STATUSES
        if not blocking or validate_booking_rules(form, exclude_id=booking.id, customer=False):
            form.populate_obj(booking)
            db.session.commit()
            flash(f"Booking for {booking.car_plate} saved.", "success")
            return redirect(_safe_next("admin.dashboard"))
    return render_template("booking_form.html", form=form, booking=booking)


@admin.route("/booking/delete/<int:booking_id>", methods=["GET", "POST"])
@login_required
def delete_booking(booking_id):
    booking = db.session.get(Booking, booking_id) or abort(404)
    if request.method == "POST":
        plate = booking.car_plate
        db.session.delete(booking)
        db.session.commit()
        flash(f"Booking for {plate} deleted.", "success")
        return redirect(_safe_next("admin.dashboard"))
    return render_template("delete_booking.html", booking=booking)


@admin.route("/booking/<int:booking_id>/status", methods=["POST"])
@login_required
def set_status(booking_id):
    """Quick status change from the booking list (htmx) or a plain form."""
    booking = db.session.get(Booking, booking_id) or abort(404)
    new_status = request.form.get("status")
    if new_status not in rules.STATUSES:
        abort(400)
    problem = _reopen_problem(booking, new_status)
    if problem:
        if _is_htmx():
            return problem, 409
        flash(problem, "danger")
        return redirect(_safe_next("admin.dashboard"))
    booking.status = new_status
    db.session.commit()
    if _is_htmx():
        return render_template("partials/_booking_row.html", b=booking, today=rules.today_local(), flash_row=True)
    flash(f"{booking.car_plate} marked {new_status.lower()}.", "success")
    return redirect(_safe_next("admin.dashboard"))


def _reopen_problem(booking, new_status):
    """Putting a cancelled/no-show booking back on the schedule must not double-book the slot."""
    if new_status in rules.BLOCKING_STATUSES and booking.status not in rules.BLOCKING_STATUSES:
        if rules.check_slot(booking.date, booking.time, booking.car_type, booking.wash_type,
                            exclude_id=booking.id, allow_past=True):
            return f"Can't put {booking.car_plate} back: someone else is booked at that time now."
    return None


# ---------- calendar ----------

@admin.route("/calendar")
@login_required
def calendar_view():
    return render_template("calendar.html")


def _parse_fc_date(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return None


@admin.route("/api/bookings")
@login_required
def get_bookings():
    query = Booking.query
    start, end = _parse_fc_date(request.args.get("start")), _parse_fc_date(request.args.get("end"))
    if start:
        query = query.filter(Booking.date >= start)
    if end:
        query = query.filter(Booking.date <= end)
    return jsonify([b.to_event() for b in query.all()])


@admin.route("/api/update-status/<int:booking_id>", methods=["POST"])
@login_required
def update_booking_status(booking_id):
    booking = db.session.get(Booking, booking_id) or abort(404)
    data = request.get_json(silent=True) or {}
    status = data.get("status")
    if status not in rules.STATUSES:
        return jsonify({"success": False, "message": "Unknown status."}), 400
    problem = _reopen_problem(booking, status)
    if problem:
        return jsonify({"success": False, "message": problem}), 409
    booking.status = status
    db.session.commit()
    return jsonify({"success": True, "event": booking.to_event()})
