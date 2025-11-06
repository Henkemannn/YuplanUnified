# syntax=docker/dockerfile:1
# Staging container for Yuplan Unified

FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080

# System deps (psycopg binary doesn't need libpq, keep minimal)
RUN adduser --disabled-password --gecos "" appuser \
    && apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (better layer caching)
COPY requirements.txt ./
RUN python -m pip install --upgrade pip \
    && pip install -r requirements.txt

# Copy application code
COPY . .

# Drop root privileges
USER appuser

EXPOSE 8080

# Gunicorn config is picked up automatically from gunicorn.conf.py in CWD
CMD ["gunicorn", "core.app_factory:create_app()", "-b", "0.0.0.0:${PORT}", "-w", "3"]
