# Arrow Limo Desktop App - Simple Email Installer
# Creates a ZIP file you can email to all 6 machines

**SIMPLIFIED DEPLOYMENT - No EXE needed!**

Instead of a complex EXE, we'll create a simple ZIP file that users extract and run a batch file.

## What You'll Send via Email

1. **ArrowLimoInstaller.zip** (~5-10 MB)
   - Contains: Python installer script
   - Contains: Setup batch file  
   - Contains: Quick start instructions

2. **Neon credentials** (in the ZIP)
   - Database connection details
   - All configuration

## How to Create the Installer Package

Run this command:

```powershell
cd L:\limo
.\create_email_installer.ps1
```

This creates: `L:\limo\dist\ArrowLimoInstaller.zip`

## How Users Install (Simple 3-Step Process)

**Step 1:** Extract the ZIP file

**Step 2:** Right-click `INSTALL.bat` → Run as Administrator  

**Step 3:** Enter machine number (1-6) when prompted

Done! App auto-starts on next login.

---

## Alternative: Web Download Link

If email attachment is too large, you can:
1. Upload `ArrowLimoInstaller.zip` to Google Drive / OneDrive
2. Share the download link with all 6 machines
3. Users download and run `INSTALL.bat`

---

**File size:** ~5-10 MB (easy to email)  
**User effort:** Extract ZIP → Run INSTALL.bat → Enter machine number  
**Time:** ~2 minutes per machine
