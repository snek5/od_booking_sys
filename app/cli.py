import random
from datetime import timedelta

import click
from werkzeug.security import generate_password_hash

from . import booking_rules as rules
from . import db
from .models import Admin, Booking

FIRST = ["Ahmad", "Siti", "Hj Rahman", "Nurul", "Daniel", "Mei Ling", "Azlan", "Farah", "Kevin", "Aisyah", "Hafiz", "Rosnah"]
LAST = ["Ali", "Abdullah", "Tan", "Lim", "Ismail", "Yusof", "Wong", "Hamid", "Osman", "Chong"]
PREFIXES = ["BA", "BB", "BC", "BD", "BE", "BF", "BG", "BH", "KA", "KB", "TA", "BAA", "BAB"]


def register_cli(app):
    @app.cli.command("create-admin")
    @click.argument("username")
    @click.password_option(envvar="ADMIN_PASSWORD")
    @click.option("--if-missing", is_flag=True, help="Do nothing if the account already exists.")
    def create_admin(username, password, if_missing):
        """Create a staff account."""
        if Admin.query.filter_by(username=username).first():
            if if_missing:
                click.echo(f"Staff account {username} already exists.")
                return
            raise click.ClickException(f"{username} already exists.")
        if len(password) < 8:
            raise click.ClickException("Use a password of at least 8 characters.")
        db.session.add(Admin(username=username, password=generate_password_hash(password)))
        db.session.commit()
        click.echo(f"Staff account {username} created.")

    @app.cli.command("seed")
    @click.option("--days", default=14, help="Spread bookings over this many days around today.")
    @click.option("--per-day", default=8, help="Bookings to try to fit into each day.")
    def seed(days, per_day):
        """Add realistic demo bookings that don't overlap."""
        today = rules.today_local()
        made = 0
        for offset in range(-days // 2, days - days // 2):
            day = today + timedelta(days=offset)
            for _ in range(per_day):
                car = random.choice(rules.CAR_TYPES)
                wash = random.choice(rules.WASH_TYPES)
                slots = [s for s in _all_free(day, car, wash)]
                if not slots:
                    continue
                slot = random.choice(slots)
                if day < today:
                    status = random.choices(
                        [rules.ATTENDED, rules.NO_SHOW, rules.CANCELLED], weights=[8, 1, 1]
                    )[0]
                else:
                    status = random.choices([rules.PENDING, rules.CANCELLED], weights=[12, 1])[0]
                db.session.add(Booking(
                    name=f"{random.choice(FIRST)} {random.choice(LAST)}",
                    contact_number=f"{random.choice('78')}{random.randint(0, 999999):06d}",
                    car_plate=f"{random.choice(PREFIXES)} {random.randint(1, 9999)}",
                    car_type=car,
                    wash_type=wash,
                    date=day,
                    time=slot,
                    status=status,
                ))
                db.session.commit()
                made += 1
        click.echo(f"Added {made} demo bookings.")


def _all_free(day, car, wash):
    """Free start times ignoring the clock (seed can fill past days)."""
    duration = rules.duration_for(car, wash)
    busy = rules._busy_intervals(day)
    from flask import current_app
    from datetime import time

    step = current_app.config["SLOT_MINUTES"]
    start = rules._minutes(rules.open_time())
    last = rules._minutes(rules.close_time()) - duration
    while start <= last:
        if rules._fits(start, start + duration, busy, current_app.config["WASH_BAYS"]):
            yield time(start // 60, start % 60)
        start += step
