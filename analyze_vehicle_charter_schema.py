"""
Analyze VEHICLES and CHARTERS table schemas in detail
Compare with application code expectations
"""

import psycopg2
from dotenv import load_dotenv
import os
from pathlib import Path
import re

load_dotenv()

conn = psycopg2.connect(
    host=os.getenv('DB_HOST'),
    database=os.getenv('DB_NAME'),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD')
)
cur = conn.cursor()

print("\n" + "="*80)
print("DETAILED SCHEMA ANALYSIS: VEHICLES & CHARTERS")
print("="*80)

# Get VEHICLES columns
print("\n📊 VEHICLES TABLE - Complete Column List:")
print("-" * 80)
cur.execute("""
    SELECT column_name, data_type, is_nullable, column_default
    FROM information_schema.columns
    WHERE table_name = 'vehicles'
    ORDER BY ordinal_position
""")
vehicle_cols = cur.fetchall()

print(f"Total Columns: {len(vehicle_cols)}\n")
for i, (col_name, col_type, nullable, default) in enumerate(vehicle_cols, 1):
    null_str = "✓" if nullable == 'YES' else "✗"
    default_str = f" = {default}" if default else ""
    print(f"{i:3d}. {col_name:<35} {col_type:<25} NULL:{null_str}{default_str}")

# Get CHARTERS columns
print("\n\n📊 CHARTERS TABLE - Complete Column List:")
print("-" * 80)
cur.execute("""
    SELECT column_name, data_type, is_nullable, column_default
    FROM information_schema.columns
    WHERE table_name = 'charters'
    ORDER BY ordinal_position
""")
charter_cols = cur.fetchall()

print(f"Total Columns: {len(charter_cols)}\n")
for i, (col_name, col_type, nullable, default) in enumerate(charter_cols, 1):
    null_str = "✓" if nullable == 'YES' else "✗"
    default_str = f" = {default}" if default else ""
    print(f"{i:3d}. {col_name:<35} {col_type:<25} NULL:{null_str}{default_str}")

# Check application models
print("\n\n" + "="*80)
print("APPLICATION CODE CHECK")
print("="*80)

models_path = Path("modern_backend/app/models")
if models_path.exists():
    print(f"\nChecking {models_path}:")
    
    for py_file in sorted(models_path.glob("*.py")):
        with open(py_file, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            if 'vehicles' in content.lower() or 'charters' in content.lower():
                # Count field definitions
                fields = re.findall(r'(\w+):\s*(?:Optional\[|int|str|float|bool|date|datetime)', content)
                print(f"\n  📄 {py_file.name}:")
                print(f"     Fields defined: {len(set(fields))}")
                if 'class Vehicle' in content:
                    print(f"     ✓ Has Vehicle model")
                if 'class Charter' in content:
                    print(f"     ✓ Has Charter model")

schemas_path = Path("modern_backend/app/schemas")
if schemas_path.exists():
    print(f"\nChecking {schemas_path}:")
    
    for py_file in sorted(schemas_path.glob("*.py")):
        with open(py_file, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            if 'vehicles' in content.lower() or 'charters' in content.lower():
                fields = re.findall(r'(\w+):\s*(?:Optional\[|int|str|float|bool|date|datetime)', content)
                print(f"\n  📄 {py_file.name}:")
                print(f"     Fields defined: {len(set(fields))}")

routers_path = Path("modern_backend/app/routers")
if routers_path.exists():
    print(f"\nChecking {routers_path}:")
    
    for py_file in ['vehicles.py', 'charters.py']:
        file_path = routers_path / py_file
        if file_path.exists():
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                endpoints = re.findall(r'@router\.(?:get|post|put|delete)\(["\']([^"\']+)["\']', content)
                print(f"\n  📄 {py_file}:")
                print(f"     Endpoints: {len(endpoints)}")
                for ep in endpoints[:5]:
                    print(f"       • {ep}")
                if len(endpoints) > 5:
                    print(f"       ... and {len(endpoints) - 5} more")

print("\n\n" + "="*80)
print("SUMMARY & NEXT STEPS")
print("="*80)
print("""
To sync application with database changes:

1. Review the column lists above
2. Identify which columns are NEW, MODIFIED, or REMOVED
3. Update models/schemas/routers accordingly

Key files to potentially update:
  ✓ modern_backend/app/models/vehicles.py
  ✓ modern_backend/app/models/charters.py
  ✓ modern_backend/app/schemas/vehicles.py
  ✓ modern_backend/app/schemas/charters.py
  ✓ modern_backend/app/routers/vehicles.py
  ✓ modern_backend/app/routers/charters.py
  ✓ desktop_app/dashboards_phase4_5_6.py (VehicleFleetCostAnalysisWidget, etc.)
  ✓ desktop_app/dashboards_phase7_8.py (CharterManagementDashboardWidget, etc.)
  ✓ frontend/src/views/*.vue (vehicle & charter components)

Please identify the specific column changes and I'll update all code accordingly.
""")

cur.close()
conn.close()
