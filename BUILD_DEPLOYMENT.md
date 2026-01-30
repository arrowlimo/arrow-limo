# Arrow Limousine Desktop App - Deployment Package Creator

This folder contains everything needed to build a standalone Windows executable that dispatchers can run locally without needing Python, Git, or any development tools.

## Quick Start

### For Windows (Easiest - Double-click to build)
```
Double-click: build_exe.bat
```

### For PowerShell (More control)
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.\build_exe.ps1
```

### For Python/Command Line
```bash
# Install dependencies first
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt

# Then build
.\.venv\Scripts\pyinstaller build_desktop_app.spec --noconfirm
```

---

## Files Explained

### Build Files
| File | Purpose |
|------|---------|
| `build_exe.bat` | Windows batch file - double-click to build (easiest) |
| `build_exe.ps1` | PowerShell script - advanced build with options |
| `build_desktop_app.spec` | PyInstaller configuration - defines what to include in exe |

### Configuration Files  
| File | Purpose |
|------|---------|
| `.env.example` | Template for database credentials (dispatcher copies and edits) |
| `.env` | Actual credentials (created automatically from .env.example) |

### Documentation
| File | Purpose |
|------|---------|
| `BUILD_DEPLOYMENT.md` | This file - build system documentation |
| `DISPATCHER_SETUP.md` | Instructions for dispatcher installing the app |

### Output
| Location | Purpose |
|----------|---------|
| `dist/ArrowLimousineApp.exe` | The standalone executable |
| `dist/ArrowLimousine_Deployment/` | Pre-packaged folder ready for distribution |

---

## Build Process

### Step 1: Prepare Environment
```powershell
# Ensure virtual environment and dependencies are ready
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\pip install pyinstaller
```

### Step 2: Configure Credentials
Create or edit `.env` file with your Neon database credentials:
```
DB_HOST=your-neon-endpoint.us-west-2.aws.neon.tech
DB_PORT=5432
DB_NAME=almsdata
DB_USER=your_username
DB_PASSWORD=your_password
DB_SSLMODE=require
```

### Step 3: Build Executable
**Option A: Windows batch (easiest)**
```
Double-click build_exe.bat
```

**Option B: PowerShell**
```powershell
.\build_exe.ps1 -Clean    # Clean build, removes old artifacts
```

**Option C: Manual PyInstaller**
```powershell
.\.venv\Scripts\pyinstaller.exe build_desktop_app.spec --noconfirm
```

### Step 4: Verify Build
- ✓ Check `dist/ArrowLimousineApp.exe` exists
- ✓ Check `dist/ArrowLimousine_Deployment/` folder is populated
- ✓ Test the exe by double-clicking it

---

## What Gets Included in the Executable

The `build_desktop_app.spec` file configures PyInstaller to bundle:

### Python Code
- `desktop_app/main.py` - Main application
- All widget modules (100+ files)
- All dashboard and reporting modules

### Data Files
- `desktop_app/ai_knowledge_db/` - Knowledge base for AI features
- `desktop_app/mega_menu_structure.json` - Menu structure
- `config/` - Configuration files

### Dependencies (automatically included)
- PyQt6 - GUI framework
- psycopg2 - PostgreSQL/Neon database client
- reportlab - PDF generation
- openpyxl - Excel export
- python-dotenv - Environment variable loading
- All other dependencies from requirements.txt

### Hidden Imports
The spec file explicitly includes:
- PyQt6 components (widgets, core, gui, web engine)
- Database adapters (psycopg2 extensions)
- Report generation libraries
- Standard library modules

---

## Distribution Package

After successful build, the `dist/ArrowLimousine_Deployment/` folder contains:

```
ArrowLimousine_Deployment/
├── ArrowLimousineApp.exe          ← Run this!
├── .env.example                    ← Copy to .env, edit credentials
└── DISPATCHER_SETUP.md             ← Installation instructions
```

### To Create Installer ZIP
```powershell
# After build completes:
$folder = ".\dist\ArrowLimousine_Deployment"
Compress-Archive -Path $folder -DestinationPath "ArrowLimousine_Installer.zip" -Force
```

### To Send to Dispatcher
1. Send `ArrowLimousine_Installer.zip` file
2. Dispatcher extracts it
3. Dispatcher reads `DISPATCHER_SETUP.md`
4. Dispatcher edits `.env` with their credentials
5. Dispatcher runs `ArrowLimousineApp.exe`

---

## Advanced Build Options

### PowerShell Flags
```powershell
# Clean build (removes build/ and dist/ folders)
.\build_exe.ps1 -Clean

# Incremental build (keeps previous artifacts, faster)
.\build_exe.ps1

# Skip clean (alias)
.\build_exe.ps1 -NoClean
```

### PyInstaller Advanced Options
```powershell
# Add console window (for debugging)
pyinstaller build_desktop_app.spec --console

# Windowed mode (default, no console)
pyinstaller build_desktop_app.spec --windowed

# One-file bundle (larger exe, but simpler distribution)
pyinstaller build_desktop_app.spec --onefile

# With debug symbols
pyinstaller build_desktop_app.spec --debug
```

---

## Troubleshooting Build Issues

### "Failed to install PyInstaller"
```powershell
# Ensure pip is up to date
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\pip install pyinstaller
```

### "Import error for PyQt6"
```powershell
# Reinstall PyQt6
.\.venv\Scripts\pip uninstall pyqt6 -y
.\.venv\Scripts\pip install PyQt6>=6.6.0
```

### "Module not found errors"
Add the missing module to `build_desktop_app.spec` in the `hiddenimports` list:
```python
hiddenimports=[
    'PyQt6.QtWidgets',
    'your_missing_module',  # ← Add here
    # ... rest of imports
]
```

### Build takes too long (>5 min)
- First build is slower (collects all dependencies)
- Subsequent builds are faster
- SSD is faster than HDD
- Close other applications to free CPU

### Output exe is very large (>500MB)
- This is normal for PyQt6 + Python bundle
- First-time exe is comprehensive
- Distribute as ZIP for file transfer
- Extracting once on dispatcher PC is fine (no re-extraction needed)

---

## Testing the Build

### Quick Test
1. **Close the application** if running
2. **Delete the built executable** from previous build:
   ```powershell
   Remove-Item -Recurse -Force ".\dist", ".\build" -ErrorAction SilentlyContinue
   ```
3. **Run build**:
   ```powershell
   .\build_exe.ps1 -Clean
   ```
4. **Double-click the new exe** to verify it launches

### Database Connection Test
After exe launches:
1. You should see the login dialog
2. Enter your database credentials (from .env)
3. You should see the charter management interface
4. Try loading a sample widget to verify database connectivity

### Dispatcher Installation Test
1. Create a test folder: `C:\Test_Dispatcher`
2. Copy `ArrowLimousine_Deployment` contents to it
3. Run `ArrowLimousineApp.exe` from that folder
4. Verify it works from a clean directory

---

## Customization

### Adding Application Icon
Place `icon.ico` in the desktop_app folder, then rebuild:
```powershell
# The spec file already looks for desktop_app/icon.ico
# Just place the file there and rebuild
.\build_exe.ps1 -Clean
```

### Customizing for Specific Dispatcher
You can pre-populate credentials in `.env.example`:
```env
# Example: Pre-fill for a specific location
DB_HOST=your-standard-neon-host.us-west-2.aws.neon.tech
DB_NAME=almsdata
# Leave user/password blank for security
DB_USER=
DB_PASSWORD=FILL_THIS_IN
```

### Changing App Name
In `build_desktop_app.spec`, change the `name` parameter:
```python
exe = EXE(
    ...
    name='YourAppName',  # ← Change this
    ...
)
```

---

## Deployment Checklist

Before distributing to dispatchers:

- [ ] Build completes successfully with no errors
- [ ] `dist/ArrowLimousineApp.exe` exists and is executable
- [ ] Test exe launches on your computer
- [ ] Test exe connects to Neon database
- [ ] Test exe shows dashboard with real data
- [ ] Create `dist/ArrowLimousine_Deployment/` folder with all files
- [ ] Include `DISPATCHER_SETUP.md` in the package
- [ ] Include `.env.example` with instructions
- [ ] Create ZIP file: `ArrowLimousine_Installer.zip`
- [ ] Test extraction and exe launch from extracted folder
- [ ] Share ZIP with dispatcher(s)
- [ ] Dispatcher confirms app launches and they can login
- [ ] Dispatcher confirms they can access their data

---

## Version Management

### Updating Existing Installations

When you release a new version:

1. **Build new executable**:
   ```powershell
   .\build_exe.ps1 -Clean
   ```

2. **Create new deployment package**:
   ```powershell
   $folder = ".\dist\ArrowLimousine_Deployment"
   Compress-Archive -Path $folder -DestinationPath "ArrowLimousine_Installer_v1.1.zip" -Force
   ```

3. **Send to dispatcher with update notes**

4. **Dispatcher updates by**:
   - Close current app
   - Backup `.env` file from old installation
   - Delete old folder
   - Extract new ZIP
   - Copy backed-up `.env` into new folder
   - Run new `ArrowLimousineApp.exe`

---

## Support & Help

### For Developers (Building the exe)
- Check PyInstaller docs: https://pyinstaller.org/
- Review `build_desktop_app.spec` for what's included
- Run with debug: `pyinstaller build_desktop_app.spec --debug`

### For Dispatchers (Using the app)
- See `DISPATCHER_SETUP.md` for complete instructions
- Troubleshooting section covers common issues
- Database credentials must be correct (ask office manager)

---

**Last Updated:** January 30, 2026  
**PyInstaller Version:** 6.0+  
**Python Version:** 3.9+  
**Platform:** Windows 10/11 (64-bit)
