# Render.com Deployment Guide - Arrow Limousine

## Quick Start (5 minutes)

### Step 1: Push to GitHub
```bash
cd l:\limo
git add .
git commit -m "Render deployment - clean root directory, configured for Neon"
git push origin main
```

### Step 2: Create Render Web Service
1. Go to [render.com/dashboard](https://render.com/dashboard)
2. Click "New +" → "Web Service"
3. Connect your GitHub repository
4. Select: `arrow-limousine` repo

### Step 3: Configure Render Service
**Basic Settings:**
- Name: `arrow-limousine-api` (or similar)
- Environment: `Python`
- Region: `US East` (same as Neon for lower latency)
- Branch: `main`
- Build command: See below
- Start command: See below

**Build Command:**
```bash
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
cd frontend && npm install && npm run build && cd ..
```

**Start Command:**
```bash
uvicorn modern_backend.app.main:app --host 0.0.0.0 --port $PORT --workers 4
```

### Step 4: Set Environment Variables
In Render Dashboard → Environment:

```
DB_HOST=ep-curly-dream-afnuyxfx-pooler.c-2.us-west-2.aws.neon.tech
DB_NAME=neondb
DB_USER=neondb_owner
DB_PASSWORD=npg_89MbcFmZwUWo
DB_SSLMODE=require
DB_PORT=5432

API_HOST=0.0.0.0
API_PORT=$PORT
ENVIRONMENT=production

SESSION_TIMEOUT_MINUTES=30
MAX_LOGIN_ATTEMPTS=5
LOGIN_LOCKOUT_MINUTES=15

SQUARE_ACCESS_TOKEN=EAAAl0IkBWKAvgZiwfzKfbUxwxaWIbmKgYV0pTmL-5wNdxDZSd6XqnR_9Kq8il22
SQUARE_ENV=production
```

### Step 5: Deploy
Click "Create Web Service" → Render will auto-deploy on push

## Database Connection

**Neon (Cloud - PRIMARY):**
```
postgresql://neondb_owner:npg_89MbcFmZwUWo@ep-curly-dream-afnuyxfx-pooler.c-2.us-west-2.aws.neon.tech:5432/neondb?sslmode=require
```

**Local (Development only):**
```
postgresql://postgres:***REDACTED***@localhost:5432/almsdata
```

## Architecture

```
                    ┌─────────────────┐
                    │   Render Web    │
                    │  arrow-limousine│
                    │      API        │
                    └────────┬────────┘
                             │
                    (SSL/TLS encrypted)
                             │
                    ┌────────▼─────────┐
                    │  Neon PostgreSQL │
                    │  Cloud Database  │
                    │  (6,667 clients) │
                    └──────────────────┘

Local Desktop App (Development)
├── Connects to Neon (via .env DB_HOST)
├── NO local sync processes
└── Data flows through REST API
```

## What's Deployed

**Uploaded to Render:**
- ✅ `modern_backend/` - FastAPI REST API
- ✅ `frontend/` - React/Vue SPA (built to /dist)
- ✅ `desktop_app/` - PyQt6 desktop (optional)
- ✅ `scripts/` - Batch processing
- ✅ `.env` - Database config (Neon)
- ✅ `docs/` - Documentation
- ✅ `requirements.txt` - Python dependencies

**NOT Uploaded:**
- ❌ `.venv` - Virtual environment (Render creates its own)
- ❌ `__pycache__`, `.ruff_cache`
- ❌ Database dumps, backups, logs
- ❌ Analysis scripts (test_*.py, check_*.py, etc.)
- ❌ Markdown reports
- ❌ Photos, PDFs, archives

## Monitoring

**Check deployment status:**
1. Render Dashboard → Service
2. Watch "Deploy" tab (should complete in ~2-3 minutes)
3. Once live, you'll get a URL: `https://arrow-limousine-api.onrender.com`

**Access API:**
- API docs: `https://arrow-limousine-api.onrender.com/docs` (Swagger UI)
- Health check: `https://arrow-limousine-api.onrender.com/health`

**Logs:**
- Render Dashboard → Logs (real-time)
- Check for any Neon connection errors

## Verify Connection

```bash
# Test from local machine
curl https://arrow-limousine-api.onrender.com/health

# Test database access
curl https://arrow-limousine-api.onrender.com/api/charters?limit=1
```

Expected response:
```json
{
  "status": "healthy",
  "database": "connected",
  "clients": 6667
}
```

## Troubleshooting

### Build fails: "ModuleNotFoundError: No module named 'modern_backend'"
- Ensure `.env` has correct DB_HOST pointing to Neon
- Check `modern_backend/__init__.py` exists
- Verify `requirements.txt` lists all dependencies

### Database connection timeout
- Verify Neon credentials in environment variables
- Check: `sslmode=require` is set
- Confirm Neon has adequate connections available

### CORS errors on frontend calls
- FastAPI CORS middleware is configured in `modern_backend/app/main.py`
- Ensures frontend can call backend API from different domain

### Port conflicts
- Render automatically assigns `$PORT` via environment
- Start command uses `--port $PORT` (not hardcoded)

## Next Steps

1. ✅ Push to GitHub
2. ✅ Create Render service
3. ✅ Set environment variables
4. ✅ Deploy and monitor
5. ⏳ Update client apps to point to: `https://arrow-limousine-api.onrender.com`
6. ⏳ Disable local PostgreSQL sync (not needed)

## Important Notes

- **Data is in Neon, not on Render** - Render is stateless
- **No local PostgreSQL needed** - Desktop app connects to Neon via REST API
- **SSL required** - All connections use `sslmode=require`
- **Auto-deployments** - Every `git push origin main` triggers redeploy
- **Idle instances** - Free tier may spin down after 15 minutes; Render keeps instances warm via ping

---
**Last Updated:** January 30, 2026
**Status:** ✅ Ready for deployment
