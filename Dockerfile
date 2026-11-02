# Car wash booking system — production image (gunicorn + SQLite on a volume)
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    FLASK_APP=run.py \
    DATABASE_URL=sqlite:////data/car_wash.db \
    ALLOW_FIRST_ADMIN_SIGNUP=0 \
    PORT=8000

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt gunicorn==23.0.0

COPY . .

# Run as an unprivileged user; /data holds the database and the generated secret key.
RUN useradd --system --uid 10001 --home-dir /app carwash \
    && mkdir -p /data \
    && chown -R carwash:carwash /data \
    && chmod +x docker-entrypoint.sh
USER carwash

VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\", \"8000\")}/healthz', timeout=4)" || exit 1

ENTRYPOINT ["./docker-entrypoint.sh"]
# One process with threads: SQLite has a single writer, and the booking lock
# that stops two people taking the same slot lives inside the process.
CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT} --workers 1 --threads 8 --access-logfile - --error-logfile - run:app"]
