import io
import json
import urllib.error
import pytest

from app import notify
from app.models import Booking, Setting

from conftest import book, tomorrow


class FakeHTTP:
    """Stands in for urllib.request.urlopen and records each request."""

    def __init__(self, fail=None):
        self.calls = []
        self.fail = fail

    def __call__(self, req, timeout=None):
        self.calls.append(req)
        if self.fail:
            raise self.fail
        return io.BytesIO(b'{"id": "msg_1"}')

    def bodies(self, host):
        return [r for r in self.calls if host in r.full_url]


@pytest.fixture
def http(monkeypatch):
    fake = FakeHTTP()
    monkeypatch.setattr(notify.urllib.request, "urlopen", fake)
    return fake


@pytest.fixture
def keys(app):
    app.config.update(
        TWILIO_ACCOUNT_SID="AC123", TWILIO_AUTH_TOKEN="tok", TWILIO_MESSAGING_SERVICE="MG1",
        RESEND_API_KEY="re_123", RESEND_FROM="Shop <b@shop.test>",
    )


def test_channels_without_keys_are_off_and_send_nothing(client, http):
    res = book(client, email="siti@example.com")
    assert res.status_code == 302
    assert http.calls == []
    # Email field isn't shown, and an email posted anyway isn't stored.
    assert b'name="email"' not in client.get("/").data
    assert Booking.query.one().email is None


def test_both_channels_send_when_keys_present(client, http, keys):
    assert b'name="email"' in client.get("/").data
    res = book(client, email=" Siti@Example.com ")
    assert "sms=1" in res.location and "email=1" in res.location

    sms = http.bodies("api.twilio.com")[0]
    assert "/Accounts/AC123/Messages.json" in sms.full_url
    assert b"To=%2B6737123456" in sms.data and b"MessagingServiceSid=MG1" in sms.data

    mail = http.bodies("api.resend.com")[0]
    payload = json.loads(mail.data)
    assert payload["to"] == ["siti@example.com"] and payload["from"] == "Shop <b@shop.test>"
    assert "BAA 1234" in payload["html"] and "BAA 1234" in payload["text"]
    assert mail.get_header("Authorization") == "Bearer re_123"
    assert mail.get_header("Idempotency-key").startswith("booking-")

    page = client.get(res.location).data
    assert b"texted these details" in page and b"emailed them to siti@example.com" in page


def test_email_is_optional(client, http, keys):
    res = book(client)
    assert "email=0" in res.location
    assert http.bodies("api.resend.com") == [] and len(http.bodies("api.twilio.com")) == 1


def test_bad_email_is_rejected(client, http, keys):
    res = book(client, email="not-an-email")
    assert res.status_code == 422 and b"name@example.com" in res.data
    assert Booking.query.count() == 0


def test_switching_sms_off_stops_texts(staff, http, keys):
    res = staff.post("/admin/settings/sms", data={"on": "0"})
    assert res.status_code == 302
    assert Setting.get("notify_sms") == "0"
    staff.post("/admin/logout")
    book(staff, email="a@b.co")
    assert http.bodies("api.twilio.com") == []
    assert len(http.bodies("api.resend.com")) == 1


def test_switching_email_off_hides_field(staff, http, keys):
    staff.post("/admin/settings/email", data={"on": "0"})
    assert b'name="email"' not in staff.get("/").data
    staff.post("/admin/settings/email", data={"on": "1"})
    assert b'name="email"' in staff.get("/").data


def test_cant_switch_on_without_keys(staff):
    res = staff.post("/admin/settings/email", data={"on": "1"}, follow_redirects=True)
    assert b"set RESEND_API_KEY, RESEND_FROM on the server first" in res.data
    assert Setting.get("notify_email") is None


def test_settings_page_shows_state(staff, keys):
    staff.post("/admin/settings/sms", data={"on": "0"})
    page = staff.get("/admin/settings").data.decode()
    assert page.count('role="switch"') == 2
    assert 'aria-checked="false"' in page and 'aria-checked="true"' in page


def test_settings_page_lists_missing_keys(staff):
    page = staff.get("/admin/settings").data
    assert b"<code>TWILIO_ACCOUNT_SID</code>" in page and b"<code>RESEND_API_KEY</code>" in page


def test_settings_need_login(client):
    for path in ("/admin/settings",):
        assert client.get(path).status_code == 302
    for path in ("/admin/settings/sms", "/admin/settings/test/sms", "/admin/settings/test/email"):
        assert client.post(path, data={"on": "0", "number": "7123456"}).status_code == 302
    assert Setting.query.count() == 0


def test_send_test_email_reports_provider_error(staff, monkeypatch, keys):
    err = urllib.error.HTTPError("https://api.resend.com/emails", 403, "Forbidden", {},
                                 io.BytesIO(b'{"message": "The shop.test domain is not verified."}'))
    monkeypatch.setattr(notify.urllib.request, "urlopen", FakeHTTP(fail=err))
    res = staff.post("/admin/settings/test/email", data={"address": "me@x.co"}, follow_redirects=True)
    assert b"Test email not sent. Resend refused the message (403): The shop.test domain is not verified." in res.data


def test_send_test_sms(staff, http, keys):
    res = staff.post("/admin/settings/test/sms", data={"number": "712 3456"}, follow_redirects=True)
    assert b"Test text sent to +673 7123456" in res.data
    assert len(http.bodies("api.twilio.com")) == 1


def test_provider_down_never_blocks_booking(client, monkeypatch, keys):
    monkeypatch.setattr(notify.urllib.request, "urlopen", FakeHTTP(fail=urllib.error.URLError("down")))
    res = book(client, email="a@b.co")
    assert res.status_code == 302 and "sms=0" in res.location and "email=0" in res.location
    assert Booking.query.count() == 1


def test_staff_can_add_email_and_search_it(staff):
    res = staff.post("/admin/booking/add", data=dict(
        car_plate="BB 2", car_type="Sedan", wash_type="Exterior", date=tomorrow().isoformat(),
        time="15:00", name="Walk In", contact_number="7000000", email="walk@in.co", status="Pending"))
    assert res.status_code == 302
    assert Booking.query.one().email == "walk@in.co"
    assert b"walk@in.co" in staff.get("/admin/dashboard?q=walk@").data
