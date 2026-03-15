==================================================
ARROW LIMOUSINE DUAL DISPATCHER SETUP
NETWORK POSTGRESQL DATABASE (2026)
==================================================

This package sets up a professional dual-dispatcher system with:
✓ Real-time shared database (both dispatchers see same data instantly)
✓ 10-50x faster than cloud (local network speed)
✓ Works offline (no internet required)
✓ Zero conflicts (PostgreSQL handles multi-user correctly)

WHAT'S INCLUDED
---------------
*** QUICK START GUIDES ***
- QUICK_START.md ← START HERE for complete setup
- NETWORK_DATABASE_SETUP_GUIDE.md ← Technical details
- README_NETWORK_SETUP.txt ← This improved version

*** SETUP SCRIPTS (Run as Administrator) ***
- GET_DISPATCHMAIN_IP.ps1 ← Get database server IP
- SETUP_POSTGRESQL_NETWORK_ACCESS.ps1 ← Enable network database
- TEST_DATABASE_CONNECTION.ps1 ← Verify connectivity
- DispatchInstaller_Dispatch1.ps1 ← Install DISPATCH1

INSTALLATION (30 minutes total)
--------------------------------
STEP 1 - DISPATCHMAIN (15 min):
  1. Run GET_DISPATCHMAIN_IP.ps1 ← Note the IP address
  2. Run SETUP_POSTGRESQL_NETWORK_ACCESS.ps1 ← Configure database

STEP 2 - Test Connection (5 min):
  3. Copy this package to DISPATCH1
  4. Run TEST_DATABASE_CONNECTION.ps1 ← Verify networking works

STEP 3 - DISPATCH1 Install (5 min):
  5. Right-click INSTALL_DISPATCH1_Y_DRIVE.bat
  6. Select "Run as administrator"
  7. Enter DISPATCHMAIN IP when prompted

STEP 4 - Verify (5 min):
  8. Launch app on both machines
  9. Test that changes sync in real-time

✓ SEE QUICK_START.md FOR DETAILED WALKTHROUGH ✓

HOW IT WORKS
------------
BEFORE (Old Setup - Cloud Database):
  DISPATCHMAIN → Internet → Neon Cloud ← Internet ← DISPATCH1
  Problems: Slow, requires internet, network errors

AFTER (New Setup - Network PostgreSQL):
  DISPATCHMAIN (PostgreSQL Server) ←→ Local Network ←→ DISPATCH1
  Benefits: 10-50x faster, offline capable, enterprise-grade

DATABASE ARCHITECTURE:
  • DISPATCHMAIN runs PostgreSQL server (listens on port 5432)
  • DISPATCHMAIN connects via localhost
  • DISPATCH1 connects via IP address (e.g., 192.168.1.100)
  • Both see same data in real-time
  • PostgreSQL handles locking/conflicts automatically

CODE AUTO-UPDATE:
  • Source code lives on L:\limo\desktop_app (DISPATCHMAIN)
  • DISPATCH1 syncs from L: drive on startup
  • Edit code on DISPATCHMAIN → restart on DISPATCH1 → changes applied

PREREQUISITES
-------------
Before starting:
□ Both computers on same local network
□ PostgreSQL already installed on DISPATCHMAIN
□ Python 3.10+ installed on both machines
□ Y: drive created on DISPATCH1 (Disk Management)
□ Administrator access on both machines
□ Know postgres password from DISPATCHMAIN
□ Both computers can ping each other

Check network connectivity:
  ping DISPATCHMAIN  (from DISPATCH1)
  ping DISPATCH1     (from DISPATCHMAIN)

DATABASE CONNECTION
-------------------
DISPATCHMAIN (.env file):
  DB_HOST=localhost
  DB_NAME=almsdata
  DB_USER=postgres
  DB_PASSWORD=[your postgres password]
  WORKSTATION_ID=DISPATCHMAIN

DISPATCH1 (.env file - created by installer):
  DB_HOST=192.168.x.x  (DISPATCHMAIN IP address)
  DB_NAME=almsdata
  DB_USER=postgres
  DB_PASSWORD=[same postgres password]
  WORKSTATION_ID=DISPATCH1

The installer will create DISPATCH1's .env automatically.

NETWORK SHARES
--------------
L: drive (Code source):
  \\DISPATCHMAIN\limo
  Used by DISPATCH1 for auto-updates

Z: drive (Shared files):
  \\DISPATCHMAIN\limo_files
  Used by both dispatchers for documents/exports

AFTER INSTALLATION
------------------
DISPATCHMAIN:
  - PostgreSQL configured for network access
  - Firewall port 5432 opened
  - Config backups saved to Desktop
  - No application changes needed

DISPATCH1:
  - Application installed to Y:\ArrowLimo\
  - Desktop shortcut: "Arrow Limo DISPATCH1"
  - Network drives mapped: L: and Z:
  - Auto-update configured

To launch: Double-click desktop shortcut on each machine

DAILY OPERATIONS
----------------
Morning Startup:
  1. Turn on DISPATCHMAIN first (database server)
  2. Turn on DISPATCH1
  3. Launch app on both - works immediately

During Day:
  - Both dispatchers work simultaneously
  - All changes sync in real-time automatically
  - No special actions needed

Making Code Changes:
  1. Edit code on DISPATCHMAIN (L:\limo\desktop_app\)
  2. Save changes
  3. On DISPATCH1: Close and relaunch app
  4. Auto-update applies changes automatically

TROUBLESHOOTING
---------------

"Cannot connect to database" on DISPATCH1:
  1. Verify DISPATCHMAIN is turned on
  2. Run GET_DISPATCHMAIN_IP.ps1 on DISPATCHMAIN
  3. Ping DISPATCHMAIN from DISPATCH1
  4. Run TEST_DATABASE_CONNECTION.ps1 on DISPATCH1
  5. Check PostgreSQL service running on DISPATCHMAIN

"Port 5432 blocked":
  • Re-run SETUP_POSTGRESQL_NETWORK_ACCESS.ps1 on DISPATCHMAIN
  • Check Windows Firewall (should allow port 5432)
  • Verify router not blocking local traffic

"Auto-update not working":
  • Verify L: drive mapped on DISPATCH1
  • Check DISPATCHMAIN is on and accessible
  • Manually remap: net use L: \\DISPATCHMAIN\limo

"Database is slow":
  • Check network speed (should be 100+ Mbps)
  • Use wired ethernet instead of WiFi
  • Verify no network congestion
  • Check antivirus not scanning database files

App won't start:
  • Check .env file exists (Y:\ArrowLimo\.env on DISPATCH1)
  • Verify Python installed (python --version)
  • Check error log (Y:\ArrowLimo\app_errors.log)
  • Try launching manually: python Y:\ArrowLimo\desktop_app\launcher.py

Network drives won't map:
  • Verify DISPATCHMAIN shares exist
  • Check network credentials
  • Manually test: \\DISPATCHMAIN\limo and \\DISPATCHMAIN\limo_files

FIREWALL REQUIREMENTS
---------------------
DISPATCHMAIN:
  - Port 5432 inbound (PostgreSQL) from local network only
  - Windows Firewall rule automatically created by setup script

DISPATCH1:
  - Port 5432 outbound (to DISPATCHMAIN)
  - Port 445 (SMB for network shares L: and Z:)
  - Usually allowed by default

ADVANTAGES OF NETWORK POSTGRESQL
---------------------------------
vs. Cloud Database (Neon):
  ✓ 10-50x faster (local network vs internet)
  ✓ Works offline (no internet required)
  ✓ No monthly costs
  ✓ Full data control
  ✓ No bandwidth limits

vs. Separate Databases:
  ✓ Real-time sync (no manual syncing)
  ✓ No conflicts (PostgreSQL handles it)
  ✓ Single source of truth
  ✓ Enterprise-grade reliability

vs. Database on Network Share:
  ✓ PostgreSQL supported (network shares corrupt databases)
  ✓ No corruption risk
  ✓ Proper multi-user locking
  ✓ Transaction safety

FILE LOCATIONS
--------------
DISPATCHMAIN:
  - Code: L:\limo\desktop_app\ (source for auto-update)
  - Config: L:\limo\.env
  - Database: C:\Program Files\PostgreSQL\[version]\data\
  - Logs: L:\limo\app_errors.log

DISPATCH1:
  - App: Y:\ArrowLimo\desktop_app\ (synced from L: drive)
  - Config: Y:\ArrowLimo\.env (contains DISPATCHMAIN IP)
  - Desktop: Arrow Limo DISPATCH1.lnk
  - Logs: Y:\ArrowLimo\app_errors.log

Shared Files:
  - Network: Z:\ (mapped to \\DISPATCHMAIN\limo_files)
  - Both dispatchers read/write to same location

BACKUP & RECOVERY
-----------------
Database Backups (DISPATCHMAIN):
  • PostgreSQL config backups saved to Desktop during setup
  • Regular database backups recommended
  • See NETWORK_DATABASE_SETUP_GUIDE.md for backup procedures

Code Backups:
  • Source code on L:\limo is the master copy
  • DISPATCH1 auto-updates from L: drive
  • Keep L:\limo backed up regularly

SECURITY
--------
- PostgreSQL only accepts connections from local network (192.168.x.x)
- Public internet cannot access database
- Firewall restricts to private networks only
- Password authentication required
- Each user tracked with WORKSTATION_ID
- All changes logged with user identification

VERIFICATION CHECKLIST
----------------------
After installation, verify:
□ Both computers can ping each other
□ PostgreSQL service running on DISPATCHMAIN
□ Port 5432 accessible from DISPATCH1
□ Both dispatchers can login to app
□ Changes on one dispatcher appear on other immediately
□ No "database locked" or connection errors
□ Auto-update works (close/reopen on DISPATCH1)
□ Network drives mapped (L: and Z: on DISPATCH1)

MAINTENANCE
-----------
Daily:
  - Auto-updates handle code sync automatically
  - Database syncs in real-time

Weekly:
  - No maintenance required

Monthly:
  - Check disk space on both machines
  - Review error logs
  - Verify backups are working

As Needed:
  - Update .env if database password changes
  - Reinstall if major system changes

SUPPORT & DOCUMENTATION
------------------------
Error Logs:
  DISPATCHMAIN: L:\limo\app_errors.log
  DISPATCH1: Y:\ArrowLimo\app_errors.log

PostgreSQL Logs:
  C:\Program Files\PostgreSQL\[version]\data\log\

Configuration Backups:
  Desktop\pg_backup_[timestamp]\

Documentation Files:
  QUICK_START.md - Complete setup walkthrough
  NETWORK_DATABASE_SETUP_GUIDE.md - Technical reference
  README_NETWORK_SETUP.txt - Detailed overview
  DISPATCH1_SETUP_GUIDE.txt - Additional instructions

==================================================
🚀 READY TO GET STARTED?
==================================================
1. Open QUICK_START.md in this folder
2. Follow the 4-step guide
3. Total setup time: ~30 minutes

Network PostgreSQL Edition - Version 2.0
February 2026 - Arrow Limousine Management System
==================================================
