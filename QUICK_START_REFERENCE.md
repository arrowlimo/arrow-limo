# 🚀 QUICK START REFERENCE CARD

## Installation & Running (3 Steps)

### Step 1: One-Click Start
```powershell
cd l:\limo
.\start-application.bat
```
✓ Installs dependencies  
✓ Starts backend (FastAPI)  
✓ Starts frontend (Vue)  
✓ Opens in browser  

**Then**: http://localhost:8080

### Step 2: Manual Start (if above doesn't work)
```powershell
# Terminal 1 - Backend
uvicorn modern_backend.app.main:app --reload

# Terminal 2 - Frontend  
cd frontend
npm run serve
```

### Step 3: Verify It Works
- Frontend: http://localhost:8080
- API Docs: http://localhost:8000/docs
- Both should load

---

## Database Options

### Local (Default - No Setup Required)
```
Host: localhost
Port: 5432
Database: almsdata
User: postgres
Password: ***REMOVED***
```

### Cloud with Neon (Recommended for Remote Access)
1. Create account at https://neon.tech
2. Follow: `NEON_DATABASE_SETUP_GUIDE.md`
3. Update `.env` file with Neon credentials
4. Run application normally

---

## Project Structure at a Glance

```
l:\limo/
├── modern_backend/     ← FastAPI (Backend API)
├── frontend/           ← Vue 3 (Frontend UI)
├── scripts/            ← Utility scripts (300+)
├── docs/               ← Documentation
├── .env                ← Database connection config
└── README.md           ← This project
```

---

## Common Commands

### Install Dependencies
```powershell
# Backend
pip install -e modern_backend[dev]

# Frontend
cd frontend && npm install
```

### Run Backend
```powershell
uvicorn modern_backend.app.main:app --reload
```

### Run Frontend
```powershell
cd frontend && npm run serve
```

### Build Frontend for Production
```powershell
cd frontend && npm run build
```

### Run Tests
```powershell
# Backend
pytest modern_backend/tests/

# Frontend
cd frontend && npm test
```

### Database Backup
```powershell
pg_dump -U postgres -d almsdata > backup.sql
```

### Database Restore
```powershell
psql -U postgres -d almsdata < backup.sql
```

---

## API Endpoints (Swagger at `/docs`)

```
GET/POST   /api/charters           - Bookings
GET/POST   /api/payments           - Payments
GET/POST   /api/receipts           - Expenses
GET        /api/banking/trans*     - Bank transactions
GET        /api/reports/*          - Financial reports
```

Full docs: http://localhost:8000/docs

---

## Database Connection in Code

### Python
```python
import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REMOVED***"
)
```

### From .env
```python
import os
from dotenv import load_dotenv

load_dotenv()
host = os.getenv('DB_HOST')
db = os.getenv('DB_NAME')
# etc...
```

---

## File Locations

| File | Purpose |
|------|---------|
| `start-application.bat` | One-click start (Windows) |
| `start-application.ps1` | One-click start (PowerShell) |
| `.env` | Database credentials |
| `modern_backend/app/main.py` | Backend entry point |
| `frontend/src/main.js` | Frontend entry point |
| `APPLICATION_COMPLETE_SETUP_GUIDE.md` | Full setup guide |
| `NEON_DATABASE_SETUP_GUIDE.md` | Cloud database setup |
| `COMPLETE_STATUS_REPORT.md` | Project status |

---

## Troubleshooting

### Port Already in Use
```powershell
# Find process using port 8000
netstat -ano | findstr :8000

# Kill it
taskkill /PID <pid> /F

# Or use different port
uvicorn modern_backend.app.main:app --port 8001
```

### Database Connection Error
```
ERROR: could not connect to server: Connection refused
```

**Fix**:
- Check PostgreSQL is running: `pg_isready`
- Verify .env settings
- Check almsdata database exists: `psql -l`

### Frontend Won't Load
```
Cannot find module '@'
```

**Fix**:
- Run: `cd frontend && npm install`
- Clear cache: `npm cache clean --force`
- Delete `node_modules` and reinstall

### Port 8080 Already in Use
```powershell
# Use different port
cd frontend
npm run serve -- --port 8081
```

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | FastAPI, Python 3.11+, Uvicorn |
| **Frontend** | Vue 3, JavaScript/Node.js, Webpack |
| **Database** | PostgreSQL 12+ (Local or Neon Cloud) |
| **Deployment** | Docker, Docker Compose |
| **Testing** | Pytest, Jest |
| **Linting** | Ruff, MyPy |

---

## Key Resources

| Resource | Link |
|----------|------|
| Full Setup Guide | `APPLICATION_COMPLETE_SETUP_GUIDE.md` |
| Cloud Database | `NEON_DATABASE_SETUP_GUIDE.md` |
| Status Report | `COMPLETE_STATUS_REPORT.md` |
| API Docs | http://localhost:8000/docs |
| FastAPI Docs | https://fastapi.tiangolo.com/ |
| Vue Docs | https://vuejs.org/ |

---

## One-Minute Troubleshooting

```powershell
# ✓ Check everything is working
# 1. Database running?
pg_isready

# 2. Can Python connect?
python -c "import psycopg2; psycopg2.connect(host='localhost')"

# 3. Node installed?
node --version && npm --version

# 4. Python dependencies?
pip list | grep fastapi

# 5. Kill old processes
Get-Process | Where-Object {$_.ProcessName -like "*python*" -or $_.ProcessName -like "*node*"} | Stop-Process -Force

# 6. Then start fresh
.\start-application.bat
```

---

## Support

### Documentation
- See `APPLICATION_COMPLETE_SETUP_GUIDE.md` for complete setup
- See `NEON_DATABASE_SETUP_GUIDE.md` for cloud database

### Code Examples
- Backend: `modern_backend/app/routers/*.py`
- Frontend: `frontend/src/components/`
- Scripts: `scripts/` (300+ examples)

### Environment
- Database: PostgreSQL on localhost:5432
- Backend API: http://127.0.0.1:8000
- Frontend: http://localhost:8080
- API Docs: http://localhost:8000/docs

---

**Status**: ✅ PRODUCTION READY  
**Last Updated**: December 23, 2025  
**Version**: 1.0.0
