# 🧼 Car Wash Booking System

A booking site for a car wash: customers pick a wash and a free time slot on their phone, and staff run the day from a calendar and a booking list.

---

## 🚀 Features

**For customers** (`/`)
- Four-step booking: plate number, car type, wash, then a day and time
- Only free times are offered — the slot picker knows how long each wash takes for each car type and never double-books
- Live summary of the booking while filling in the form, and a confirmation "ticket" afterwards
- Optional SMS confirmation through Twilio

**For staff** (`/admin`)
- **Calendar** (FullCalendar): month, week and day views, coloured by status; click a booking to see details and mark it *Arrived*, *No show* or *Cancelled*; click an empty slot to add a booking there
- **Booking list**: today's numbers at a glance, search by plate/name/phone, filter by date or status, pagination, one-click *Arrived* / *No show* (htmx)
- Add, edit and delete bookings (walk-ins and phone bookings)
- Staff accounts: the first account is created on first run; after that, only logged-in staff can add accounts

Statuses: **Pending** → **Attended**, **No Show** or **Cancelled**. Cancelled and no-show bookings free up their slot.

---

## 🧰 Tech Stack

- **Backend**: Flask, Flask-Login, Flask-WTF (CSRF on every form), SQLAlchemy, Flask-Migrate
- **Frontend**: Bootstrap 5, htmx, FullCalendar 6 — all served locally, no CDNs; Barlow font self-hosted
- **Database**: SQLite by default, any SQLAlchemy URL via `DATABASE_URL`

---

## 📁 Project Structure
```
.
├── app
│   ├── __init__.py          # app factory, error pages
│   ├── booking_rules.py     # car types, washes, durations, statuses, slot availability
│   ├── cli.py               # flask create-admin / flask seed
│   ├── forms.py
│   ├── models.py
│   ├── sms.py               # optional Twilio confirmation
│   ├── views
│   │   ├── main.py          # customer booking, /slots partial, confirmation
│   │   └── admin.py         # staff pages and calendar API
│   ├── templates
│   │   ├── _base.html       # shared <head>, scripts
│   │   ├── public_base.html # customer layout
│   │   ├── admin_base.html  # staff layout with sidebar
│   │   └── partials/        # UI macros, slot grid, booking row
│   └── static
│       ├── styles.css       # the design system (colours, type, components)
│       ├── booking.js       # customer form behaviour
│       ├── script.js        # staff calendar
│       └── fonts/ img/ bootstrap.* htmx.min.js index.global.min.js
├── migrations/
├── tests/
├── config.py                # all settings, read from environment / .env
├── requirements.txt
└── run.py
```

---

## 🛠️ Getting Started

```bash
git clone https://github.com/snek5/ss_bookingsys_carwash.git
cd ss_bookingsys_carwash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # then edit SECRET_KEY, SHOP_NAME, …
```

Create or update the database (safe to run on an existing database — it migrates old data too):
```bash
flask --app run.py db upgrade
```

Optional demo data, and a staff account from the command line:
```bash
flask --app run.py seed
flask --app run.py create-admin desk
```

Run it:
```bash
flask --app run.py run --debug
```

Open http://127.0.0.1:5000 for the customer page and http://127.0.0.1:5000/admin for staff. If there are no staff accounts yet, `/admin` takes you to set up the first one.

Run the tests:
```bash
pip install pytest
pytest
```

---

## ⚙️ Settings

Set these in `.env` (see `.env.example`) or the environment.

| Setting | Default | What it does |
| --- | --- | --- |
| `SECRET_KEY` | dev value | **Change in production.** Signs sessions and confirmation links. |
| `DATABASE_URL` | `instance/car_wash.db` | Any SQLAlchemy database URL. |
| `SHOP_NAME` | Nama Car Wash | Shown in the header, page titles and SMS. |
| `SHOP_PHONE` | — | Shown to customers who need to change a booking. |
| `TIMEZONE` | Asia/Brunei | Used for "today" and to hide times that have passed. |
| `OPEN_TIME` / `CLOSE_TIME` | 09:00 / 18:00 | Every wash must start and finish inside these. |
| `SLOT_MINUTES` | 15 | How often a booking can start. |
| `WASH_BAYS` | 1 | How many cars can be washed at the same time. |
| `BOOKING_WINDOW_DAYS` | 30 | How far ahead customers can book. |
| `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `MESSAGING_SERVICE` | — | Turn on SMS confirmations. Leave empty to skip SMS. |
| `SMS_COUNTRY_CODE` | +673 | Prefixed to the 7-digit phone number. |

Wash durations, car types and wash descriptions live in `app/booking_rules.py`.

## 👤 Author

OuroDev
