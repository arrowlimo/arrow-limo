#!/usr/bin/env python3
"""Create run_type_default_charges table for storing default charges by run type."""
import psycopg2
from dotenv import load_dotenv
import os
import sys

load_dotenv()

host = "localhost"
db_name = os.getenv("LOCAL_DB_NAME", "almsdata")
db_user = os.getenv("LOCAL_DB_USER", "alms")
db_password = os.getenv("LOCAL_DB_PASSWORD") or os.getenv("DB_PASSWORD")

try:
    conn = psycopg2.connect(host=host, database=db_name, user=db_user, password=db_password)
except Exception as e:
    print(f"❌ Connection failed: {e}")
    sys.exit(1)

cur = conn.cursor()

# Create the table
create_sql = """
CREATE TABLE IF NOT EXISTS run_type_default_charges (
    run_type_id INTEGER NOT NULL,
    charge_description VARCHAR(255) NOT NULL,
    charge_type VARCHAR(50),
    amount NUMERIC(12, 2),
    calc_type VARCHAR(50),
    value NUMERIC(12, 2),
    is_taxable BOOLEAN DEFAULT true,
    sequence INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (run_type_id, charge_description)
);
"""

try:
    cur.execute(create_sql)
    conn.commit()
    print("✅ run_type_default_charges table created successfully")
except Exception as e:
    conn.rollback()
    print(f"❌ Error creating table: {e}")
    sys.exit(1)

# Now populate with some common run type default charges
# First, let's see what run types exist
cur.execute("""
    SELECT run_type_id, run_type_name 
    FROM charter_run_types 
    ORDER BY run_type_id
""")

run_types = cur.fetchall()
print(f"\nFound {len(run_types)} run types:")
for rt_id, rt_name in run_types:
    print(f"  {rt_id}: {rt_name}")

# Insert default charges for each run type
# Standard charges for most runs
common_charges = [
    ("Gratuity", "other", None, "Percent", 18.0, True, 10),
]

# Airport-specific charges
airport_charges = [
    ("Airport Handling", "other", None, "Fixed", 0.0, True, 5),
]

for rt_id, rt_name in run_types:
    rt_name_lower = rt_name.lower()
    charges_to_add = list(common_charges)
    
    # Add airport charges if applicable
    if "airport" in rt_name_lower:
        charges_to_add.extend(airport_charges)
    
    for desc, ctype, amount, calc_type, value, taxable, seq in charges_to_add:
        try:
            cur.execute("""
                INSERT INTO run_type_default_charges 
                (run_type_id, charge_description, charge_type, amount, calc_type, value, is_taxable, sequence)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (run_type_id, charge_description) DO UPDATE SET
                    calc_type = EXCLUDED.calc_type,
                    value = EXCLUDED.value,
                    is_taxable = EXCLUDED.is_taxable,
                    sequence = EXCLUDED.sequence,
                    updated_at = CURRENT_TIMESTAMP
            """, (rt_id, desc, ctype, amount, calc_type, value, taxable, seq))
        except Exception as e:
            print(f"  Warning: Could not insert {desc} for run type {rt_id}: {e}")

conn.commit()

# Show what was created
cur.execute("""
    SELECT COUNT(*) FROM run_type_default_charges
""")
count = cur.fetchone()[0]
print(f"\n✅ Inserted {count} default charge entries")

# Show sample
cur.execute("""
    SELECT rt.run_type_name, rtdc.charge_description, rtdc.calc_type, rtdc.value
    FROM run_type_default_charges rtdc
    JOIN charter_run_types rt ON rt.run_type_id = rtdc.run_type_id
    ORDER BY rtdc.run_type_id, rtdc.sequence
    LIMIT 10
""")
print("\nSample charges:")
for rt_name, desc, calc, value in cur.fetchall():
    print(f"  {rt_name}: {desc} ({calc} {value})")

cur.close()
conn.close()
