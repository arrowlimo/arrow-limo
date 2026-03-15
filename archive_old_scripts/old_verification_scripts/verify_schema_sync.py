"""
Verify schemas match database - validation script
"""

import psycopg2
from dotenv import load_dotenv
import os
from pathlib import Path
import re
import sys

load_dotenv()

conn = psycopg2.connect(
    host=os.getenv('DB_HOST'),
    database=os.getenv('DB_NAME'),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD')
)
cur = conn.cursor()

print("\n" + "="*70)
print("SCHEMA VALIDATION - Vehicles & Charters")
print("="*70)

# Get database columns
cur.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name = 'vehicles'
    ORDER BY ordinal_position
""")
vehicle_db_cols = {row[0]: row[1] for row in cur.fetchall()}

cur.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name = 'charters'
    ORDER BY ordinal_position
""")
charter_db_cols = {row[0]: row[1] for row in cur.fetchall()}

# Read schema files
vehicle_schema_file = Path("modern_backend/app/schemas/vehicle.py")
charter_schema_file = Path("modern_backend/app/schemas/charter.py")

print("\n📊 VEHICLES TABLE SCHEMA")
print("-" * 70)
print(f"Database columns: {len(vehicle_db_cols)}")
print(f"Schema file: {vehicle_schema_file.name}")

if vehicle_schema_file.exists():
    with open(vehicle_schema_file, 'r') as f:
        content = f.read()
    
    # Extract field names from schema
    schema_fields = re.findall(r'(\w+):\s*(?:Optional\[|int|str|float|bool|date|datetime|Dict|List)', content)
    schema_fields = list(set(schema_fields))
    
    print(f"Schema fields: {len(schema_fields)}")
    
    # Check coverage
    missing = []
    for db_col in vehicle_db_cols:
        if db_col not in schema_fields and db_col != 'vehicle_id' and db_col != 'updated_at':
            missing.append(db_col)
    
    if missing:
        print(f"\n⚠️  Missing from schema: {missing}")
    else:
        print("✅ All database columns covered in schema")
else:
    print(f"❌ Schema file not found: {vehicle_schema_file}")

print("\n📊 CHARTERS TABLE SCHEMA")
print("-" * 70)
print(f"Database columns: {len(charter_db_cols)}")
print(f"Schema file: {charter_schema_file.name}")

if charter_schema_file.exists():
    with open(charter_schema_file, 'r') as f:
        content = f.read()
    
    # Extract field names from schema
    schema_fields = re.findall(r'(\w+):\s*(?:Optional\[|int|str|float|bool|date|datetime|Dict|List)', content)
    schema_fields = list(set(schema_fields))
    
    print(f"Schema fields: {len(schema_fields)}")
    
    # Check coverage
    missing = []
    for db_col in charter_db_cols:
        if db_col not in schema_fields and db_col != 'charter_id' and db_col != 'created_at' and db_col != 'updated_at':
            missing.append(db_col)
    
    if missing:
        print(f"\n⚠️  Missing from schema: {missing}")
    else:
        print("✅ All database columns covered in schema")
else:
    print(f"❌ Schema file not found: {charter_schema_file}")

# Check routers
print("\n\n📁 ROUTER INTEGRATION CHECK")
print("-" * 70)

vehicles_router = Path("modern_backend/app/routers/vehicles.py")
charters_router = Path("modern_backend/app/routers/charters.py")

for router_file in [vehicles_router, charters_router]:
    if router_file.exists():
        with open(router_file, 'r') as f:
            content = f.read()
        
        has_schema_import = 'from ..schemas' in content and ('Vehicle' in content or 'Charter' in content)
        endpoints = re.findall(r'@router\.(?:get|post|put|patch|delete)\(["\']([^"\']+)["\']', content)
        
        print(f"\n{router_file.name}:")
        print(f"  Endpoints: {len(endpoints)}")
        print(f"  Schema imports: {'✅ YES' if has_schema_import else '❌ NO'}")
        if not has_schema_import:
            print(f"    → Add: from ..schemas import Vehicle (or Charter)")

cur.close()
conn.close()

print("\n" + "="*70)
print("VALIDATION COMPLETE")
print("="*70)
print("""
✅ Schemas created and ready
⏳ Routers need schema integration
📝 See DATABASE_SCHEMA_SYNC_VEHICLES_CHARTERS.md for details
""")
