# Multi-Machine Deployment Setup Guide

**Last Updated:** January 20, 2026  
**Status:** ✅ Ready for deployment (Neon verified with 1,864 charters, 2,464 payments, 2,165 receipts)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                   Neon Database Cloud                    │
│   (ep-curly-dream-afnuyxfx-pooler.c-2.us-west-2...)   │
│                    PG17, 495 tables                      │
└────────────┬──────────────────────────────────────┬─────┘
             │                                      │
      ┌──────┴──────┐                    ┌─────────┴─────────┐
      │              │                    │                   │
   ┌──▼──────┐  ┌───▼──────┐         ┌──▼──────┐       ┌────▼─────┐
   │Machine 1│  │Machine 2 │         │Machine N│  ...  │Local Desk│
   │(Desktop)│  │(Desktop) │         │(Desktop)│       │(Backup)  │
   └─────────┘  └──────────┘         └─────────┘       └──────────┘
   
   All machines connect via PostgreSQL connection pool (10 connections)
   App code synced via network share or Git
   Auto-start via Task Scheduler on each machine
```

---

## Prerequisites

Before deploying to 6 machines:

1. **Network share created:**
   ```
   \\SERVER\arrow-limo-app
   (contains: main.py, desktop_app/, requirements.txt, .env.neon)
   ```

2. **Each machine has:**
   - Windows 10/11 with PowerShell 5.1+
   - Python 3.12+ (or use bundled portable Python)
   - Network access to `\\SERVER\arrow-limo-app`
   - Network access to Neon endpoint (ep-curly-dream-*.us-west-2.aws.neon.tech:5432)

3. **Neon database verified:**
   - ✅ 1,864 charters
   - ✅ 2,464 payments
   - ✅ 2,165 receipts
   - ✅ 14 employees
   - ✅ 26 vehicles
   - Connection pool: ~10 concurrent (sufficient for 6 users)

---

## Deployment Steps

### Step 0: Set Up Network Share

**On the network server (\\SERVER):**

```powershell
# Create share directory
New-Item -ItemType Directory -Path "D:\Shares\arrow-limo-app" -Force

# Share it on network (set permissions to "Everyone: Read")
# Right-click folder → Properties → Sharing tab → Share button
# Add "Everyone" with Read permission
```

**Network share should contain:**
```
\\SERVER\arrow-limo-app\
├── main.py
├── desktop_app\
│   ├── __init__.py
│   ├── advanced_mega_menu_widget.py
│   ├── dashboard_classes.py
│   └── ... (all dashboard widgets)
├── requirements.txt
├── .env.neon
└── README_DEPLOYMENT.md
```

---

### Step 1: Run Setup on Machine 1

**On Machine 1 (first desktop):**

```powershell
# Open PowerShell as Administrator
cd L:\limo

# Run deployment setup script
.\scripts\setup_machine_deployment.ps1 -MachineNumber 1 -NetworkShare "\\SERVER\arrow-limo-app"
```

**What the script does:**
- ✅ Verifies network share access
- ✅ Copies app files to `C:\ArrowLimoApp`
- ✅ Sets up Python environment (.env file)
- ✅ Installs Python dependencies
- ✅ Creates Task Scheduler job for auto-start
- ✅ Creates desktop shortcut
- ✅ Tests Neon connection
- ✅ Displays connection summary

**Expected output:**
```
========================================
Setup Complete for Machine #1
========================================

Configuration Summary:
  Local App Path: C:\ArrowLimoApp
  Task Name: \ArrowLimo\ArrowLimoApp-Machine1
  Auto-start: Enabled (on login)
  Database: Neon (ep-curly-dream-*.us-west-2.aws.neon.tech)

✓ Neon connection verified
✓ Charters table: 1864 rows
```

**Manual verification:**
```powershell
# Test manually (before logout)
cd C:\ArrowLimoApp
python -X utf8 main.py

# When app opens:
# - Enter any test user credentials
# - Verify login dialog appears
# - Check rate limiting works
# - Close app
```

---

### Step 2: Repeat for Machines 2–6

**On each additional machine:**

```powershell
# Open PowerShell as Administrator
# Download setup script from network share or copy locally

# For Machine 2:
.\setup_machine_deployment.ps1 -MachineNumber 2 -NetworkShare "\\SERVER\arrow-limo-app"

# For Machine 3:
.\setup_machine_deployment.ps1 -MachineNumber 3 -NetworkShare "\\SERVER\arrow-limo-app"

# ... and so on for Machines 4, 5, 6
```

**Or use a batch script to automate (optional):**

```powershell
# batch_deploy_all_machines.ps1
$machines = @(1, 2, 3, 4, 5, 6)
$networkShare = "\\SERVER\arrow-limo-app"
$setupScript = "\\SERVER\arrow-limo-app\scripts\setup_machine_deployment.ps1"

foreach ($machineNum in $machines) {
    Write-Host "Deploying to Machine $machineNum..." -ForegroundColor Cyan
    & $setupScript -MachineNumber $machineNum -NetworkShare $networkShare
    Start-Sleep -Seconds 5
}
```

---

## Verification Checklist

After deploying all 6 machines, verify:

| Machine | Status | Notes |
|---------|--------|-------|
| 1       | ✓ Setup | Auto-start enabled |
| 2       | ✓ Setup | Auto-start enabled |
| 3       | ✓ Setup | Auto-start enabled |
| 4       | ✓ Setup | Auto-start enabled |
| 5       | ✓ Setup | Auto-start enabled |
| 6       | ✓ Setup | Auto-start enabled |

**Test concurrent connections:**

```powershell
# Run this on ANY machine to test all 6 connecting simultaneously
python -c "
import psycopg2
import threading
import os
from dotenv import load_dotenv

load_dotenv('.env')

def test_connection(machine_id):
    try:
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST'),
            database=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            sslmode='require'
        )
        print(f'Machine {machine_id}: Connected ✓')
        conn.close()
    except Exception as e:
        print(f'Machine {machine_id}: Failed ✗ ({e})')

threads = []
for i in range(1, 7):
    t = threading.Thread(target=test_connection, args=(i,))
    threads.append(t)
    t.start()

for t in threads:
    t.join()

print('All 6 concurrent connections tested.')
"
```

---

## Maintenance & Updates

### Auto-Sync Code from Network Share

Every time code changes are pushed to the network share, machines will load the latest version on next **login or manual app restart**.

**To push an update:**

1. **On your development machine:**
   ```powershell
   # Update network share files
   Copy-Item -Path "L:\limo\main.py" -Destination "\\SERVER\arrow-limo-app\main.py" -Force
   Copy-Item -Path "L:\limo\desktop_app\*" -Destination "\\SERVER\arrow-limo-app\desktop_app\" -Recurse -Force
   Copy-Item -Path "L:\limo\requirements.txt" -Destination "\\SERVER\arrow-limo-app\requirements.txt" -Force
   ```

2. **Users see update on next login** (or manually restart app from desktop shortcut)

### Backup & Disaster Recovery

**Weekly backup to local drive (on each machine):**

```powershell
# Run this daily via Task Scheduler (e.g., 2:00 AM)
.\backup_neon_to_local.ps1

# Backs up:
# - Neon database → C:\ArrowLimoApp\backups\neondb_YYYY-MM-DD.dump
# - Keeps 7-day rolling history
```

---

## Troubleshooting

### Issue: App doesn't auto-start on login

**Solution:**
```powershell
# Check task exists
Get-ScheduledTask -TaskPath "\ArrowLimo\" -TaskName "ArrowLimoApp-Machine1"

# Manually trigger for testing
Start-ScheduledTask -TaskPath "\ArrowLimo\" -TaskName "ArrowLimoApp-Machine1"

# View task history
Get-ScheduledTaskInfo -TaskPath "\ArrowLimo\" -TaskName "ArrowLimoApp-Machine1"
```

### Issue: "Cannot access network share"

**Solution:**
```powershell
# Verify share is reachable
Test-Path "\\SERVER\arrow-limo-app"

# Test from command line
net view \\SERVER

# Check if share permissions allow READ
# (Right-click share → Properties → Sharing → Permissions)
```

### Issue: Neon connection fails

**Solution:**
```powershell
# Check .env file in C:\ArrowLimoApp\.env
Get-Content C:\ArrowLimoApp\.env | Select-String "DB_"

# Test connection manually
python -c "
import psycopg2
import os
from dotenv import load_dotenv
load_dotenv('C:\\ArrowLimoApp\\.env')
conn = psycopg2.connect(
    host=os.getenv('DB_HOST'),
    database=os.getenv('DB_NAME'),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD'),
    sslmode='require'
)
print('Connected to Neon ✓')
"
```

### Issue: Python dependencies missing

**Solution:**
```powershell
cd C:\ArrowLimoApp
python -m pip install -r requirements.txt --upgrade
```

---

## Connection Pool Monitoring

**Check active connections to Neon:**

```sql
SELECT 
    usename,
    application_name,
    client_addr,
    state,
    query_start,
    state_change
FROM pg_stat_activity
WHERE datname = 'neondb'
ORDER BY state_change DESC;
```

**Expected:** Up to 6 concurrent connections (1 per machine) when all are logged in.  
**Connection pool:** ~10 connections (5 reserved for admin/maintenance).

---

## Rollback

If you need to revert to a previous version:

```powershell
# On network server, restore previous version
Copy-Item -Path "\\BACKUP_SERVER\arrow-limo-app-v1.0\*" `
          -Destination "\\SERVER\arrow-limo-app\" `
          -Recurse -Force

# Users will load the rolled-back version on next login
```

---

## Support & Logging

**App logs are stored in:**
```
C:\ArrowLimoApp\logs\
└── app_YYYY-MM-DD.log
```

**To monitor a machine in real-time:**
```powershell
Get-Content -Path "C:\ArrowLimoApp\logs\app_2026-01-20.log" -Wait
```

---

**Next Steps:**
1. ✅ Set up network share on \\SERVER
2. ✅ Run `setup_machine_deployment.ps1` on each machine
3. ✅ Log out and back in (or manually start Task Scheduler job)
4. ✅ Test all 6 machines connect to Neon simultaneously
5. ✅ Verify app loads and responds normally

**Questions?** Check the logs or reach out to your IT team for network share access issues.
