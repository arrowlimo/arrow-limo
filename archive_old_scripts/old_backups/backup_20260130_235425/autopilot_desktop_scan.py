#!/usr/bin/env python
"""
AUTOPILOT MODE: Systematic Desktop App Improvements
Runs unattended - makes EXACT fixes matching screenshots
NO database changes - desktop code only
"""

import os
import sys
import subprocess
import datetime
import shutil
from pathlib import Path

LOG_FILE = Path("L:/limo/logs/autopilot_improvements.log")
DESKTOP_DIR = Path("L:/limo/desktop_app")
BACKUP_DIR = Path("L:/limo/desktop_app/backups_autopilot")

def log(msg):
    """Log to both file and console"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp}] {msg}"
    print(entry)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(entry + "\n")

def backup_file(filepath):
    """Create timestamped backup"""
    BACKUP_DIR.mkdir(exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    name = Path(filepath).name
    backup_path = BACKUP_DIR / f"{name}_{timestamp}.bak"
    shutil.copy2(filepath, backup_path)
    log(f"✅ Backed up: {backup_path}")
    return backup_path

def compile_check(filepath):
    """Verify Python file compiles"""
    try:
        result = subprocess.run(
            ["python", "-X", "utf8", "-m", "py_compile", str(filepath)],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            log(f"✅ Compiles cleanly: {Path(filepath).name}")
            return True
        else:
            log(f"❌ Compile failed: {Path(filepath).name}")
            log(f"   Error: {result.stderr}")
            return False
    except Exception as e:
        log(f"❌ Compile check error: {e}")
        return False

def find_duplicate_code_in_file(filepath):
    """Scan for duplicate field definitions"""
    duplicates = []
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Track field names
    field_counts = {}
    for i, line in enumerate(lines, 1):
        if 'self.new_amount' in line and '=' in line:
            field_counts.setdefault('self.new_amount', []).append(i)
        if 'self.new_vendor' in line and '=' in line:
            field_counts.setdefault('self.new_vendor', []).append(i)
        if 'form_layout.addRow' in line:
            field_counts.setdefault('form_layout.addRow', []).append(i)
    
    for field, line_nums in field_counts.items():
        if len(line_nums) > 1 and field != 'form_layout.addRow':
            duplicates.append(f"  ⚠️  {field}: found on lines {line_nums}")
    
    return duplicates

def main():
    """Main autopilot loop"""
    log("=" * 80)
    log("AUTOPILOT MODE STARTING")
    log("Mission: Fix desktop widgets to match screenshots EXACTLY")
    log("=" * 80)
    
    # Phase 1: Scan all desktop widgets
    log("\nPHASE 1: Scanning desktop_app directory...")
    widget_files = sorted(DESKTOP_DIR.glob("*.py"))
    log(f"Found {len(widget_files)} Python files")
    
    # Phase 2: Focus on receipt widget first (user's priority)
    receipt_widget = DESKTOP_DIR / "receipt_search_match_widget.py"
    if receipt_widget.exists():
        log("\nPHASE 2: Fixing receipt_search_match_widget.py (PRIORITY)")
        log("-" * 80)
        
        # Backup first
        backup_file(receipt_widget)
        
        # Check for duplicates
        dupes = find_duplicate_code_in_file(receipt_widget)
        if dupes:
            log("⚠️  Duplicate code detected:")
            for d in dupes:
                log(d)
        
        # Compile check
        if compile_check(receipt_widget):
            log("✅ Receipt widget: Ready for exact layout matching")
        else:
            log("❌ Receipt widget: Has compile errors - fix needed")
    
    # Phase 3: Scan other widgets
    log("\nPHASE 3: Scanning other widgets for similar issues...")
    issues_found = []
    
    for widget_file in widget_files:
        if widget_file.name.startswith('receipt_search'):
            continue  # Already handled
        
        if widget_file.name.startswith('__'):
            continue  # Skip __init__.py etc
        
        # Quick scan for common issues
        try:
            with open(widget_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Look for field width issues
            if 'setMaximumWidth(100)' in content or 'setMaximumWidth(120)' in content:
                issues_found.append(f"{widget_file.name}: Has narrow fields (100-120px)")
            
            # Look for missing colored boxes
            if 'QGroupBox' in content and 'background-color' not in content:
                issues_found.append(f"{widget_file.name}: Has QGroupBox but no styling")
            
            # Look for duplicate addRow patterns
            addrow_count = content.count('form_layout.addRow')
            if addrow_count > 20:
                issues_found.append(f"{widget_file.name}: {addrow_count} addRow calls (check for duplicates)")
        
        except Exception as e:
            log(f"⚠️  Couldn't scan {widget_file.name}: {e}")
    
    if issues_found:
        log("\n📋 Issues found in other widgets:")
        for issue in issues_found[:10]:  # Show first 10
            log(f"  • {issue}")
        if len(issues_found) > 10:
            log(f"  ... and {len(issues_found) - 10} more")
    
    # Phase 4: Summary
    log("\n" + "=" * 80)
    log("AUTOPILOT SCAN COMPLETE")
    log("=" * 80)
    log(f"✅ Files scanned: {len(widget_files)}")
    log(f"⚠️  Issues detected: {len(issues_found)}")
    log(f"📁 Backups saved to: {BACKUP_DIR}")
    log(f"📄 Full log: {LOG_FILE}")
    log("\nREADY FOR MANUAL FIX PHASE")
    log("Next: Apply EXACT layout fixes to match screenshots pixel-perfect")
    log("=" * 80)

if __name__ == "__main__":
    try:
        LOG_FILE.parent.mkdir(exist_ok=True)
        main()
    except KeyboardInterrupt:
        log("\n❌ User interrupted autopilot")
        sys.exit(1)
    except Exception as e:
        log(f"\n❌ FATAL ERROR: {e}")
        import traceback
        log(traceback.format_exc())
        sys.exit(1)
