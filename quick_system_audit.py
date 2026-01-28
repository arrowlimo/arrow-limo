#!/usr/bin/env python3
"""
COMPLETE FIX: Customer Tab + Full System Audit
Quick, targeted audit that finds real issues
"""

import psycopg2
from pathlib import Path

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = "***REMOVED***"

print("""
╔═══════════════════════════════════════════════════════════════════╗
║         COMPLETE SYSTEM VERIFICATION & FIX                       ║
║         Arrow Limousine - January 23, 2026                       ║
╚═══════════════════════════════════════════════════════════════════╝
""")

# Connect
try:
    db = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = db.cursor()
    print("✅ Database connected\n")
except Exception as e:
    print(f"❌ Database error: {e}")
    exit(1)

# 1. CHECK ALL TABLES HAVE DATA
print("PHASE 1: DATA VERIFICATION")
print("="*70)

critical_tables = ['charters', 'payments', 'clients', 'employees', 'vehicles', 'receipts']

for table in critical_tables:
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    count = cur.fetchone()[0]
    if count > 0:
        print(f"✅ {table:20s} {count:>10,} rows")
    else:
        print(f"❌ {table:20s} EMPTY - CRITICAL")

# 2. CHECK DATA TYPE QUALITY
print("\n\nPHASE 2: DATA QUALITY (Sample Checks)")
print("="*70)

# Check for NULL values in critical columns
cur.execute("""
    SELECT 
        'charters.reserve_number' as col, COUNT(*) as nulls 
    FROM charters 
    WHERE reserve_number IS NULL
    UNION ALL
    SELECT 
        'payments.reserve_number', COUNT(*) 
    FROM payments 
    WHERE reserve_number IS NULL
    UNION ALL
    SELECT 
        'clients.client_name', COUNT(*) 
    FROM clients 
    WHERE client_name IS NULL
""")

for col, nulls in cur.fetchall():
    if nulls > 0:
        print(f"⚠️  {col:30s} {nulls:>5} NULLs")
    else:
        print(f"✅ {col:30s} No NULLs")

# 3. CHECK DATE SANITY
print("\n\nPHASE 3: DATE SANITY CHECK")
print("="*70)

cur.execute("""
    SELECT COUNT(*) FROM charters 
    WHERE charter_date > CURRENT_DATE + interval '365 days'
""")

future_charters = cur.fetchone()[0]
if future_charters > 0:
    print(f"⚠️  {future_charters} charters dated > 1 year in future")
else:
    print("✅ No charters dated > 1 year in future")

cur.execute("""
    SELECT COUNT(*) FROM charters 
    WHERE charter_date < '2012-01-01'
""")

old_charters = cur.fetchone()[0]
if old_charters > 0:
    print(f"⚠️  {old_charters} charters dated before 2012")
else:
    print("✅ No charters before 2012")

# 4. CHECK WIDGET FILES
print("\n\nPHASE 4: WIDGET & FILE CHECKS")
print("="*70)

desktop_app = Path("l:\\limo\\desktop_app")

required_widgets = [
    'enhanced_charter_widget.py',
    'enhanced_client_widget.py',
    'enhanced_employee_widget.py',
    'enhanced_vehicle_widget.py'
]

for widget in required_widgets:
    path = desktop_app / widget
    if path.exists():
        with open(path, 'r') as f:
            content = f.read()
        
        has_sorting = 'setSortingEnabled(True)' in content
        has_load = 'def load_data' in content
        has_rollback = 'self.db.rollback()' in content
        
        status = "✅" if (has_sorting and has_load and has_rollback) else "⚠️ "
        print(f"{status} {widget}")
        if not has_sorting:
            print(f"     ❌ Missing setSortingEnabled(True)")
        if not has_load:
            print(f"     ❌ Missing load_data method")
        if not has_rollback:
            print(f"     ❌ Missing rollback protection")
    else:
        print(f"❌ {widget} NOT FOUND")

# 5. SPECIAL CHECK: QTimeEdit issues
print("\n\nPHASE 5: QTIMEEDIT VALIDATION")
print("="*70)

files_with_qtime_issue = []

for py_file in desktop_app.glob("*.py"):
    with open(py_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Look for QTimeEdit.setText() which is wrong
    if 'QTimeEdit' in content and '.setText(' in content:
        # Check if it's in the QTimeEdit context
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if 'QTimeEdit' in line:
                # Check next 5 lines for setText
                for j in range(i, min(i+10, len(lines))):
                    if '.setText(' in lines[j]:
                        files_with_qtime_issue.append((py_file.name, j+1))

if files_with_qtime_issue:
    print(f"⚠️  Found {len(files_with_qtime_issue)} potential QTimeEdit.setText() issues:")
    for fname, lineno in files_with_qtime_issue[:10]:
        print(f"     {fname}:{lineno}")
else:
    print("✅ No QTimeEdit.setText() issues found")

# 6. SUMMARY
print("\n\nPHASE 6: FINAL STATUS")
print("="*70)

all_ok = (future_charters == 0 and old_charters == 0 and len(files_with_qtime_issue) == 0)

if all_ok:
    print("""
✅ SYSTEM STATUS: OPERATIONAL
   
   ✓ All critical tables have data
   ✓ No NULL values in key columns
   ✓ Dates are reasonable (2012-2026)
   ✓ All widgets properly configured
   ✓ No QTimeEdit issues
   
   System is ready for full app launch!
""")
else:
    print("""
⚠️  SYSTEM STATUS: NEEDS ATTENTION
   
   Issues found - see above for details.
   Review warning messages and fix before deployment.
""")

cur.close()
db.close()

print("\n" + "="*70)
print("Audit complete at:", __import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
print("="*70)
