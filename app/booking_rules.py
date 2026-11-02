"""Everything the app knows about car types, washes, statuses and scheduling.

Keep the vocabulary here so the forms, the calendar, the dashboard and the SMS
all agree on the same names.
"""
import threading
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from flask import current_app

CAR_TYPES = ["Sedan", "SUV", "Truck", "Others"]
WASH_TYPES = ["Exterior", "Interior + Exterior", "Polish"]

# Minutes a wash takes, by car type then wash type.
WASH_DURATIONS = {
    "Sedan": {"Exterior": 30, "Interior + Exterior": 45, "Polish": 60},
    "SUV": {"Exterior": 45, "Interior + Exterior": 60, "Polish": 90},
    "Truck": {"Exterior": 60, "Interior + Exterior": 90, "Polish": 120},
    "Others": {"Exterior": 45, "Interior + Exterior": 60, "Polish": 90},
}

WASH_DESCRIPTIONS = {
    "Exterior": "Body rinse, foam wash, wheels and dry.",
    "Interior + Exterior": "Full outside wash plus vacuum, dash and windows inside.",
    "Polish": "Full wash finished with a machine polish and wax.",
}

PENDING = "Pending"
ATTENDED = "Attended"
NO_SHOW = "No Show"
CANCELLED = "Cancelled"
STATUSES = [PENDING, ATTENDED, NO_SHOW, CANCELLED]
# Bookings with these statuses keep their slot taken.
BLOCKING_STATUSES = (PENDING, ATTENDED)
# CSS modifier per status, shared by badges and calendar events.
STATUS_KEYS = {PENDING: "pending", ATTENDED: "attended", NO_SHOW: "noshow", CANCELLED: "cancelled"}


# Held while checking a slot and saving the booking, so two people submitting the
# same time at once can't both get it. Works because the server runs one process
# (see Dockerfile); with several processes, use a database-level lock instead.
booking_lock = threading.Lock()


def duration_for(car_type, wash_type):
    return WASH_DURATIONS.get(car_type, WASH_DURATIONS["Others"]).get(wash_type, 30)


def status_key(status):
    return STATUS_KEYS.get(status, "pending")


# ---------- time helpers ----------

def _parse_hhmm(value):
    return datetime.strptime(value, "%H:%M").time()


def open_time():
    return _parse_hhmm(current_app.config["OPEN_TIME"])


def close_time():
    return _parse_hhmm(current_app.config["CLOSE_TIME"])


def now_local():
    """Current wall-clock time at the shop, as a naive datetime."""
    tz = ZoneInfo(current_app.config["TIMEZONE"])
    return datetime.now(tz).replace(tzinfo=None)


def today_local():
    return now_local().date()


def last_bookable_date():
    return today_local() + timedelta(days=current_app.config["BOOKING_WINDOW_DAYS"])


def nice_date(value):
    if not value:
        return ""
    if isinstance(value, str):
        value = date.fromisoformat(value)
    today = today_local()
    if value == today:
        prefix = "Today, "
    elif value == today + timedelta(days=1):
        prefix = "Tomorrow, "
    else:
        prefix = value.strftime("%a ")
    return f"{prefix}{value.day} {value.strftime('%b %Y')}"


def nice_time(value):
    if not value:
        return ""
    if isinstance(value, str):
        value = _parse_hhmm(value[:5])
    return value.strftime("%I:%M %p").lstrip("0")


def format_duration(minutes):
    hours, mins = divmod(minutes, 60)
    if hours and mins:
        return f"{hours} h {mins} min"
    if hours:
        return f"{hours} h"
    return f"{mins} min"


# ---------- availability ----------

def _minutes(t):
    return t.hour * 60 + t.minute


def _busy_intervals(day, exclude_id=None):
    from .models import Booking

    query = Booking.query.filter(Booking.date == day, Booking.status.in_(BLOCKING_STATUSES))
    if exclude_id:
        query = query.filter(Booking.id != exclude_id)
    intervals = []
    for b in query.all():
        start = _minutes(b.time)
        intervals.append((start, start + b.duration))
    return intervals


def _fits(start, end, busy, bays):
    overlapping = sum(1 for b_start, b_end in busy if b_start < end and start < b_end)
    return overlapping < bays


def check_slot(day, start, car_type, wash_type, exclude_id=None, allow_past=False):
    """Return None if the slot can be booked, otherwise a message saying why not."""
    duration = duration_for(car_type, wash_type)
    start_m = _minutes(start)
    end_m = start_m + duration
    if start_m < _minutes(open_time()) or end_m > _minutes(close_time()):
        return (
            f"A {wash_type.lower()} wash for a {car_type} takes {format_duration(duration)}, "
            f"so it has to start between {nice_time(open_time())} and "
            f"{nice_time((datetime.combine(day, close_time()) - timedelta(minutes=duration)).time())}."
        )
    if not allow_past and datetime.combine(day, start) <= now_local():
        return "That time has already passed. Pick a later time."
    if not _fits(start_m, end_m, _busy_intervals(day, exclude_id), current_app.config["WASH_BAYS"]):
        return "That time was just taken. Pick another time."
    return None


def available_slots(day, car_type, wash_type, exclude_id=None):
    """All start times for the day, each marked free or taken."""
    duration = duration_for(car_type, wash_type)
    step = current_app.config["SLOT_MINUTES"]
    busy = _busy_intervals(day, exclude_id)
    bays = current_app.config["WASH_BAYS"]
    now = now_local()

    slots = []
    start = _minutes(open_time())
    last_start = _minutes(close_time()) - duration
    while start <= last_start:
        t = time(start // 60, start % 60)
        past = datetime.combine(day, t) <= now
        free = not past and _fits(start, start + duration, busy, bays)
        slots.append({"time": t, "value": t.strftime("%H:%M"), "free": free, "past": past})
        start += step
    return slots
