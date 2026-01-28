# QUICK START: Deploy Arrow Limo App to Your Machine

**Your Machine Number:** _____ (fill in: 1, 2, 3, 4, 5, or 6)

---

## 🚀 3-Step Setup (5 Minutes)

### Step 1: Open PowerShell as Administrator

```
Windows Key → Type: powershell → Right-click → Run as Administrator
```

### Step 2: Run This Command

Replace `{YOUR_MACHINE_NUMBER}` with your machine number (1-6):

```powershell
.\setup_machine_deployment.ps1 -MachineNumber {YOUR_MACHINE_NUMBER} -NetworkShare "\\Dispatchmain\ArrowLimoApp"
```

**Example for Machine 1:**
```powershell
.\setup_machine_deployment.ps1 -MachineNumber 1 -NetworkShare "\\Dispatchmain\ArrowLimoApp"
```

### Step 3: Wait for Completion

When you see this:
```
✓ Neon connection verified
✓ Charters table: 1864 rows

Setup Complete for Machine #1
```

You're done! ✅

---

## 🔑 Auto-Start Setup

**The app will automatically start when you log in.**

To activate:
1. **Log out completely** (not just lock)
2. **Log back in**
3. **App starts automatically** (in 10-20 seconds)

---

## 🖼️ Desktop Shortcut

A shortcut was created on your desktop:
- **Arrow Limo App.lnk**

Click it anytime to manually start the app.

---

## 🐛 Troubleshooting

### "Can't access \\Dispatchmain\ArrowLimoApp"

```powershell
# First, make sure Dispatchmain is powered on
ping Dispatchmain

# Then try again:
Test-Path "\\Dispatchmain\ArrowLimoApp"
```

If still fails, check with your IT support about network sharing.

### "Python not found"

Install Python 3.12+:
1. Go to: https://www.python.org/downloads/
2. Download and install
3. Re-run the setup script

### "Neon connection failed"

```powershell
# Check your .env file
Get-Content "C:\ArrowLimoApp\.env"

# Should show database credentials
```

If you see errors, contact support.

---

## ✅ Verification

After setup, test manually:

```powershell
cd C:\ArrowLimoApp
python -X utf8 main.py
```

**In the app:**
1. Try logging in (any username/password)
2. Check the rate limiting (5 attempts max)
3. Look for the dashboard
4. Close when done

---

## 📋 What Gets Installed

| Item | Location |
|------|----------|
| App code | `C:\ArrowLimoApp` |
| Auto-start task | Task Scheduler → \ArrowLimo\ |
| Desktop shortcut | `Desktop\Arrow Limo App.lnk` |
| Config file | `C:\ArrowLimoApp\.env` |
| Logs | `C:\ArrowLimoApp\logs\` |

---

## 🔐 Security

- App connects to cloud database (Neon)
- All credentials are in `.env` (read-only)
- Passwords hashed with PBKDF2
- Session timeout: 30 minutes

---

## 📞 Need Help?

**Check the logs:**
```powershell
Get-Content "C:\ArrowLimoApp\logs\app_*.log" -Tail 50
```

**Manual connection test:**
```powershell
cd C:\ArrowLimoApp
python -c "
import psycopg2
from dotenv import load_dotenv
import os

load_dotenv('.env')

try:
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST'),
        database=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        sslmode='require'
    )
    print('✓ Connected to Neon database')
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM public.charters')
    print(f'✓ Found {cur.fetchone()[0]} charters in database')
    conn.close()
except Exception as e:
    print(f'✗ Connection failed: {e}')
"
```

---

## 🎯 You're All Set!

✅ App installed  
✅ Auto-start configured  
✅ Neon connection ready  
✅ Desktop shortcut created

**Log out and log back in to see the app start automatically.** 🚀

---

**Network Share:** `\\Dispatchmain\ArrowLimoApp`  
**Full Setup Guide:** `L:\limo\DEPLOYMENT_READY.md` (on Dispatchmain)  
**Issues?** See troubleshooting above or check `C:\ArrowLimoApp\logs\`
