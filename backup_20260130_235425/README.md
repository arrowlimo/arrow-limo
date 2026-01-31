# Modern Backend (FastAPI)

This directory provides a modernized FastAPI backend alongside your existing Flask app, enabling an incremental migration path without breaking current functionality.

## Features
- FastAPI app with CORS, correlation IDs, and global error handler
- Reports export router (booking-trends CSV sample)
- Tooling: Ruff, MyPy, Pytest, Pre-commit
- Dockerfile (multi-stage) with Uvicorn
- GitHub Actions CI pipeline (lint, type-check, tests, Docker build)

## Run locally
- Install Python 3.11+
- Option A: quick run

```bash
pip install "fastapi[standard]" "psycopg2-binary"
uvicorn modern_backend.app.main:app --reload
```

- Option B: using pyproject (dev extras configured)

```bash
pip install -e modern_backend[dev]
uvicorn modern_backend.app.main:app --reload
```

## Docker
```bash
docker build -f modern_backend/Dockerfile -t limo-modern-backend .
docker run -p 8000:8000 --env-file .env limo-modern-backend
```

## Migration plan
1. Keep Flask API serving existing SPA
2. Add/port routes to FastAPI under `modern_backend/app/routers`
3. Switch SPA to FastAPI once parity is reached

## Notes
- Environment variables are shared with the Flask app for DB access
- Sentry can be added via the `sentry-sdk` dependency if desired
