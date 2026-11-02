import re

from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    DateField,
    PasswordField,
    RadioField,
    SelectField,
    StringField,
    TimeField,
)
from wtforms.validators import DataRequired, EqualTo, Length, Regexp, ValidationError

from . import booking_rules as rules


def _clean_plate(value):
    return re.sub(r"\s+", " ", value or "").strip().upper()


def _strip(value):
    return (value or "").strip()


class BookingForm(FlaskForm):
    """Customer booking form. The time comes from the slot picker."""

    car_plate = StringField(
        "Plate number",
        filters=[_clean_plate],
        validators=[
            DataRequired("Enter the car's plate number."),
            Length(min=2, max=15, message="Plate numbers are 2 to 15 characters."),
            Regexp(r"^[A-Z0-9 ]+$", message="Use letters and numbers only."),
        ],
    )
    car_type = RadioField(
        "Car type",
        choices=[(c, c) for c in rules.CAR_TYPES],
        default="Sedan",
        validators=[DataRequired("Choose a car type.")],
    )
    wash_type = RadioField(
        "Wash",
        choices=[(w, w) for w in rules.WASH_TYPES],
        default="Exterior",
        validators=[DataRequired("Choose a wash.")],
    )
    date = DateField("Day", validators=[DataRequired("Pick a day.")])
    time = TimeField("Time", validators=[DataRequired("Pick a time.")])
    name = StringField(
        "Your name",
        filters=[_strip],
        validators=[DataRequired("Enter your name."), Length(min=2, max=100)],
    )
    contact_number = StringField(
        "Phone number",
        filters=[lambda v: re.sub(r"[\s-]", "", v or "")],
        validators=[
            DataRequired("Enter your phone number."),
            Regexp(r"^\d{7}$", message="Enter the 7-digit number, without +673."),
        ],
    )


class AdminBookingForm(BookingForm):
    """Same fields as the customer form, plus status. Staff type the time directly."""

    car_type = SelectField("Car type", choices=[(c, c) for c in rules.CAR_TYPES])
    wash_type = SelectField("Wash", choices=[(w, w) for w in rules.WASH_TYPES])
    name = StringField(
        "Customer name",
        filters=[_strip],
        validators=[DataRequired("Enter the customer's name."), Length(min=2, max=100)],
    )
    status = SelectField(
        "Status",
        choices=[(s, s) for s in rules.STATUSES],
        default=rules.PENDING,
    )


class LoginForm(FlaskForm):
    username = StringField("Username", filters=[_strip], validators=[DataRequired("Enter your username.")])
    password = PasswordField("Password", validators=[DataRequired("Enter your password.")])
    remember = BooleanField("Keep me logged in on this device")


class RegisterForm(FlaskForm):
    username = StringField(
        "Username",
        filters=[_strip],
        validators=[
            DataRequired("Choose a username."),
            Length(min=3, max=50, message="Usernames are 3 to 50 characters."),
        ],
    )
    password = PasswordField(
        "Password",
        validators=[DataRequired("Choose a password."), Length(min=8, message="Use at least 8 characters.")],
    )
    confirm_password = PasswordField(
        "Repeat password",
        validators=[DataRequired("Repeat the password."), EqualTo("password", message="The passwords don't match.")],
    )

    def validate_username(self, field):
        from .models import Admin

        if Admin.query.filter_by(username=field.data).first():
            raise ValidationError("That username is taken.")
