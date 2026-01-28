# RENDER DEPLOYMENT - STEP BY STEP

## ✅ Pre-Flight Check
- [x] requirements.txt generated
- [x] Procfile created
- [x] render.yaml created
- [x] Code ready for production

---

## 🚀 DEPLOY TO RENDER (10 minutes)

### Step 1: Sign Up to Render
1. Go to **https://render.com**
2. Click **Sign Up**
3. Use GitHub to sign up (easier)
4. Authorize GitHub access

### Step 2: Create Web Service
1. Dashboard → **New +** dropdown → **Web Service**
2. Connect GitHub repository
   - Select your repo (arrow-limo or whatever it's called)
   - Click **Connect**

### Step 3: Configure Service
Fill in these fields:

| Field | Value |
|-------|-------|
| **Name** | `arrow-limo-api` |
| **Root Directory** | `modern_backend` |
| **Runtime** | `Python 3.11` |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| **Environment** | `Production` |

### Step 4: Set Environment Variables ⚠️ IMPORTANT
Click **Add Environment Variable** and add these (get values from Neon):

**From your Neon connection string** `postgresql://user:password@host/dbname`:

1. **DATABASE_URL**
   - Value: Your full Neon connection string
   - Example: `postgresql://user123:pass456@db.neon.tech/almsdata?sslmode=require`

2. **DB_HOST**
   - Value: Extract from connection (the host part)
   - Example: `db.neon.tech`

3. **DB_NAME**
   - Value: `almsdata` (your database name)

4. **DB_USER**
   - Value: Your Neon username
   - Example: `user123`

5. **DB_PASSWORD**
   - Value: Your Neon password
   - Example: `pass456`

⚠️ **Click the lock icon** next to each to mark as secret (encrypted)

### Step 5: Deploy
1. Click **Create Web Service**
2. Wait 2-3 minutes for build
3. Watch the logs scroll by
4. Should see: `✓ Build successful`
5. Get your API URL: `https://arrow-limo-api.onrender.com` (or custom name)

### Step 6: Test Backend
Visit: `https://arrow-limo-api.onrender.com/docs`

Should see:
- ✅ FastAPI Swagger UI loads
- ✅ All endpoints listed
- ✅ Database connection working

If errors:
- Click **Logs** in Render dashboard
- Look for error messages
- Common issues:
  - ❌ Database connection string wrong → Copy from Neon again
  - ❌ Port binding issue → Check Start Command
  - ❌ Missing dependency → Check requirements.txt

---

## 📝 Get Your Neon Connection String

1. Go to **https://console.neon.tech**
2. Select your project
3. Find "Connection string"
4. Should look like:
   ```
   postgresql://user:password@host/dbname?sslmode=require
   ```
5. Copy the **entire string** → Paste into Render `DATABASE_URL`

---

## 🔄 Auto-Deploy from GitHub

Once deployed, Render automatically redeploys when you push to GitHub:

```bash
# Make changes locally
git add .
git commit -m "Update feature"
git push origin main

# Automatic:
# - Render detects push
# - Rebuilds in 2-3 minutes
# - Changes live!
# - No manual redeploy needed
```

---

## ✅ You're Live!

After deployment completes:

**Backend Running At:**
```
https://arrow-limo-api.onrender.com
```

**API Documentation:**
```
https://arrow-limo-api.onrender.com/docs
```

**Next Step:** Deploy frontend to Netlify

---

## ⚠️ Troubleshooting

### "Build Failed"
```
Check logs → Usually missing dependency
Solution: pip freeze > requirements.txt (again)
```

### "Connection Timeout"
```
Database connection string wrong
Solution: Copy full Neon string including ?sslmode=require
```

### "500 Internal Server Error"
```
API error → Check logs
Solution: Look at the error traceback in logs
```

### Backend Sleeping (Free Tier)
```
Free tier spins down after 15 min inactivity
Solution: Upgrade to Starter ($7/mo) or accept first request takes 30 sec
```

---

## 🎯 Final Checklist

Before going live:
- [ ] Neon connection string copied
- [ ] All 5 env variables set (with lock icons)
- [ ] Build completed successfully
- [ ] /docs endpoint responds
- [ ] Database connection working
- [ ] Logs show no errors

**Ready to deploy?** I can help if you get stuck at any step!
