#!/usr/bin/env python3
"""
Try to insert ALL batch_deposit_allocations and catch actual constraint errors.
"""

import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()

conn = psycopg2.connect(
    host=os.getenv("DB_HOST", "localhost"),
    database=os.getenv("DB_NAME", "almsdata"),
    user=os.getenv("DB_USER", "postgres"),
    password=os.getenv("DB_PASSWORD", "***REDACTED***")
)

cur = conn.cursor()

print("Attempting INSERT of ALL batch_deposit_allocations...")

try:
    cur.execute("""
        INSERT INTO charter_payments (charter_id, client_name, charter_date, payment_date, amount, payment_method, source, payment_key, imported_at)
        SELECT 
            bda.reserve_number,
            c.client_display_name,
            c.charter_date,
            COALESCE(c.charter_date, CURRENT_DATE),
            bda.allocation_amount,
            'credit_card',
            'batch_deposit_allocation',
            'BDA_' || bda.allocation_id,
            NOW()
        FROM batch_deposit_allocations bda
        JOIN charters c ON c.reserve_number = bda.reserve_number
    """)
    
    print(f"✅ Success! Inserted {cur.rowcount:,} rows")
    conn.commit()
    
except psycopg2.errors.UniqueViolation as e:
    print(f"\n❌ UniqueViolation: {e}")
    print(f"\nThis error occurs when trying to insert duplicate (payment_id, charter_id, payment_date, amount)")
    print(f"Because payment_id is NULL for batch_deposit_allocations, duplicate keys are likely.")
    
    # Check how many would be blocked
    cur.execute("""
        SELECT COUNT(*) FROM (
            SELECT 
                bda.reserve_number,
                c.client_display_name,
                c.charter_date,
                COALESCE(c.charter_date, CURRENT_DATE),
                bda.allocation_amount
            FROM batch_deposit_allocations bda
            JOIN charters c ON c.reserve_number = bda.reserve_number
        ) AS temp
    """)
    expected = cur.fetchone()[0]
    print(f"\nExpected to insert: {expected:,}")
    print(f"Actually inserted: {cur.rowcount:,}")
    
    conn.rollback()

except Exception as e:
    print(f"❌ Error: {type(e).__name__}: {e}")
    conn.rollback()

cur.close()
conn.close()
