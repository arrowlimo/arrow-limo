#!/usr/bin/env python3
"""
Execute deletion of payments for charters fully reconciled in Neon.
"""
import psycopg2
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Local database connection
local_conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password=os.getenv("POSTGRES_PASSWORD")
)

def execute_deletion():
    """Execute the SQL deletion script."""
    print("=" * 80)
    print("DELETING PAYMENTS FOR FULLY RECONCILED CHARTERS")
    print("=" * 80)
    print()
    
    # Read the SQL file
    with open("delete_fully_paid_charter_payments_20260205_155703.sql", "r") as f:
        sql = f.read()
    
    # Count before
    with local_conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM payments")
        count_before = cur.fetchone()[0]
        print(f"📊 Payments before deletion: {count_before:,}")
    
    # Execute deletion
    print(f"\n🔴 Deleting 1,321 payments for fully reconciled charters...")
    with local_conn.cursor() as cur:
        cur.execute(sql)
        deleted = cur.rowcount
        local_conn.commit()
        print(f"✅ Deleted {deleted:,} payments")
    
    # Count after
    with local_conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM payments")
        count_after = cur.fetchone()[0]
        print(f"📊 Payments after deletion: {count_after:,}")
        print(f"📉 Net change: {count_after - count_before:,}")
    
    print()
    print("=" * 80)
    print("✅ DELETION COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    try:
        execute_deletion()
    finally:
        local_conn.close()
