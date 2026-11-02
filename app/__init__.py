import os

from dotenv import load_dotenv
from flask import Flask
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

load_dotenv()

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()
migrate = Migrate()


def create_app(config_object="config.Config"):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_object)

    os.makedirs(app.instance_path, exist_ok=True)
    if not app.config.get("SQLALCHEMY_DATABASE_URI"):
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(
            app.instance_path, "car_wash.db"
        )

    db.init_app(app)
    csrf.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = "admin.login"
    login_manager.login_message = "Log in to see the bookings."
    login_manager.login_message_category = "info"

    from . import booking_rules
    from .views.admin import admin
    from .views.main import main

    app.register_blueprint(main)
    app.register_blueprint(admin, url_prefix="/admin")

    @app.context_processor
    def inject_globals():
        return {
            "shop_name": app.config["SHOP_NAME"],
            "shop_phone": app.config["SHOP_PHONE"],
            "rules": booking_rules,
        }

    app.jinja_env.filters["nice_date"] = booking_rules.nice_date
    app.jinja_env.filters["nice_time"] = booking_rules.nice_time

    _register_error_pages(app)

    from .cli import register_cli

    register_cli(app)
    return app


ERRORS = {
    400: ("That request didn't make sense", "Go back and try again."),
    403: ("You can't open this page", "Log in with a staff account, or go back to the booking page."),
    404: ("Page not found", "The link may be old or mistyped."),
    500: ("Something went wrong", "Try again in a moment. If it keeps happening, call the shop."),
}


def _register_error_pages(app):
    from flask import flash, jsonify, redirect, render_template, request
    from flask_wtf.csrf import CSRFError

    def render(code):
        heading, message = ERRORS[code]
        if request.accept_mimetypes.best == "application/json" or request.is_json:
            return jsonify({"success": False, "message": heading}), code
        return render_template("error.html", code=code, heading=heading, message=message), code

    for code in ERRORS:
        app.register_error_handler(code, lambda e, code=code: render(code))

    @app.errorhandler(CSRFError)
    def csrf_error(e):
        if request.is_json or request.headers.get("HX-Request"):
            return jsonify({"success": False, "message": "This page expired. Reload it and try again."}), 400
        flash("This page expired, so nothing was saved. Please try again.", "warning")
        return redirect(request.full_path if request.method == "GET" else request.path)
