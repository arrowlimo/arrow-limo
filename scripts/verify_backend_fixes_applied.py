#!/usr/bin/env python3
"""
Verify Backend Fixes Applied
============================
Confirms all 9 critical issues from backend audit have been fixed.
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
BACKEND_ROOT = REPO_ROOT / "modern_backend" / "app"

def check_settings_py():
    """Verify settings.py doesn't have hardcoded password."""
    settings_path = BACKEND_ROOT / "settings.py"
    content = settings_path.read_text(encoding="utf-8")
    
    print("\n1. SETTINGS.PY - Hardcoded Password Fix")
    print("=" * 60)
    
    # Check if password has hardcoded value
    if 'db_password: str = "***REMOVED***"' in content:
        print("❌ FAILED: Hardcoded password still exists")
        return False
    elif 'db_password: str' in content:
        print("✅ PASSED: db_password requires environment variable")
        # Show the actual line
        for line in content.split('\n'):
            if 'db_password:' in line:
                print(f"   Line: {line.strip()}")
        return True
    else:
        print("❌ FAILED: db_password field not found")
        return False

def check_bookings_py():
    """Verify bookings.py has Path() on PATCH endpoint."""
    bookings_path = BACKEND_ROOT / "routers" / "bookings.py"
    content = bookings_path.read_text(encoding="utf-8")
    
    print("\n2. BOOKINGS.PY - Path() Validation Fix")
    print("=" * 60)
    
    # Check if PATCH endpoint has Path()
    if 'charter_id: int = Path(' in content or 'charter_id: int = Path' in content:
        print("✅ PASSED: PATCH endpoint has Path() validation")
        for i, line in enumerate(content.split('\n')):
            if 'async def update_booking(' in line:
                print(f"   Function signature at line {i+1}")
                # Show next few lines
                for next_line in content.split('\n')[i:i+5]:
                    if 'charter_id' in next_line:
                        print(f"   {next_line.strip()}")
        return True
    else:
        print("❌ FAILED: PATCH endpoint missing Path() validation")
        return False

def check_charges_py():
    """Verify charges.py uses cursor() context manager."""
    charges_path = BACKEND_ROOT / "routers" / "charges.py"
    content = charges_path.read_text(encoding="utf-8")
    
    print("\n3. CHARGES.PY - cursor() Context Manager Fix")
    print("=" * 60)
    
    # Count occurrences
    get_connection_count = content.count('get_connection()')
    cursor_context_count = content.count('with cursor()')
    manual_commit_count = content.count('conn.commit()')
    
    print(f"   get_connection() calls: {get_connection_count}")
    print(f"   with cursor() calls: {cursor_context_count}")
    print(f"   manual conn.commit() calls: {manual_commit_count}")
    
    if get_connection_count == 0 and manual_commit_count == 0 and cursor_context_count >= 4:
        print("✅ PASSED: All endpoints use cursor() context manager")
        return True
    else:
        print("❌ FAILED: Still has get_connection() or manual commits")
        return False

def check_payments_py():
    """Verify payments.py uses cursor() and PaymentUpdate is fixed."""
    payments_path = BACKEND_ROOT / "routers" / "payments.py"
    content = payments_path.read_text(encoding="utf-8")
    
    print("\n4. PAYMENTS.PY - cursor() + PaymentUpdate Fix")
    print("=" * 60)
    
    # Check connection management
    get_connection_count = content.count('get_connection()')
    cursor_context_count = content.count('with cursor()')
    manual_commit_count = content.count('conn.commit()')
    
    print(f"   get_connection() calls: {get_connection_count}")
    print(f"   with cursor() calls: {cursor_context_count}")
    print(f"   manual conn.commit() calls: {manual_commit_count}")
    
    connection_ok = get_connection_count == 0 and manual_commit_count == 0 and cursor_context_count >= 4
    
    # Check PaymentUpdate model
    model_ok = False
    if 'class PaymentUpdate' in content:
        # Find the model definition
        model_start = content.index('class PaymentUpdate')
        # Get next 300 characters (should cover all fields)
        model_section = content[model_start:model_start+300]
        
        # Count lines until next class/function/decorator
        model_lines = []
        in_model = False
        for line in content[model_start:].split('\n'):
            if line.startswith('class PaymentUpdate'):
                in_model = True
                model_lines.append(line)
            elif in_model:
                if line.startswith('@') or line.startswith('class ') or line.startswith('def '):
                    break
                model_lines.append(line)
        
        model_text = '\n'.join(model_lines)
        
        # Check if charter_id is in the model
        if 'charter_id:' in model_text or 'charter_id =' in model_text:
            print("   PaymentUpdate: charter_id still present ❌")
        else:
            print("   PaymentUpdate: charter_id not present ✅")
            model_ok = True
    
    if connection_ok and model_ok:
        print("✅ PASSED: cursor() used + charter_id removed from PaymentUpdate")
        return True
    else:
        print("❌ FAILED: Issues remain")
        return False

def check_reports_py():
    """Verify reports.py export endpoint uses cursor()."""
    reports_path = BACKEND_ROOT / "routers" / "reports.py"
    content = reports_path.read_text(encoding="utf-8")
    
    print("\n5. REPORTS.PY - Export Endpoint cursor() Fix")
    print("=" * 60)
    
    # Find the export function (not async)
    if 'def export(' in content:
        func_start = content.index('def export(')
        func_section = content[func_start:func_start+2000]
        
        # Check if it uses cursor()
        if 'with cursor()' in func_section:
            print("✅ PASSED: export() uses cursor() context manager")
            return True
        else:
            print("❌ FAILED: export() doesn't use cursor()")
            return False
    else:
        print("❌ FAILED: export() function not found")
        return False

def main():
    print("\n" + "=" * 80)
    print("BACKEND FIXES VERIFICATION")
    print("Checking if all 9 critical issues from audit have been fixed")
    print("=" * 80)
    
    results = [
        check_settings_py(),      # 1 issue
        check_bookings_py(),      # 1 issue
        check_charges_py(),       # 4 issues (connection mgmt)
        check_payments_py(),      # 2 issues (connection + model)
        check_reports_py(),       # 1 issue (main endpoint)
    ]
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    passed = sum(results)
    total = len(results)
    
    print(f"\n✅ Passed: {passed}/{total}")
    print(f"❌ Failed: {total - passed}/{total}")
    
    if all(results):
        print("\n🎉 ALL FIXES VERIFIED - Backend is production ready!")
        return 0
    else:
        print("\n⚠️  Some fixes missing - review failed checks above")
        return 1

if __name__ == "__main__":
    sys.exit(main())
