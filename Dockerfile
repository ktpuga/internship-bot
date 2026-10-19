FROM python:3.13-slim

# No .pyc clutter, unbuffered logs so `docker logs` shows output immediately.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DB_PATH=/data/seen.db

WORKDIR /app

# Install deps first so this layer is cached when only code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot/ bot/

# Run as an unprivileged user; /data holds the SQLite DB (mount a volume here).
RUN useradd --system --uid 10001 bot && mkdir -p /data && chown bot /data
USER bot
VOLUME ["/data"]

# Healthy = a poll cycle finished recently. 3x the default 15-min interval + slack.
HEALTHCHECK --interval=5m --timeout=10s --start-period=2m \
  CMD python -c "import time,sys;t=int(open('/data/heartbeat').read());sys.exit(0 if time.time()-t<3000 else 1)"

CMD ["python", "-m", "bot.main"]
