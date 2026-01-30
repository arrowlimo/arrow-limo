# Arrow Limousine Desktop App - Dispatcher Installation Guide

## What's Included

This package contains a standalone Windows application that gives dispatchers access to the Arrow Limousine Management System without needing Python, Visual Studio Code, or any development tools.

**Files:**
- `ArrowLimousineApp.exe` - The complete application (standalone, no installation required)
- `.env.example` - Configuration template (copy and edit with your credentials)
- `DISPATCHER_SETUP.md` - This file

## System Requirements

- **Windows 10 or Windows 11** (64-bit)
- **4GB RAM minimum** (8GB recommended)
- **100MB free disk space**
- **Internet connection** (to connect to the cloud database)

## Installation & Setup (5 minutes)

### Step 1: Extract the Package
1. Download or receive the ZIP file `ArrowLimousine_Installer.zip`
2. Extract it to a folder, e.g., `C:\ArrowLimousine` or `D:\Apps\ArrowLimousine`
3. You should see:
   - `ArrowLimousineApp.exe`
   - `.env.example`

### Step 2: Create Configuration File
1. **Inside the same folder**, copy `.env.example` to `.env`
   - Right-click `.env.example` → Copy
   - Right-click in empty space → Paste
   - Rename to `.env`

2. **Edit the `.env` file** with your database credentials:
   - Right-click `.env` → Open with → Notepad
   - Find these lines and fill in your values:
     ```
     DB_HOST=your-neon-host.us-west-2.aws.neon.tech
     DB_PORT=5432
     DB_NAME=almsdata
     DB_USER=your_neon_username
     DB_PASSWORD=your_neon_password
     ```
   - **Replace** `your-neon-host`, `your_neon_username`, `your_neon_password` with actual values provided by the office
   - Save the file (Ctrl+S)

### Step 3: Run the Application
1. **Double-click** `ArrowLimousineApp.exe`
2. **Wait 5-10 seconds** for the app to start (first launch is slower)
3. When prompted, **login with your dispatcher credentials**:
   - Username: (provided by office)
   - Password: (provided by office)

### Step 4: You're Done!
- The application is now running on your computer
- **No installation needed** - it's completely portable
- You can move the folder anywhere or run it from USB drive if needed

---

## Features Available

Once logged in, you have full access to:

### Dashboard
- **Navigator Tab** - Jump to any feature you need
- **Quick Charts** - Overview of daily activity
- **Upcoming Bookings** - Today's and tomorrow's charters

### Management
- **Charter Management** - View/edit bookings
- **Fleet Management** - Vehicle information and status
- **Employee Management** - Driver and staff info
- **Customer Management** - Client database with history
- **Billing** - Invoices and payments
- **Reports** - Detailed financial and operational reports
- **Quote Generator** - Create custom quotes for new bookings

### Operations
- **Dispatcher Calendar** - Schedule management
- **Banking** - Bank account reconciliation
- **Expenses** - Receipt and cost tracking
- **Payroll** - Driver and staff payments

---

## Troubleshooting

### "The app won't start"
1. Check Windows Defender isn't blocking it (click "More info" → "Run anyway")
2. Ensure `.env` file is in the same folder as `ArrowLimousineApp.exe`
3. Check your internet connection (needed for database access)
4. Try running as Administrator (right-click → Run as administrator)

### "Database connection failed"
1. Open `.env` with Notepad
2. Verify `DB_HOST`, `DB_USER`, `DB_PASSWORD` are correct
3. Ask your office manager for the exact credentials
4. Make sure you have internet access
5. Check if Neon database is accessible: ask office to verify

### "Login failed"
1. Check username and password are correct (case-sensitive)
2. Ensure Caps Lock is off
3. Ask office manager to verify your user account is active
4. Try logging in with a different user account to test

### "App runs but shows blank windows"
1. Close the app (Alt+F4)
2. Delete the `.env` file
3. Copy `.env.example` again
4. Re-enter credentials carefully
5. Restart the app

### "The app is very slow"
1. Check internet connection (database is cloud-based)
2. Close other applications using internet (downloads, video streaming)
3. Restart the app
4. If still slow, contact office IT

---

## Tips & Tricks

### Create a Shortcut on Desktop
1. Right-click `ArrowLimousineApp.exe` → Create shortcut
2. Move the shortcut to your Desktop
3. Double-click the shortcut to launch from Desktop

### Auto-Start on Windows Startup (Optional)
1. Press **Windows + R** to open Run dialog
2. Type `shell:startup` and press Enter
3. Copy your shortcut or `.exe` into this folder
4. The app will launch when Windows starts

### Portable to USB Drive
- The entire folder is portable
- Copy `C:\ArrowLimousine` to a USB drive
- Run `ArrowLimousineApp.exe` directly from the USB on any Windows PC
- It works without installation!

### Updating the App
- When the office provides a new version:
  1. Close the current app
  2. Backup your `.env` file (copy somewhere safe)
  3. Delete the old folder
  4. Extract the new version
  5. Copy your backed-up `.env` into the new folder
  6. Run the new `ArrowLimousineApp.exe`

---

## Security Notes

⚠️ **Important:** Your `.env` file contains database credentials. Keep it safe!

- Never share your `.env` file
- Never commit it to version control
- Don't email it or upload to cloud storage
- Keep it only on your computer in the application folder

---

## Getting Help

If you encounter issues:

1. **Check this guide** - Section "Troubleshooting" above
2. **Verify credentials** - Ask your office manager for current DB credentials
3. **Test database connection** - Try with the web app at https://arrow-limo.onrender.com to verify creds work
4. **Contact IT** - Reach out to your office manager or IT support with:
   - What you were trying to do
   - The exact error message you received
   - Screenshot of the error
   - Your Windows version (Windows + Pause/Break → System)

---

## Additional Resources

- **Web Version** - https://arrow-limo.onrender.com (same app, accessible from browser)
- **Quick Start Video** - Ask your office manager for the training video
- **Feature Documentation** - Available in the app under Help → Documentation

---

**Version:** 1.0  
**Last Updated:** January 30, 2026  
**Built for:** Windows 10/11 (64-bit)

