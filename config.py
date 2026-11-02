import os


def _int(name, default):
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


class Config:
    # Security — always set SECRET_KEY in production (.env or environment).
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me")

    # Database. Defaults to SQLite in the Flask instance folder (instance/car_wash.db).
    # Set DATABASE_URL to use Postgres/MySQL instead.
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")  # filled in by create_app if unset
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Shop details shown across the site.
    SHOP_NAME = os.getenv("SHOP_NAME", "Nama Car Wash")
    SHOP_PHONE = os.getenv("SHOP_PHONE", "")
    TIMEZONE = os.getenv("TIMEZONE", "Asia/Brunei")

    # Opening hours and scheduling.
    OPEN_TIME = os.getenv("OPEN_TIME", "09:00")
    CLOSE_TIME = os.getenv("CLOSE_TIME", "18:00")
    SLOT_MINUTES = _int("SLOT_MINUTES", 15)       # how often a booking can start
    WASH_BAYS = _int("WASH_BAYS", 1)              # cars that can be washed at the same time
    BOOKING_WINDOW_DAYS = _int("BOOKING_WINDOW_DAYS", 30)  # how far ahead customers can book

    # SMS confirmations (optional). If any of these is missing, SMS is skipped.
    TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
    TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
    TWILIO_MESSAGING_SERVICE = os.getenv("MESSAGING_SERVICE")
    SMS_COUNTRY_CODE = os.getenv("SMS_COUNTRY_CODE", "+673")

    ADMIN_PAGE_SIZE = 15

    # When there are no staff accounts yet, let the first visitor to /admin create one.
    # Fine on your own machine; turn it off on a public server (the container does)
    # and create the first account with ADMIN_USERNAME/ADMIN_PASSWORD or `flask create-admin`.
    ALLOW_FIRST_ADMIN_SIGNUP = os.getenv("ALLOW_FIRST_ADMIN_SIGNUP", "1").lower() in ("1", "true", "yes")


class TestConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite://"
