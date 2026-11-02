#!/bin/sh
# Prepares the database and first staff account, then starts the server.
set -e

DATA_DIR="${DATA_DIR:-/data}"
mkdir -p "$DATA_DIR"

# Keep one secret key across restarts so logins and confirmation links stay valid.
if [ -z "$SECRET_KEY" ]; then
    if [ ! -s "$DATA_DIR/.secret_key" ]; then
        python -c "import secrets; print(secrets.token_urlsafe(48))" > "$DATA_DIR/.secret_key"
        chmod 600 "$DATA_DIR/.secret_key"
        echo "Generated a secret key in $DATA_DIR/.secret_key"
    fi
    SECRET_KEY="$(cat "$DATA_DIR/.secret_key")"
    export SECRET_KEY
fi

echo "Updating the database…"
flask db upgrade

if [ -n "$ADMIN_USERNAME" ] && [ -n "$ADMIN_PASSWORD" ]; then
    flask create-admin "$ADMIN_USERNAME" --if-missing  # password read from ADMIN_PASSWORD
fi

STAFF_COUNT="$(python -c "
from app import create_app
from app.models import Admin
with create_app().app_context():
    print(Admin.query.count())
")"
if [ "$STAFF_COUNT" = "0" ]; then
    echo "No staff accounts yet. Set ADMIN_USERNAME and ADMIN_PASSWORD, or run:"
    echo "  docker compose exec web flask create-admin <username>"
fi

exec "$@"
