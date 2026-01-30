#!/usr/bin/env python3
"""
Debug batch_deposit_allocations migration with detailed error handling.
"""

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import os
from datetime import datetime

load_dotenv()

conn = psycopg2.connect(
    host=os.getenv("DB_HOST", "localhost"),
    database=os.getenv("DB_NAME", "almsdata"),
    user=os.getenv("DB_USER", "postgres"),
    password=os.getenv("DB_PASSWORD", "***REMOVED***"),
    cursor_factory=RealDictCursor
)

cur = conn.cursor()

print("="*100)
print("DEBUG BATCH_DEPOSIT_ALLOCATIONS MIGRATION")
print("="*100)

# First, let's count what we're trying to insert
cur.execute("""
    SELECT COUNT(*) as count
    FROM batch_deposit_allocations bda
    JOIN charters c ON c.reserve_number = bda.reserve_number
""")
expected = cur.fetchone()['count']
print(f"\nExpected to insert: {expected:,} rows")

# Try to insert with detailed error handling
try:
    print("\nAttempting INSERT...")
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
    
    inserted = cur.rowcount
    print(f"Inserted: {inserted:,} rows")
    
    if inserted < expected:
        print(f"\n⚠️  Only {inserted:,}/{expected:,} rows inserted!")
        print("Checking for errors...")
        
        # Check for unique constraint violations
        cur.execute("""
            SELECT charter_id, payment_date, amount, COUNT(*) as count
            FROM charter_payments
            WHERE source = 'batch_deposit_allocation'
            GROUP BY charter_id, payment_date, amount
            HAVING COUNT(*) > 1
        """)
        
        dups = cur.fetchall()
        if dups:
            print(f"Found {len(dups)} duplicate key combinations:")
            for row in dups[:5]:
                print(f"  {row}")
    
    conn.commit()
    print("\n✅ Committed")
    
except psycopg2.errors.UniqueViolation as e:
    print(f"❌ Unique constraint violation: {e}")
    conn.rollback()
except Exception as e:
    print(f"❌ Error: {e}")
    conn.rollback()

# Verify final count
cur.execute("SELECT COUNT(*) as count FROM charter_payments WHERE source = 'batch_deposit_allocation'")
final = cur.fetchone()['count']
print(f"\nFinal charter_payments (batch_deposit_allocation): {final:,}")

cur.close()
conn.close()

print("\n" + "="*100)
