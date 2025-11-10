# Minimal fallback Dockerfile to isolate build failures
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 PORT=8080
WORKDIR /app

# Create non-root user for runtime
RUN useradd -m appuser

COPY requirements.txt ./
RUN python -m pip install --upgrade pip && pip install -r requirements.txt

COPY . .

# Ensure app files are owned by non-root user
RUN chown -R appuser:appuser /app

# Drop privileges
USER appuser

# Run with Gunicorn on the Fly-assigned port, binding to all interfaces
# Use a shell to expand $PORT into the bind address
CMD ["gunicorn", "core.wsgi:app", "-b", "0.0.0.0:8080", "-w", "3"]
