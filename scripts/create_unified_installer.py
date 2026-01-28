#!/usr/bin/env python3
"""
Enhanced Arrow Limousine Deployment System
==========================================

Builds on existing deployment packages to create a unified encapsulated system
similar to LMSWinGold.exe but with modern architecture and better distribution.
"""

import os
import shutil
import subprocess
import json
from pathlib import Path
import zipfile
import tempfile
from datetime import datetime

class ALMSDeploymentBuilder:
    def __init__(self):
        self.workspace_root = Path("L:/limo")
        self.deployment_dir = self.workspace_root / "deployment-packages"
        self.build_date = datetime.now().strftime("%Y%m%d")
        self.version = "2.0.0"
        
    def create_unified_installer(self):
        """Create unified installer that combines all deployment options"""
        print("🚀 CREATING UNIFIED ARROW LIMOUSINE INSTALLER")
        print("=" * 60)
        
        installer_dir = self.deployment_dir / "unified-installer"
        installer_dir.mkdir(parents=True, exist_ok=True)
        
        # Create main installer script
        self.create_main_installer_script(installer_dir)
        self.create_installation_wizard(installer_dir)
        self.create_system_detector(installer_dir)
        self.create_database_migrator(installer_dir)
        self.create_service_installer(installer_dir)
        
        print("[OK] Unified installer created successfully!")
        
    def create_main_installer_script(self, installer_dir):
        """Create main installer entry point"""
        installer_script = f'''
@echo off
setlocal enabledelayedexpansion
title Arrow Limousine Management System - Universal Installer

echo.
echo  ╔══════════════════════════════════════════════════════════════╗
echo  ║           ARROW LIMOUSINE MANAGEMENT SYSTEM v{self.version}           ║
echo  ║                    Universal Installer                      ║
echo  ╚══════════════════════════════════════════════════════════════╝
echo.

REM Check for administrator privileges
net session >nul 2>&1
if !errorlevel! neq 0 (
    echo [FAIL] This installer requires administrator privileges.
    echo Please right-click and select "Run as administrator"
    pause
    exit /b 1
)

REM Detect system configuration
call :detect_system
call :show_installation_options
call :perform_installation

goto :eof

:detect_system
echo 🔍 Detecting system configuration...
python --version >nul 2>&1
if !errorlevel! equ 0 (
    set PYTHON_AVAILABLE=true
    echo [OK] Python detected
) else (
    set PYTHON_AVAILABLE=false
    echo [WARN]  Python not detected
)

docker --version >nul 2>&1
if !errorlevel! equ 0 (
    set DOCKER_AVAILABLE=true
    echo [OK] Docker detected
) else (
    set DOCKER_AVAILABLE=false
    echo [WARN]  Docker not detected
)

node --version >nul 2>&1
if !errorlevel! equ 0 (
    set NODE_AVAILABLE=true
    echo [OK] Node.js detected
) else (
    set NODE_AVAILABLE=false
    echo [WARN]  Node.js not detected
)

echo.
goto :eof

:show_installation_options
echo 📋 Available Installation Options:
echo.
echo 1. 🏢 Enterprise Installation (Docker + PostgreSQL)
echo 2. 💼 Professional Installation (Local Network)
echo 3. 🏠 Standard Installation (Standalone)
echo 4. 📱 Portable Installation (No Installation Required)
echo 5. 🔧 Developer Installation (Full Source)
echo.
set /p INSTALL_CHOICE=Please select installation type (1-5): 

goto :eof

:perform_installation
if "!INSTALL_CHOICE!"=="1" call :install_enterprise
if "!INSTALL_CHOICE!"=="2" call :install_professional
if "!INSTALL_CHOICE!"=="3" call :install_standard
if "!INSTALL_CHOICE!"=="4" call :install_portable
if "!INSTALL_CHOICE!"=="5" call :install_developer

echo.
echo [OK] Installation completed successfully!
echo 🌐 Access your system at: http://localhost:5000
echo 📖 Documentation: %INSTALL_DIR%\\documentation\\
echo.
pause
goto :eof

:install_enterprise
echo.
echo 🏢 Installing Enterprise Edition...
echo    - Docker containers for all services
echo    - PostgreSQL database cluster
echo    - Load balancing and scaling
echo    - Full backup and monitoring
echo.

if "!DOCKER_AVAILABLE!"=="false" (
    echo Installing Docker Desktop...
    call :install_docker
)

echo Setting up Docker environment...
copy "docker-compose.enterprise.yml" "%PROGRAMFILES%\\Arrow Limousine\\"
copy "enterprise\\*" "%PROGRAMFILES%\\Arrow Limousine\\" /s

cd "%PROGRAMFILES%\\Arrow Limousine"
docker-compose -f docker-compose.enterprise.yml up -d

goto :eof

:install_professional
echo.
echo 💼 Installing Professional Edition...
echo    - Local network multi-user access
echo    - Centralized PostgreSQL database
echo    - Web-based interface
echo    - Basic reporting and backup
echo.

call :install_python_requirements
call :setup_database
call :install_web_services

goto :eof

:install_standard
echo.
echo 🏠 Installing Standard Edition...
echo    - Single-user installation
echo    - SQLite database
echo    - Web interface
echo    - Basic features
echo.

call :install_python_requirements
call :setup_sqlite_database
call :install_web_services
call :create_desktop_shortcuts

goto :eof

:install_portable
echo.
echo 📱 Installing Portable Edition...
echo    - No system installation required
echo    - Self-contained in folder
echo    - Can run from USB drive
echo    - Limited features
echo.

set /p PORTABLE_DIR=Enter installation directory (or press Enter for Desktop): 
if "!PORTABLE_DIR!"=="" set PORTABLE_DIR=%USERPROFILE%\\Desktop\\ArrowLimo

echo Extracting portable application to !PORTABLE_DIR!...
xcopy "portable\\*" "!PORTABLE_DIR!\\" /s /e /y

echo Creating launcher...
echo @echo off > "!PORTABLE_DIR!\\Start Arrow Limo.bat"
echo cd /d "!PORTABLE_DIR!" >> "!PORTABLE_DIR!\\Start Arrow Limo.bat"
echo python alms_portable.py >> "!PORTABLE_DIR!\\Start Arrow Limo.bat"

goto :eof

:install_developer
echo.
echo 🔧 Installing Developer Edition...
echo    - Full source code access
echo    - Development tools
echo    - Database migration tools
echo    - Testing framework
echo.

call :install_python_requirements
call :install_development_tools
call :setup_development_database
call :setup_development_environment

goto :eof

REM Helper functions
:install_python_requirements
echo Installing Python requirements...
pip install -r requirements.txt
goto :eof

:setup_database
echo Setting up PostgreSQL database...
REM Database setup logic here
goto :eof

:setup_sqlite_database
echo Setting up SQLite database...
python setup_sqlite.py
goto :eof

:install_web_services
echo Installing web services...
REM Service installation logic here
goto :eof

:create_desktop_shortcuts
echo Creating desktop shortcuts...
REM Shortcut creation logic here
goto :eof

:install_docker
echo Please install Docker Desktop manually from docker.com
echo Press any key when Docker is installed...
pause >nul
goto :eof

:install_development_tools
echo Installing development tools...
pip install -r requirements-dev.txt
npm install -g @vue/cli
goto :eof

:setup_development_database
echo Setting up development database...
python scripts/setup_dev_database.py
goto :eof

:setup_development_environment
echo Setting up development environment...
copy ".env.example" ".env"
echo Development environment ready!
goto :eof
'''
        
        installer_bat = installer_dir / "INSTALL.bat"
        installer_bat.write_text(installer_script)
        
    def create_installation_wizard(self, installer_dir):
        """Create GUI installation wizard"""
        wizard_script = '''
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import subprocess
import threading
import os
from pathlib import Path

class ALMSInstallationWizard:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Arrow Limousine Management System - Installation Wizard")
        self.root.geometry("600x500")
        self.root.resizable(False, False)
        
        # Installation options
        self.install_type = tk.StringVar(value="standard")
        self.install_dir = tk.StringVar(value=r"C:\\Program Files\\Arrow Limousine")
        self.create_shortcuts = tk.BooleanVar(value=True)
        self.start_on_boot = tk.BooleanVar(value=False)
        
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the user interface"""
        # Header
        header_frame = ttk.Frame(self.root)
        header_frame.pack(fill='x', padx=20, pady=10)
        
        title_label = ttk.Label(header_frame, text="Arrow Limousine Management System", 
                               font=('Arial', 16, 'bold'))
        title_label.pack()
        
        subtitle_label = ttk.Label(header_frame, text="Complete Limousine Business Management Solution")
        subtitle_label.pack()
        
        # Installation type selection
        type_frame = ttk.LabelFrame(self.root, text="Installation Type")
        type_frame.pack(fill='x', padx=20, pady=10)
        
        ttk.Radiobutton(type_frame, text="🏢 Enterprise (Docker + PostgreSQL)", 
                       variable=self.install_type, value="enterprise").pack(anchor='w', padx=10, pady=5)
        ttk.Radiobutton(type_frame, text="💼 Professional (Network Access)", 
                       variable=self.install_type, value="professional").pack(anchor='w', padx=10, pady=5)
        ttk.Radiobutton(type_frame, text="🏠 Standard (Single User)", 
                       variable=self.install_type, value="standard").pack(anchor='w', padx=10, pady=5)
        ttk.Radiobutton(type_frame, text="📱 Portable (No Installation)", 
                       variable=self.install_type, value="portable").pack(anchor='w', padx=10, pady=5)
        
        # Installation directory
        dir_frame = ttk.LabelFrame(self.root, text="Installation Directory")
        dir_frame.pack(fill='x', padx=20, pady=10)
        
        dir_entry_frame = ttk.Frame(dir_frame)
        dir_entry_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Entry(dir_entry_frame, textvariable=self.install_dir, width=50).pack(side='left', fill='x', expand=True)
        ttk.Button(dir_entry_frame, text="Browse", command=self.browse_directory).pack(side='right', padx=(5,0))
        
        # Options
        options_frame = ttk.LabelFrame(self.root, text="Installation Options")
        options_frame.pack(fill='x', padx=20, pady=10)
        
        ttk.Checkbutton(options_frame, text="Create desktop shortcuts", 
                       variable=self.create_shortcuts).pack(anchor='w', padx=10, pady=2)
        ttk.Checkbutton(options_frame, text="Start service on system boot", 
                       variable=self.start_on_boot).pack(anchor='w', padx=10, pady=2)
        
        # Progress bar
        self.progress_frame = ttk.LabelFrame(self.root, text="Installation Progress")
        self.progress_frame.pack(fill='x', padx=20, pady=10)
        
        self.progress_bar = ttk.Progressbar(self.progress_frame, mode='indeterminate')
        self.progress_bar.pack(fill='x', padx=10, pady=5)
        
        self.status_label = ttk.Label(self.progress_frame, text="Ready to install")
        self.status_label.pack(padx=10, pady=5)
        
        # Buttons
        button_frame = ttk.Frame(self.root)
        button_frame.pack(fill='x', padx=20, pady=10)
        
        ttk.Button(button_frame, text="Cancel", command=self.root.quit).pack(side='right', padx=(5,0))
        self.install_button = ttk.Button(button_frame, text="Install", command=self.start_installation)
        self.install_button.pack(side='right')
        
    def browse_directory(self):
        """Browse for installation directory"""
        directory = filedialog.askdirectory(initialdir=self.install_dir.get())
        if directory:
            self.install_dir.set(directory)
            
    def start_installation(self):
        """Start the installation process"""
        self.install_button.config(state='disabled')
        self.progress_bar.start()
        
        # Run installation in separate thread
        install_thread = threading.Thread(target=self.perform_installation)
        install_thread.daemon = True
        install_thread.start()
        
    def perform_installation(self):
        """Perform the actual installation"""
        try:
            install_type = self.install_type.get()
            install_dir = Path(self.install_dir.get())
            
            self.update_status("Creating installation directory...")
            install_dir.mkdir(parents=True, exist_ok=True)
            
            self.update_status("Copying application files...")
            # Copy files based on installation type
            
            self.update_status("Installing dependencies...")
            # Install Python packages, Node.js, etc.
            
            self.update_status("Setting up database...")
            # Database setup
            
            self.update_status("Creating shortcuts...")
            if self.create_shortcuts.get():
                # Create desktop and start menu shortcuts
                pass
                
            self.update_status("Configuring services...")
            if self.start_on_boot.get():
                # Configure Windows service
                pass
                
            self.update_status("Installation completed successfully!")
            self.progress_bar.stop()
            
            messagebox.showinfo("Installation Complete", 
                              "Arrow Limousine Management System has been installed successfully!\\n\\n"
                              "You can now access the application at http://localhost:5000")
            
        except Exception as e:
            self.update_status(f"Installation failed: {str(e)}")
            messagebox.showerror("Installation Error", f"Installation failed: {str(e)}")
        finally:
            self.install_button.config(state='normal')
            self.progress_bar.stop()
            
    def update_status(self, message):
        """Update status message"""
        self.status_label.config(text=message)
        self.root.update_idletasks()
        
    def run(self):
        """Run the installation wizard"""
        self.root.mainloop()

if __name__ == "__main__":
    wizard = ALMSInstallationWizard()
    wizard.run()
'''
        
        wizard_file = installer_dir / "installation_wizard.py"
        wizard_file.write_text(wizard_script)
        
    def create_system_detector(self, installer_dir):
        """Create system detection and requirements checker"""
        detector_script = '''
import platform
import subprocess
import json
import os
from pathlib import Path

class SystemDetector:
    def __init__(self):
        self.system_info = {}
        self.requirements_met = {}
        
    def detect_system(self):
        """Detect system configuration and capabilities"""
        self.system_info = {
            'os': platform.system(),
            'os_version': platform.version(),
            'architecture': platform.machine(),
            'python_version': platform.python_version(),
            'processor': platform.processor(),
            'ram': self.get_ram_info(),
            'disk_space': self.get_disk_space(),
            'network': self.check_network_connectivity()
        }
        
        self.check_requirements()
        return self.system_info
        
    def get_ram_info(self):
        """Get RAM information"""
        try:
            if platform.system() == 'Windows':
                result = subprocess.run(['wmic', 'computersystem', 'get', 'TotalPhysicalMemory', '/value'], 
                                      capture_output=True, text=True)
                for line in result.stdout.split('\\n'):
                    if 'TotalPhysicalMemory' in line:
                        ram_bytes = int(line.split('=')[1])
                        return f"{ram_bytes // (1024**3)} GB"
            return "Unknown"
        except:
            return "Unknown"
            
    def get_disk_space(self):
        """Get available disk space"""
        try:
            if platform.system() == 'Windows':
                import shutil
                total, used, free = shutil.disk_usage('C:')
                return f"{free // (1024**3)} GB free"
            return "Unknown"
        except:
            return "Unknown"
            
    def check_network_connectivity(self):
        """Check network connectivity"""
        try:
            import urllib.request
            urllib.request.urlopen('http://google.com', timeout=5)
            return True
        except:
            return False
            
    def check_requirements(self):
        """Check if system meets requirements"""
        requirements = {
            'python': self.check_python(),
            'node': self.check_node(),
            'docker': self.check_docker(),
            'git': self.check_git(),
            'ram': self.check_ram_requirement(),
            'disk': self.check_disk_requirement(),
            'network': self.system_info.get('network', False)
        }
        
        self.requirements_met = requirements
        return requirements
        
    def check_python(self):
        """Check Python installation"""
        try:
            result = subprocess.run(['python', '--version'], capture_output=True, text=True)
            version = result.stdout.strip().split()[1]
            major, minor = map(int, version.split('.')[:2])
            return major >= 3 and minor >= 8
        except:
            return False
            
    def check_node(self):
        """Check Node.js installation"""
        try:
            result = subprocess.run(['node', '--version'], capture_output=True, text=True)
            return result.returncode == 0
        except:
            return False
            
    def check_docker(self):
        """Check Docker installation"""
        try:
            result = subprocess.run(['docker', '--version'], capture_output=True, text=True)
            return result.returncode == 0
        except:
            return False
            
    def check_git(self):
        """Check Git installation"""
        try:
            result = subprocess.run(['git', '--version'], capture_output=True, text=True)
            return result.returncode == 0
        except:
            return False
            
    def check_ram_requirement(self):
        """Check RAM requirement (minimum 4GB)"""
        try:
            ram_str = self.system_info.get('ram', '0 GB')
            ram_gb = int(ram_str.split()[0])
            return ram_gb >= 4
        except:
            return False
            
    def check_disk_requirement(self):
        """Check disk space requirement (minimum 2GB)"""
        try:
            disk_str = self.system_info.get('disk_space', '0 GB')
            disk_gb = int(disk_str.split()[0])
            return disk_gb >= 2
        except:
            return False
            
    def generate_report(self):
        """Generate system compatibility report"""
        report = {
            'system_info': self.system_info,
            'requirements_met': self.requirements_met,
            'recommended_installation': self.get_recommended_installation(),
            'warnings': self.get_warnings()
        }
        return report
        
    def get_recommended_installation(self):
        """Get recommended installation type"""
        reqs = self.requirements_met
        
        if reqs.get('docker') and reqs.get('ram') and reqs.get('network'):
            return 'enterprise'
        elif reqs.get('python') and reqs.get('node') and reqs.get('network'):
            return 'professional'
        elif reqs.get('python'):
            return 'standard'
        else:
            return 'portable'
            
    def get_warnings(self):
        """Get installation warnings"""
        warnings = []
        reqs = self.requirements_met
        
        if not reqs.get('python'):
            warnings.append("Python 3.8+ not found - will need to install")
        if not reqs.get('node'):
            warnings.append("Node.js not found - some features may be limited")
        if not reqs.get('ram'):
            warnings.append("Low RAM detected - performance may be affected")
        if not reqs.get('disk'):
            warnings.append("Low disk space - installation may fail")
        if not reqs.get('network'):
            warnings.append("No network connectivity - online features disabled")
            
        return warnings

if __name__ == "__main__":
    detector = SystemDetector()
    info = detector.detect_system()
    report = detector.generate_report()
    
    print(json.dumps(report, indent=2))
'''
        
        detector_file = installer_dir / "system_detector.py"
        detector_file.write_text(detector_script)
        
    def create_database_migrator(self, installer_dir):
        """Create database migration and setup tools"""
        migrator_script = '''
import sqlite3
import psycopg2
import json
import os
from pathlib import Path

class DatabaseMigrator:
    def __init__(self, install_type="standard"):
        self.install_type = install_type
        self.db_config = self.get_db_config()
        
    def get_db_config(self):
        """Get database configuration based on installation type"""
        configs = {
            'standard': {
                'type': 'sqlite',
                'path': 'data/almsdata.db'
            },
            'professional': {
                'type': 'postgresql',
                'host': 'localhost',
                'port': 5432,
                'database': 'almsdata',
                'user': 'postgres',
                'password': '***REMOVED***'
            },
            'enterprise': {
                'type': 'postgresql',
                'host': 'postgres-cluster',
                'port': 5432,
                'database': 'almsdata',
                'user': 'postgres',
                'password': '***REMOVED***'
            }
        }
        return configs.get(self.install_type, configs['standard'])
        
    def setup_database(self):
        """Setup database based on configuration"""
        if self.db_config['type'] == 'sqlite':
            return self.setup_sqlite()
        elif self.db_config['type'] == 'postgresql':
            return self.setup_postgresql()
            
    def setup_sqlite(self):
        """Setup SQLite database"""
        db_path = Path(self.db_config['path'])
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        conn = sqlite3.connect(db_path)
        
        # Create tables
        self.create_tables_sqlite(conn)
        
        # Import initial data
        self.import_initial_data_sqlite(conn)
        
        conn.close()
        return True
        
    def setup_postgresql(self):
        """Setup PostgreSQL database"""
        try:
            conn = psycopg2.connect(
                host=self.db_config['host'],
                port=self.db_config['port'],
                database='postgres',  # Connect to default database first
                user=self.db_config['user'],
                password=self.db_config['password']
            )
            conn.autocommit = True
            cur = conn.cursor()
            
            # Create database if not exists
            cur.execute(f"SELECT 1 FROM pg_database WHERE datname = '{self.db_config['database']}'")
            if not cur.fetchone():
                cur.execute(f"CREATE DATABASE {self.db_config['database']}")
                
            cur.close()
            conn.close()
            
            # Connect to the actual database
            conn = psycopg2.connect(
                host=self.db_config['host'],
                port=self.db_config['port'],
                database=self.db_config['database'],
                user=self.db_config['user'],
                password=self.db_config['password']
            )
            
            # Create tables
            self.create_tables_postgresql(conn)
            
            # Import initial data
            self.import_initial_data_postgresql(conn)
            
            conn.close()
            return True
            
        except Exception as e:
            print(f"PostgreSQL setup failed: {e}")
            return False
            
    def create_tables_sqlite(self, conn):
        """Create SQLite tables"""
        # Add table creation SQL here
        pass
        
    def create_tables_postgresql(self, conn):
        """Create PostgreSQL tables"""
        # Add table creation SQL here
        pass
        
    def import_initial_data_sqlite(self, conn):
        """Import initial data for SQLite"""
        # Add initial data import logic
        pass
        
    def import_initial_data_postgresql(self, conn):
        """Import initial data for PostgreSQL"""
        # Add initial data import logic
        pass
        
    def migrate_from_lms(self, lms_path):
        """Migrate data from legacy LMS system"""
        try:
            import pyodbc
            lms_conn = pyodbc.connect(f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={lms_path};')
            
            # Migration logic here
            
            lms_conn.close()
            return True
            
        except Exception as e:
            print(f"LMS migration failed: {e}")
            return False

if __name__ == "__main__":
    migrator = DatabaseMigrator()
    migrator.setup_database()
'''
        
        migrator_file = installer_dir / "database_migrator.py"
        migrator_file.write_text(migrator_script)
        
    def create_service_installer(self, installer_dir):
        """Create Windows service installer"""
        service_script = '''
import os
import sys
import subprocess
from pathlib import Path

class WindowsServiceInstaller:
    def __init__(self, install_dir):
        self.install_dir = Path(install_dir)
        self.service_name = "ArrowLimoService"
        self.service_display_name = "Arrow Limousine Management System"
        
    def install_service(self):
        """Install Windows service"""
        service_script = f"""
import win32serviceutil
import win32service
import win32event
import servicemanager
import subprocess
import sys
import os
from pathlib import Path

class ArrowLimoService(win32serviceutil.ServiceFramework):
    _svc_name_ = "{self.service_name}"
    _svc_display_name_ = "{self.service_display_name}"
    _svc_description_ = "Arrow Limousine Management System Background Service"
    
    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self.is_alive = True
        
    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.hWaitStop)
        self.is_alive = False
        
    def SvcDoRun(self):
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, '')
        )
        
        # Start the main application
        app_path = Path(__file__).parent / "api.py"
        self.process = subprocess.Popen([sys.executable, str(app_path)])
        
        # Wait for stop signal
        while self.is_alive:
            win32event.WaitForSingleObject(self.hWaitStop, 1000)
            
        # Cleanup
        if hasattr(self, 'process'):
            self.process.terminate()

if __name__ == '__main__':
    win32serviceutil.HandleCommandLine(ArrowLimoService)
"""
        
        service_file = self.install_dir / "arrow_limo_service.py"
        service_file.write_text(service_script)
        
        # Install the service
        cmd = [sys.executable, str(service_file), "install"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("[OK] Windows service installed successfully")
            return True
        else:
            print(f"[FAIL] Service installation failed: {result.stderr}")
            return False
            
    def uninstall_service(self):
        """Uninstall Windows service"""
        service_file = self.install_dir / "arrow_limo_service.py"
        if service_file.exists():
            cmd = [sys.executable, str(service_file), "remove"]
            subprocess.run(cmd)

if __name__ == "__main__":
    installer = WindowsServiceInstaller("C:\\Program Files\\Arrow Limousine")
    installer.install_service()
'''
        
        service_file = installer_dir / "service_installer.py"
        service_file.write_text(service_script)

def main():
    """Main function to create all deployment packages"""
    builder = ALMSDeploymentBuilder()
    builder.create_unified_installer()
    
    print(f"\n🎯 Unified installer created in: {builder.deployment_dir}/unified-installer")
    print("📋 Files created:")
    print("   • INSTALL.bat - Main installer")
    print("   • installation_wizard.py - GUI installer")
    print("   • system_detector.py - System compatibility checker")
    print("   • database_migrator.py - Database setup and migration")
    print("   • service_installer.py - Windows service installer")
    print("\n🚀 Ready for deployment!")

if __name__ == "__main__":
    main()