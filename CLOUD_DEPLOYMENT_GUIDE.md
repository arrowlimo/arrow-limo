# Arrow Limousine Cloud Deployment Guide
## Deploying Web App to Production

### Prerequisites
- [ ] GitHub repository (create if needed)
- [ ] Neon account (PostgreSQL database)
- [ ] Render account (backend hosting)
- [ ] Netlify account (frontend hosting)

---

## STEP 1: Prepare Backend for Production

### 1.1 Create requirements.txt
```bash
cd modern_backend
pip freeze > requirements.txt
```

### 1.2 Create Procfile for Render
Create `modern_backend/Procfile`:
```
web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

### 1.3 Create render.yaml
Create `modern_backend/render.yaml`:
```yaml
services:
  - type: web
    name: arrow-limo-api
    env: python
    region: oregon
    plan: free
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: DATABASE_URL
        sync: false
      - key: PYTHON_VERSION
        value: 3.11
```

---

## STEP 2: Setup Neon Database

### 2.1 Create Neon Project
1. Go to https://neon.tech
2. Sign up / Log in
3. Create new project: "arrow-limo-prod"
4. Copy connection string (starts with `postgresql://`)

### 2.2 Migrate Local Database to Neon
```powershell
# Dump local database
pg_dump -h localhost -U postgres -d almsdata -F c -f almsdata_prod.dump

# Restore to Neon (replace with your connection string)
pg_restore -h <neon-host> -U <neon-user> -d <neon-db> --clean --if-exists almsdata_prod.dump
```

---

## STEP 3: Deploy Backend to Render

### 3.1 Push Code to GitHub
```bash
git add modern_backend/
git commit -m "Prepare backend for production"
git push origin main
```

### 3.2 Connect Render
1. Go to https://render.com
2. Sign up / Log in
3. New → Web Service
4. Connect GitHub repository
5. Root directory: `modern_backend`
6. Build command: `pip install -r requirements.txt`
7. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

### 3.3 Set Environment Variables
In Render dashboard:
- `DATABASE_URL` = Your Neon connection string
- `DB_HOST` = Extract from Neon connection
- `DB_NAME` = almsdata
- `DB_USER` = Extract from Neon connection
- `DB_PASSWORD` = Extract from Neon connection

### 3.4 Deploy
- Click "Create Web Service"
- Wait 2-3 minutes for deployment
- Copy API URL (e.g., `https://arrow-limo-api.onrender.com`)

---

## STEP 4: Prepare Frontend for Production

### 4.1 Update API Endpoint
Edit `frontend/src/config.js` (or create if missing):
```javascript
export const API_BASE_URL = process.env.VUE_APP_API_URL || 'https://arrow-limo-api.onrender.com'
```

### 4.2 Create Build Configuration
Create `frontend/netlify.toml`:
```toml
[build]
  command = "npm run build"
  publish = "dist"

[[redirects]]
  from = "/*"
  to = "/index.html"
  status = 200
```

---

## STEP 5: Deploy Frontend to Netlify

### 5.1 Push Frontend to GitHub
```bash
git add frontend/
git commit -m "Prepare frontend for production"
git push origin main
```

### 5.2 Connect Netlify
1. Go to https://netlify.com
2. Sign up / Log in
3. New site from Git
4. Connect GitHub repository
5. Base directory: `frontend`
6. Build command: `npm run build`
7. Publish directory: `dist`

### 5.3 Set Environment Variables
In Netlify dashboard:
- `VUE_APP_API_URL` = Your Render API URL

### 5.4 Deploy
- Click "Deploy site"
- Wait 1-2 minutes
- Copy site URL (e.g., `https://arrow-limo.netlify.app`)

---

## STEP 6: Configure CORS

Update `modern_backend/app/main.py` CORS settings:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://arrow-limo.netlify.app",  # Your Netlify URL
        "http://localhost:8080",  # Local development
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Push update:
```bash
git add modern_backend/app/main.py
git commit -m "Configure CORS for production"
git push origin main
```

Render will auto-deploy in 2-3 minutes!

---

## STEP 7: Verify Deployment

### Backend Health Check
Visit: `https://arrow-limo-api.onrender.com/docs`
- Should show FastAPI Swagger UI
- Test API endpoints

### Frontend Check
Visit: `https://arrow-limo.netlify.app`
- Should load web interface
- Test login/functionality

---

## Auto-Update Workflow

Once deployed, updates are automatic:

```bash
# 1. Make changes locally
git add .
git commit -m "Update feature"
git push origin main

# 2. Automatic deployment:
# - Render rebuilds backend (2-3 min)
# - Netlify rebuilds frontend (1 min)
# - Changes live!
```

---

## Monitoring & Logs

### Backend Logs (Render)
- Dashboard → Logs tab
- Real-time error tracking

### Frontend Logs (Netlify)
- Deploy logs show build errors
- Function logs for serverless

### Database (Neon)
- Connection pooling metrics
- Query performance

---

## Cost Breakdown

| Service | Free Tier | Paid Plan |
|---------|-----------|-----------|
| **Neon** | 512MB storage, 3 projects | $19/mo (Pro) |
| **Render** | 750 hours/mo, sleeps after 15min | $7/mo (Starter) |
| **Netlify** | 100GB bandwidth, 300 build min | $19/mo (Pro) |

**Total Free**: $0/month (with limitations)
**Total Paid**: ~$45/month (production-ready)

---

## Next Steps

Ready to deploy? I can:
1. Create the required config files
2. Generate migration scripts
3. Set up CI/CD pipeline
4. Add monitoring/alerts

Let me know when to proceed!
