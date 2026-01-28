#!/usr/bin/env python
"""
Batch fix script for dashboard column references
Fixes common column mismatches across all dashboard phase files
"""

import os
import re

FIXES = [
    # Fix 1: driver_id -> employee_id (charters joining employees)
    (r'c\.driver_id = e\.employee_id', 'c.employee_id = e.employee_id'),
    
    # Fix 2: customer_id -> client_id (charters joining clients)
    (r'c\.customer_id', 'c.client_id'),
    (r'cl\.client_id = c\.customer_id', 'cl.client_id = c.client_id'),
    
    # Fix 3: employee_type -> is_chauffeur
    (r"e\.employee_type = 'Driver'", 'e.is_chauffeur = true'),
    (r"WHERE e\.employee_type = 'Driver'", 'WHERE e.is_chauffeur = true'),
    
    # Fix 4: customer_rating -> client_rating
    (r'c\.customer_rating', 'c.client_rating'),
    
    # Fix 5: customer_name -> company_name
    (r'cl\.customer_name', 'cl.company_name'),
    
    # Fix 6: purchase_date doesn't exist (remove it)
    (r'EXTRACT\(YEAR FROM AGE\(CURRENT_DATE, purchase_date\)\)', 'EXTRACT(YEAR FROM current_date) - v.year'),
    (r'ORDER BY purchase_date DESC', 'ORDER BY v.year DESC'),
]

def fix_file(filepath, fixes):
    """Apply fixes to a single file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original = content
        for pattern, replacement in fixes:
            content = re.sub(pattern, replacement, content)
        
        if content != original:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        return False
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False

# Find and fix all dashboard phase files
dashboard_dir = r'l:\limo\desktop_app'
files_to_fix = [
    'dashboards_phase4_5_6.py',  # Already partially fixed
    'dashboards_phase7_8.py',
    'dashboards_phase9.py',
    'dashboards_phase10.py',
    'dashboards_phase11.py',
    'dashboards_phase12.py',
    'dashboards_phase13.py',
    'dashboards_phase2_phase3.py',
]

print("=" * 60)
print("BATCH FIXING DASHBOARD COLUMN REFERENCES")
print("=" * 60)

fixed_count = 0
for filename in files_to_fix:
    filepath = os.path.join(dashboard_dir, filename)
    if os.path.exists(filepath):
        print(f"\n{filename}:")
        if fix_file(filepath, FIXES):
            print(f"  ✅ Fixed")
            fixed_count += 1
        else:
            print(f"  ℹ️  No changes needed")
    else:
        print(f"  ❌ File not found")

print("\n" + "=" * 60)
print(f"✅ Fixed {fixed_count} files")
print("=" * 60)
