# Arrow Limo Multi-Machine Deployment - READY TO GO

**Status:** ✅ Ready for deployment to 6 machines  
**Date:** January 20, 2026  
**Network Share Host:** `Dispatchmain` (this machine)

---

## 🚀 Quick Start

### For Other Machines to Access:

```
Network Path: \\Dispatchmain\ArrowLimoApp
```

**On each of the 6 remote machines, run (in PowerShell as Administrator):**

```powershell
# Machine 1
.\setup_machine_deployment.ps1 -MachineNumber 1 -NetworkShare "\\Dispatchmain\ArrowLimoApp"

# Machine 2
.\setup_machine_deployment.ps1 -MachineNumber 2 -NetworkShare "\\Dispatchmain\ArrowLimoApp"

# ... repeat for Machines 3-6
```

---

## 📋 Network Share Contents

The following files are now ready at `L:\limo\network_share_deployment`:

```
L:\limo\network_share_deployment\
├── main.py                    ← Desktop app entry point
├── requirements.txt           ← Python dependencies
├── .env.neon                  ← Neon database credentials
└── desktop_app\               ← All dashboard widgets and components
    ├── admin_management_widget.py
    ├── advanced_mega_menu_widget.py
    ├── dashboards_*.py
    ├── ... (136 widgets total)
    └── ...
```

**Network accessible as:** `\\Dispatchmain\ArrowLimoApp`

---

## ✅ Pre-Deployment Checklist

Before running setup on remote machines:

- [x] Neon database verified (1,864 charters, 2,464 payments, 2,165 receipts)
- [x] Network share created and accessible
- [x] Credentials in `.env.neon` (Neon connection details)
- [x] Setup script ready: `setup_machine_deployment.ps1`
- [x] All app files copied to network share
- [x] Computer name: **Dispatchmain**

---

## 🔧 Deployment Steps (For Each Machine)

### Step 1: Open PowerShell as Administrator

On each of the 6 remote machines.

### Step 2: Copy Setup Script

Download or copy `setup_machine_deployment.ps1` to the remote machine:

```powershell
# From L:\limo on this machine, copy the script to each remote machine
Copy-Item -Path "L:\limo\scripts\setup_machine_deployment.ps1" `
          -Destination "\\RemoteMachine\C$\Users\$env:USERNAME\Downloads\" `
          -Force
```

Or manually copy `L:\limo\scripts\setup_machine_deployment.ps1` to each machine.

### Step 3: Run Setup Script

```powershell
cd C:\Users\YourUsername\Downloads

# For Machine 1:
.\setup_machine_deployment.ps1 -MachineNumber 1 -NetworkShare "\\Dispatchmain\ArrowLimoApp"

# Wait for completion (should see: "✓ Neon connection verified")
```

### Step 4: Log Out and Back In

Auto-start task will trigger on next login.

### Step 5: Verify

```powershell
# Check that desktop shortcut was created
Get-Item "$env:USERPROFILE\Desktop\Arrow Limo App.lnk"

# Test manual start
Start-ScheduledTask -TaskPath "\ArrowLimo\" -TaskName "ArrowLimoApp-Machine1"
```

---

## 🔌 Network Connectivity Requirements

Each machine needs:
- ✅ Network access to `\\Dispatchmain\ArrowLimoApp` (for app files)
- ✅ Internet access to Neon: `ep-curly-dream-afnuyxfx-pooler.c-2.us-west-2.aws.neon.tech:5432`
- ✅ Python 3.12+ installed (or will be installed by setup script)

---

## 📊 Connection Pool Status

**Neon Configuration:**
- Database: `neondb`
- User: `neondb_owner`
- Connection pool: ~10 concurrent connections
- Expected load: 6 users (sufficient ✅)

**Current Data:**
- Charters: 1,864
- Payments: 2,464
- Receipts: 2,165
- Employees: 14
- Vehicles: 26

---

## 🛠️ Troubleshooting

### Can't access network share?

```powershell
# Verify network connectivity
Test-Connection Dispatchmain -ErrorAction SilentlyContinue

# Try to access share
Test-Path "\\Dispatchmain\ArrowLimoApp"

# If fails, try with FQDN or IP
Test-Path "\\Dispatchmain.local\ArrowLimoApp"
```

### Neon connection fails?

```powershell
# Check .env file
Get-Content "C:\ArrowLimoApp\.env" | Select-String "DB_"

# Test manually
python -c "
import psycopg2
import os
from dotenv import load_dotenv
load_dotenv('C:\\ArrowLimoApp\\.env')
conn = psycopg2.connect(
    host=os.getenv('DB_HOST'),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD'),
    database=os.getenv('DB_NAME'),
    sslmode='require'
)
print('✓ Connected to Neon')
"
```

### Task Scheduler not auto-starting app?

```powershell
# Check if task exists
Get-ScheduledTask -TaskPath "\ArrowLimo\" | Select-Object TaskName, State

# Manually trigger
Start-ScheduledTask -TaskPath "\ArrowLimo\" -TaskName "ArrowLimoApp-Machine1"

# View logs
Get-ScheduledTaskInfo -TaskPath "\ArrowLimo\" -TaskName "ArrowLimoApp-Machine1"
```

---

## 📝 Network Share Management

### Keep Share Running

The share `\\Dispatchmain\ArrowLimoApp` will remain active as long as:
1. This machine (Dispatchmain) is powered on
2. Windows File Sharing is enabled
3. Network is connected

### Update Files

When code changes are needed:

```powershell
# On Dispatchmain, update the shared files
Copy-Item "L:\limo\main.py" "L:\limo\network_share_deployment\" -Force
Copy-Item "L:\limo\desktop_app\*" "L:\limo\network_share_deployment\desktop_app\" -Recurse -Force

# All 6 machines will load the latest version on next app restart
```

### Backup Network Share

```powershell
# Backup deployment package daily
$backup = "L:\limo\network_share_backup_$(Get-Date -Format 'yyyy-MM-dd').zip"
Compress-Archive -Path "L:\limo\network_share_deployment" -DestinationPath $backup -Force
```

---

## 🎯 Next Actions

1. **On this machine (Dispatchmain):**
   - ✅ Network share created: `\\Dispatchmain\ArrowLimoApp`
   - ✅ All files copied to network share
   - ✅ Ready for deployment

2. **On each remote machine (1-6):**
   - [ ] Download `setup_machine_deployment.ps1`
   - [ ] Run setup script with correct machine number
   - [ ] Log out and back in (or manually start task)
   - [ ] Verify app starts and connects to Neon

3. **Verification:**
   - [ ] All 6 machines can access `\\Dispatchmain\ArrowLimoApp`
   - [ ] All 6 apps connect to Neon simultaneously
   - [ ] Login dialog appears and auth works
   - [ ] Dashboard loads without errors

---

## 📞 Support

**Common Issues:**
- Network share not accessible → Check Windows Firewall (File Sharing enabled)
- Neon connection fails → Verify IP whitelisting or firewall rules
- Python dependencies missing → Run `python -m pip install -r requirements.txt`
- Task Scheduler not starting app → Check task history and logs

**Log Locations:**
- Desktop app logs: `C:\ArrowLimoApp\logs\app_YYYY-MM-DD.log`
- Task Scheduler history: Event Viewer → Windows Logs → System (filter: Task Scheduler)

---

**Ready to deploy!** 🚀

Network Share: `\\Dispatchmain\ArrowLimoApp`  
Setup Script: `L:\limo\scripts\setup_machine_deployment.ps1`  
Neon Status: ✅ Verified (1,864 charters ready)
