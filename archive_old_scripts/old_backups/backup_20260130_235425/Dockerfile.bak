# syntax=docker/dockerfile:1.7

FROM python:3.11-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY modern_backend/pyproject.toml /app/pyproject.toml
RUN pip install --upgrade pip && pip install "fastapi[standard]" "psycopg2-binary" \
    && pip install -e .[dev] || true

# App code
COPY modern_backend/app /app/modern_backend/app

# Uvicorn entrypoint
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s CMD curl -fsS http://localhost:8000/health || exit 1
CMD ["uvicorn", "modern_backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
