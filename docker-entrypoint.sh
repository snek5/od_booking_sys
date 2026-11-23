#!/bin/sh
# Prepares the database and first staff account, then starts the server.
set -e

DATA_DIR="${DATA_DIR:-/data}"

# Started as root: make the data folder ours, then run this script again as `carwash`.
if [ "$(id -u)" = "0" ]; then
    mkdir -p "$DATA_DIR"
    chown -R carwash:carwash "$DATA_DIR"
    exec python -c '
import os, pwd, sys
u = pwd.getpwnam("carwash")
os.setgroups([]); os.setgid(u.pw_gid); os.setuid(u.pw_uid)
os.environ["HOME"] = u.pw_dir
os.execvp(sys.argv[1], sys.argv[1:])
' "$0" "$@"
fi

mkdir -p "$DATA_DIR"
if [ ! -w "$DATA_DIR" ]; then
    echo "Can't write to $DATA_DIR. Mount a writable volume there, or start the container as root so it can fix the permissions." >&2
    exit 1
fi

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
