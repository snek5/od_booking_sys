from datetime import datetime, timedelta, timezone

from flask_login import UserMixin

from . import db
from . import booking_rules as rules


def _utcnow():
    return datetime.now(timezone.utc)


class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    contact_number = db.Column(db.String(20), nullable=False)
    car_plate = db.Column(db.String(15), nullable=False)
    car_type = db.Column(db.String(50), nullable=False)
    wash_type = db.Column(db.String(50), nullable=False)
    date = db.Column(db.Date, nullable=False)
    time = db.Column(db.Time, nullable=False)
    status = db.Column(db.String(20), default=rules.PENDING)
    created_at = db.Column(db.DateTime, default=_utcnow)

    @property
    def duration(self):
        return rules.duration_for(self.car_type, self.wash_type)

    @property
    def start(self):
        return datetime.combine(self.date, self.time)

    @property
    def end(self):
        return self.start + timedelta(minutes=self.duration)

    @property
    def status_key(self):
        return rules.status_key(self.status)

    def to_event(self):
        """Shape used by FullCalendar on the admin calendar."""
        return {
            "id": self.id,
            "title": f"{self.car_plate} — {self.wash_type}",
            "start": self.start.isoformat(timespec="minutes"),
            "end": self.end.isoformat(timespec="minutes"),
            "classNames": [f"ev-{self.status_key}"],
            "extendedProps": {
                "plate": self.car_plate,
                "name": self.name,
                "contact": self.contact_number,
                "carType": self.car_type,
                "washType": self.wash_type,
                "status": self.status,
                "statusKey": self.status_key,
                "when": f"{rules.nice_date(self.date)}, {rules.nice_time(self.time)}"
                        f" – {rules.nice_time(self.end.time())}",
            },
        }

    def __repr__(self):
        return f"<Booking {self.id} {self.car_plate} {self.date} {self.time}>"


class Admin(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
