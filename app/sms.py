"""Optional SMS confirmations through Twilio.

SMS is skipped (never an error) when Twilio isn't installed or configured, so a
booking always goes through even if the message can't be sent.
"""
from flask import current_app

from . import booking_rules as rules


def sms_enabled():
    cfg = current_app.config
    return all(cfg.get(k) for k in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_MESSAGING_SERVICE"))


def send_confirmation(booking):
    """Send the booking confirmation. Returns True if the SMS was handed to Twilio."""
    if not sms_enabled():
        return False
    cfg = current_app.config
    body = (
        f"{cfg['SHOP_NAME']}: your wash is booked.\n"
        f"{booking.car_plate} ({booking.car_type}) — {booking.wash_type}\n"
        f"{rules.nice_date(booking.date)}, {rules.nice_time(booking.time)}\n"
        f"Please arrive 5 minutes early."
    )
    try:
        from twilio.rest import Client

        client = Client(cfg["TWILIO_ACCOUNT_SID"], cfg["TWILIO_AUTH_TOKEN"])
        client.messages.create(
            body=body,
            messaging_service_sid=cfg["TWILIO_MESSAGING_SERVICE"],
            to=f"{cfg['SMS_COUNTRY_CODE']}{booking.contact_number}",
        )
        return True
    except Exception:  # noqa: BLE001 — never block a booking on SMS
        current_app.logger.exception("Could not send booking SMS for booking %s", booking.id)
        return False
