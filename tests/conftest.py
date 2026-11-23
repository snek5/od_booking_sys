from datetime import timedelta

import pytest
from werkzeug.security import generate_password_hash

from app import create_app, db
from app import booking_rules as rules
from app.models import Admin, Booking


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
