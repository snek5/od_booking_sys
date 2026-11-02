from datetime import datetime, time, timedelta

import pytest

from app import create_app, db
from app import booking_rules as rules
from app.models import Admin, Booking
from werkzeug.security import generate_password_hash


@pytest.fixture
def app():
    app = create_app("config.TestConfig")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def staff(client):
    db.session.add(Admin(username="desk", password=generate_password_hash("washwash")))
    db.session.commit()
    client.post("/admin/login", data={"username": "desk", "password": "washwash"})
    return client


def tomorrow():
    return rules.today_local() + timedelta(days=1)


def add(day, start, car="Sedan", wash="Polish", status=rules.PENDING):
    b = Booking(name="A B", contact_number="7123456", car_plate="BA 1", car_type=car,
                wash_type=wash, date=day, time=start, status=status)
    db.session.add(b)
    db.session.commit()
    return b


def book(client, **over):
    data = dict(car_plate="baa  1234", car_type="Sedan", wash_type="Exterior",
                date=tomorrow().isoformat(), time="10:00", name="Siti", contact_number="712 3456")
    data.update(over)
    return client.post("/", data=data)


def test_customer_booking_happy_path(client):
    res = book(client)
    assert res.status_code == 302 and "/booked/" in res.location
    b = Booking.query.one()
    assert (b.car_plate, b.contact_number, b.status) == ("BAA 1234", "7123456", "Pending")
    page = client.get(res.location)
    assert b"re booked</h1>" in page.data and b"BAA 1234" in page.data


def test_overlap_is_rejected_even_when_existing_booking_starts_earlier(client):
    add(tomorrow(), time(9, 30))  # sedan polish: 9:30–10:30
    res = book(client, time="10:00")
    assert res.status_code == 422
    assert b"just taken" in res.data
    assert Booking.query.count() == 1


def test_cancelled_bookings_free_their_slot(client):
    add(tomorrow(), time(10, 0), status=rules.CANCELLED)
    assert book(client).status_code == 302


def test_wash_must_finish_by_closing(client):
    res = book(client, time="17:45", car_type="Truck", wash_type="Polish")
    assert res.status_code == 422 and b"has to start between" in res.data


def test_past_day_rejected(client):
    res = book(client, date=(rules.today_local() - timedelta(days=1)).isoformat())
    assert res.status_code == 422


def test_slots_partial_marks_taken_times(client):
    add(tomorrow(), time(10, 0))
    res = client.get(f"/slots?date={tomorrow()}&car_type=Sedan&wash_type=Exterior")
    html = res.data.decode()
    assert 'value="10:30" required' in html  # free
    assert 'id="t-10:15" value="10:15" required\n               data-label="10:15 AM"\n               disabled' in html


def test_booking_token_cannot_be_guessed(client):
    assert client.get("/booked/1").status_code == 404


def test_durations_use_form_names(app):
    assert rules.duration_for("Truck", "Exterior") == 60  # used to fall back to 30


def test_register_only_open_for_first_account(client):
    assert client.get("/admin/register").status_code == 200
    client.post("/admin/register", data={"username": "boss", "password": "longenough", "confirm_password": "longenough"})
    client.post("/admin/logout")
    res = client.get("/admin/register")
    assert res.status_code == 302 and "/admin/login" in res.location


def test_staff_pages_need_login(client):
    for url in ["/admin/dashboard", "/admin/calendar", "/admin/booking/add", "/admin/api/bookings"]:
        assert client.get(url).status_code == 302


def test_edit_saves_every_field(staff):
    b = add(tomorrow(), time(11, 0))
    res = staff.post(f"/admin/booking/edit/{b.id}", data=dict(
        car_plate="kb 22", car_type="SUV", wash_type="Exterior", date=tomorrow().isoformat(),
        time="12:00", name="New Name", contact_number="8888888", status="Pending"))
    assert res.status_code == 302
    db.session.refresh(b)
    assert (b.car_plate, b.car_type, b.name, b.time) == ("KB 22", "SUV", "New Name", time(12, 0))


def test_admin_add_stores_real_dates(staff):
    res = staff.post("/admin/booking/add", data=dict(
        car_plate="BB 9", car_type="Sedan", wash_type="Exterior", date=tomorrow().isoformat(),
        time="15:00", name="Walk In", contact_number="7000000", status="Pending"))
    assert res.status_code == 302
    assert Booking.query.one().date == tomorrow()


def test_quick_status_change_returns_row(staff):
    b = add(tomorrow(), time(11, 0))
    res = staff.post(f"/admin/booking/{b.id}/status", data={"status": "Attended"}, headers={"HX-Request": "true"})
    assert res.status_code == 200 and b"status-attended" in res.data and res.data.lstrip().startswith(b"<tr")


def test_reopening_cancelled_booking_cannot_double_book(staff):
    old = add(tomorrow(), time(11, 0), status=rules.CANCELLED)
    add(tomorrow(), time(11, 0))
    res = staff.post(f"/admin/api/update-status/{old.id}", json={"status": "Pending"})
    assert res.status_code == 409


def test_calendar_feed(staff):
    add(tomorrow(), time(9, 0), car="Truck", wash="Interior + Exterior", status=rules.NO_SHOW)
    events = staff.get("/admin/api/bookings").get_json()
    assert events[0]["end"].endswith("T10:30")
    assert events[0]["classNames"] == ["ev-noshow"]


def test_dashboard_renders_with_filters(staff):
    add(rules.today_local(), time(17, 0))
    for q in ["", "?when=all&status=Pending", "?q=BA", "?on=" + rules.today_local().isoformat(), "?page=9"]:
        assert staff.get("/admin/dashboard" + q).status_code == 200
