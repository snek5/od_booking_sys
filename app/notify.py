"""Booking confirmations by text (Twilio) and email (Resend).

API keys come from the environment (see config.py). Staff switch each channel on
or off on the Settings page; the switch is stored in the `setting` table. A
channel only sends when it has its keys *and* is switched on.

Sending never blocks a booking: failures are logged and reported back as False.
Both services are called over plain HTTPS, so no extra packages are needed.
"""
import base64
import json
import urllib.error
import urllib.parse
import urllib.request

from flask import current_app, render_template

from . import booking_rules as rules
from .models import Setting

TIMEOUT = 10  # seconds per request

CHANNELS = {
    "sms": {
        "label": "Text message",
        "provider": "Twilio",
        # config key -> environment variable to set
        "keys": {
            "TWILIO_ACCOUNT_SID": "TWILIO_ACCOUNT_SID",
            "TWILIO_AUTH_TOKEN": "TWILIO_AUTH_TOKEN",
            "TWILIO_MESSAGING_SERVICE": "MESSAGING_SERVICE",
        },
    },
    "email": {
        "label": "Email",
        "provider": "Resend",
        "keys": {
            "RESEND_API_KEY": "RESEND_API_KEY",
            "RESEND_FROM": "RESEND_FROM",
        },
    },
}


class SendError(Exception):
    """The provider refused or couldn't be reached. The message is safe to show staff."""


# ---------- switches ----------

def missing_keys(channel):
    cfg = current_app.config
    return [env for key, env in CHANNELS[channel]["keys"].items() if not cfg.get(key)]


def is_switched_on(channel):
    """The staff switch. Until someone changes it, a channel with keys starts on."""
    value = Setting.get(f"notify_{channel}")
    if value is None:
        return not missing_keys(channel)
    return value == "1"


def set_switch(channel, on):
    Setting.put(f"notify_{channel}", "1" if on else "0")


def is_active(channel):
    return is_switched_on(channel) and not missing_keys(channel)


def channel_status():
    """Everything the Settings page needs, per channel."""
    out = {}
    for name, meta in CHANNELS.items():
        missing = missing_keys(name)
        out[name] = {
            **meta,
            "name": name,
            "missing": missing,
            "ready": not missing,
            "on": is_switched_on(name),
            "active": not missing and is_switched_on(name),
        }
    return out


# ---------- HTTP ----------

def _post(url, *, headers, data, what):
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
            return json.loads(res.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            detail = json.loads(e.read() or b"{}").get("message", "")
        except ValueError:
            detail = ""
        raise SendError(f"{what} refused the message ({e.code}){': ' + detail if detail else ''}.") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise SendError(f"Couldn't reach {what}. Check the server's internet connection.") from e


# ---------- providers ----------

def send_sms(to_local_number, body):
    """Send one text through Twilio. `to_local_number` is the 7-digit number."""
    cfg = current_app.config
    sid = cfg["TWILIO_ACCOUNT_SID"]
    auth = base64.b64encode(f"{sid}:{cfg['TWILIO_AUTH_TOKEN']}".encode()).decode()
    return _post(
        f"https://api.twilio.com/2010-04-01/Accounts/{urllib.parse.quote(sid)}/Messages.json",
        headers={
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data=urllib.parse.urlencode({
            "To": f"{cfg['SMS_COUNTRY_CODE']}{to_local_number}",
            "MessagingServiceSid": cfg["TWILIO_MESSAGING_SERVICE"],
            "Body": body,
        }).encode(),
        what="Twilio",
    )


def send_email(to, subject, html, text, idempotency_key=None):
    """Send one email through Resend."""
    cfg = current_app.config
    payload = {"from": cfg["RESEND_FROM"], "to": [to], "subject": subject, "html": html, "text": text}
    if cfg.get("RESEND_REPLY_TO"):
        payload["reply_to"] = cfg["RESEND_REPLY_TO"]
    headers = {
        "Authorization": f"Bearer {cfg['RESEND_API_KEY']}",
        "Content-Type": "application/json",
        "User-Agent": "carwash-booking/1.0",
    }
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    return _post("https://api.resend.com/emails", headers=headers,
                 data=json.dumps(payload).encode(), what="Resend")


# ---------- booking confirmation ----------

def sms_text(booking):
    shop = current_app.config["SHOP_NAME"]
    return (
        f"{shop}: your wash is booked.\n"
        f"{booking.car_plate} ({booking.car_type}) - {booking.wash_type}\n"
        f"{rules.fixed_date(booking.date)}, {rules.nice_time(booking.time)}\n"
        f"Please arrive 5 minutes early."
    )


def confirmation_email(booking):
    ctx = {"booking": booking, "rules": rules, "shop_name": current_app.config["SHOP_NAME"],
           "shop_phone": current_app.config["SHOP_PHONE"]}
    subject = f"Booked: {booking.wash_type} wash, {rules.fixed_date(booking.date)} at {rules.nice_time(booking.time)}"
    return subject, render_template("emails/confirmation.html", **ctx), render_template("emails/confirmation.txt", **ctx)


def send_confirmation(booking):
    """Send the confirmation on every active channel. Returns {"sms": bool, "email": bool}."""
    sent = {"sms": False, "email": False}
    if is_active("sms"):
        try:
            send_sms(booking.contact_number, sms_text(booking))
            sent["sms"] = True
        except SendError:
            current_app.logger.exception("Booking %s: text message not sent", booking.id)
    if booking.email and is_active("email"):
        try:
            subject, html, text = confirmation_email(booking)
            send_email(booking.email, subject, html, text, idempotency_key=f"booking-{booking.id}-confirmation")
            sent["email"] = True
        except SendError:
            current_app.logger.exception("Booking %s: email not sent", booking.id)
    return sent
