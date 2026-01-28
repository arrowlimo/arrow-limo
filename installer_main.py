
"""
Arrow Limo Desktop App - Self-Contained Installer
This script deploys the app to the local machine
"""

import os
import sys
import shutil
import subprocess
import winreg
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk
import threading

class InstallerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Arrow Limo Desktop App - Installer")
        self.root.geometry("600x400")
        self.root.resizable(False, False)
        
        # Machine number
        self.machine_number = tk.StringVar(value="1")
        
        # Create UI
        self.create_widgets()
        
    def create_widgets(self):
        # Header
        header = tk.Label(
            self.root, 
            text="Arrow Limo Desktop App Installer",
            font=("Arial", 16, "bold"),
            bg="#0066cc",
            fg="white",
            pady=10
        )
        header.pack(fill=tk.X)
        
        # Instructions
        instructions = tk.Label(
            self.root,
            text="This installer will set up the Arrow Limo Desktop App on your computer.\n"
                 "The app will connect to the cloud database (Neon) and auto-start on login.",
            wraplength=550,
            justify=tk.LEFT,
            pady=10
        )
        instructions.pack()
        
        # Machine number selection
        machine_frame = tk.Frame(self.root)
        machine_frame.pack(pady=10)
        
        tk.Label(machine_frame, text="Machine Number:", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=5)
        
        machine_spinbox = tk.Spinbox(
            machine_frame,
            from_=1,
            to=6,
            textvariable=self.machine_number,
            width=5,
            font=("Arial", 10)
        )
        machine_spinbox.pack(side=tk.LEFT, padx=5)
        
        tk.Label(machine_frame, text="(1-6)", fg="gray").pack(side=tk.LEFT)
        
        # Progress area
        self.progress_frame = tk.Frame(self.root)
        self.progress_frame.pack(pady=20, fill=tk.BOTH, expand=True)
        
        self.progress_text = tk.Text(
            self.progress_frame,
            height=10,
            width=70,
            font=("Consolas", 9),
            bg="#f0f0f0",
            state=tk.DISABLED
        )
        self.progress_text.pack(padx=10, pady=5)
        
        # Progress bar
        self.progress_bar = ttk.Progressbar(
            self.root,
            mode="indeterminate",
            length=550
        )
        
        # Install button
        self.install_button = tk.Button(
            self.root,
            text="Install Arrow Limo App",
            font=("Arial", 12, "bold"),
            bg="#0066cc",
            fg="white",
            command=self.start_installation,
            width=30,
            height=2
        )
        self.install_button.pack(pady=10)
        
    def log(self, message):
        """Add message to progress log"""
        self.progress_text.config(state=tk.NORMAL)
        self.progress_text.insert(tk.END, message + "\n")
        self.progress_text.see(tk.END)
        self.progress_text.config(state=tk.DISABLED)
        self.root.update()
        
    def start_installation(self):
        """Start installation in background thread"""
        self.install_button.config(state=tk.DISABLED)
        self.progress_bar.pack(pady=5)
        self.progress_bar.start(10)
        
        # Run installation in thread
        thread = threading.Thread(target=self.run_installation)
        thread.daemon = True
        thread.start()
        
    def run_installation(self):
        """Run the actual installation"""
        try:
            machine_num = int(self.machine_number.get())
            
            self.log("╔════════════════════════════════════════════╗")
            self.log("║  Arrow Limo Desktop App - Installation    ║")
            self.log(f"║  Machine #{machine_num}                              ║")
            self.log("╚════════════════════════════════════════════╝")
            self.log("")
            
            # Step 1: Create installation directory
            self.log("Step 1: Creating installation directory...")
            install_dir = Path("C:/ArrowLimoApp")
            install_dir.mkdir(parents=True, exist_ok=True)
            self.log(f"✓ Created: {install_dir}")
            
            # Step 2: Extract bundled files
            self.log("\nStep 2: Extracting application files...")
            
            # Get path to bundled resources (PyInstaller extracts to _MEIPASS)
            if getattr(sys, 'frozen', False):
                bundle_dir = Path(sys._MEIPASS)
            else:
                bundle_dir = Path(__file__).parent
            
            # Copy main.py
            main_py = bundle_dir / "main.py"
            if main_py.exists():
                shutil.copy(main_py, install_dir / "main.py")
                self.log("  ✓ main.py")
            
            # Copy desktop_app folder
            desktop_app_src = bundle_dir / "desktop_app"
            desktop_app_dst = install_dir / "desktop_app"
            if desktop_app_src.exists():
                if desktop_app_dst.exists():
                    shutil.rmtree(desktop_app_dst)
                shutil.copytree(desktop_app_src, desktop_app_dst)
                file_count = len(list(desktop_app_dst.rglob("*.py")))
                self.log(f"  ✓ desktop_app/ ({file_count} files)")
            
            # Copy requirements.txt
            req_file = bundle_dir / "requirements.txt"
            if req_file.exists():
                shutil.copy(req_file, install_dir / "requirements.txt")
                self.log("  ✓ requirements.txt")
            
            # Copy .env.neon to .env
            env_file = bundle_dir / ".env.neon"
            if env_file.exists():
                shutil.copy(env_file, install_dir / ".env")
                self.log("  ✓ .env (Neon credentials)")
            
            # Step 3: Install Python dependencies
            self.log("\nStep 3: Installing Python dependencies...")
            try:
                python_exe = sys.executable
                req_path = install_dir / "requirements.txt"
                
                if req_path.exists():
                    subprocess.run(
                        [python_exe, "-m", "pip", "install", "-r", str(req_path), "--quiet"],
                        check=True,
                        capture_output=True
                    )
                    self.log("  ✓ Dependencies installed")
                else:
                    self.log("  ⚠ requirements.txt not found - skipping")
            except Exception as e:
                self.log(f"  ⚠ Warning: {e}")
            
            # Step 4: Create Task Scheduler auto-start
            self.log("\nStep 4: Setting up auto-start...")
            
            task_name = f"ArrowLimoApp-Machine{machine_num}"
            task_path = "\\ArrowLimo\\"
            
            # Remove existing task if present
            subprocess.run(
                ["schtasks", "/Delete", "/TN", f"{task_path}{task_name}", "/F"],
                capture_output=True
            )
            
            # Create new task
            python_path = sys.executable
            app_script = str(install_dir / "main.py")
            
            task_xml = f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>Arrow Limo Desktop App - Auto-start for Machine {machine_num}</Description>
  </RegistrationInfo>
  <Triggers>
    <LogonTrigger>
      <Enabled>true</Enabled>
    </LogonTrigger>
  </Triggers>
  <Principals>
    <Principal>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>true</RunOnlyIfNetworkAvailable>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <WakeToRun>false</WakeToRun>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <Priority>7</Priority>
  </Settings>
  <Actions>
    <Exec>
      <Command>{python_path}</Command>
      <Arguments>-X utf8 "{app_script}"</Arguments>
      <WorkingDirectory>{install_dir}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>"""
            
            # Write XML to temp file
            temp_xml = install_dir / "task_temp.xml"
            temp_xml.write_text(task_xml, encoding="utf-16")
            
            # Create task
            result = subprocess.run(
                ["schtasks", "/Create", "/TN", f"{task_path}{task_name}", 
                 "/XML", str(temp_xml), "/F"],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                self.log(f"  ✓ Auto-start task created: {task_name}")
            else:
                self.log(f"  ⚠ Task creation failed: {result.stderr}")
            
            # Clean up temp file
            temp_xml.unlink(missing_ok=True)
            
            # Step 5: Create desktop shortcut
            self.log("\nStep 5: Creating desktop shortcut...")
            
            try:
                import win32com.client
                
                desktop = Path.home() / "Desktop"
                shortcut_path = desktop / "Arrow Limo App.lnk"
                
                shell = win32com.client.Dispatch("WScript.Shell")
                shortcut = shell.CreateShortCut(str(shortcut_path))
                shortcut.TargetPath = python_path
                shortcut.Arguments = f'-X utf8 "{app_script}"'
                shortcut.WorkingDirectory = str(install_dir)
                shortcut.Description = f"Arrow Limo Desktop App - Machine {machine_num}"
                shortcut.Save()
                
                self.log(f"  ✓ Desktop shortcut created")
            except Exception as e:
                self.log(f"  ⚠ Shortcut creation failed: {e}")
            
            # Step 6: Test Neon connection
            self.log("\nStep 6: Testing Neon database connection...")
            
            try:
                import psycopg2
                from dotenv import load_dotenv
                
                load_dotenv(install_dir / ".env")
                
                conn = psycopg2.connect(
                    host=os.getenv("DB_HOST"),
                    database=os.getenv("DB_NAME"),
                    user=os.getenv("DB_USER"),
                    password=os.getenv("DB_PASSWORD"),
                    sslmode=os.getenv("DB_SSLMODE", "require")
                )
                
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM public.charters")
                charter_count = cur.fetchone()[0]
                
                self.log(f"  ✓ Connected to Neon database")
                self.log(f"  ✓ Found {charter_count:,} charters")
                
                cur.close()
                conn.close()
            except Exception as e:
                self.log(f"  ⚠ Connection test failed: {e}")
                self.log("  (You may need to check .env credentials)")
            
            # Success
            self.log("\n╔════════════════════════════════════════════╗")
            self.log("║  Installation Complete! ✓                 ║")
            self.log("╚════════════════════════════════════════════╝")
            self.log("")
            self.log(f"Installation directory: {install_dir}")
            self.log(f"Auto-start task: {task_name}")
            self.log("")
            self.log("Next steps:")
            self.log("  1. Log out and log back in")
            self.log("  2. App will start automatically")
            self.log("  3. Or use desktop shortcut to start now")
            
            # Stop progress bar and show completion
            self.progress_bar.stop()
            self.progress_bar.pack_forget()
            
            self.install_button.config(
                text="Installation Complete ✓",
                bg="#00aa00",
                state=tk.DISABLED
            )
            
            messagebox.showinfo(
                "Installation Complete",
                f"Arrow Limo Desktop App installed successfully!\n\n"
                f"Machine #{machine_num}\n"
                f"Location: {install_dir}\n\n"
                f"The app will auto-start on your next login.\n"
                f"Or click the desktop shortcut to start now."
            )
            
        except Exception as e:
            self.progress_bar.stop()
            self.progress_bar.pack_forget()
            self.log(f"\n❌ Installation failed: {e}")
            self.install_button.config(state=tk.NORMAL)
            messagebox.showerror("Installation Error", f"Installation failed:\n{e}")

def main():
    root = tk.Tk()
    app = InstallerGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
