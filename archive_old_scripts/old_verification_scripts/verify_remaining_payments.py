#!/usr/bin/env python3
"""
Verify remaining local-only payments after deletion.
"""
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Database connections
local_conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password=os.getenv("POSTGRES_PASSWORD")
)

neon_conn = psycopg2.connect(os.getenv("NEON_DATABASE_URL"))

print("=" * 80)
print("VERIFY REMAINING PAYMENTS AFTER CLEANUP")
print("=" * 80)
print()

# Get all payment IDs from both databases
print("Loading payment IDs from both databases...")
with local_conn.cursor() as cur:
    cur.execute("SELECT payment_id FROM payments ORDER BY payment_id")
    local_ids = {row[0] for row in cur.fetchall()}
    print(f"✅ Local: {len(local_ids):,} payment_ids")

with neon_conn.cursor() as cur:
    cur.execute("SELECT payment_id FROM payments ORDER BY payment_id")
    neon_ids = {row[0] for row in cur.fetchall()}
    print(f"✅ Neon: {len(neon_ids):,} payment_ids")

print()
print("=" * 80)
print("COMPARISON")
print("=" * 80)

# Calculate differences
in_both = local_ids & neon_ids
local_only = local_ids - neon_ids
neon_only = neon_ids - local_ids

print(f"✅ In BOTH databases:  {len(in_both):>6,} payment_ids")
print(f"📤 LOCAL only:         {len(local_only):>6,} payment_ids")
print(f"📥 NEON only:          {len(neon_only):>6,} payment_ids")
print()
print(f"📊 Total unique IDs:   {len(local_ids | neon_ids):>6,} payment_ids")

# Get reserve number count for local-only payments
print()
print("=" * 80)
print("LOCAL-ONLY PAYMENT DETAILS")
print("=" * 80)
if local_only:
    with local_conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT 
                COUNT(*) as payment_count,
                COUNT(DISTINCT reserve_number) as charter_count,
                MIN(payment_date) as earliest_payment,
                MAX(payment_date) as latest_payment,
                SUM(amount) as total_amount
            FROM payments
            WHERE payment_id = ANY(%s)
        """, (list(local_only),))
        summary = cur.fetchone()
        
        print(f"Payments:       {summary['payment_count']:>6,}")
        print(f"Charters:       {summary['charter_count']:>6,}")
        print(f"Earliest:       {summary['earliest_payment']}")
        print(f"Latest:         {summary['latest_payment']}")
        print(f"Total Amount: ${summary['total_amount']:>12,.2f}")

# Check for 2025+ payments
        print()
        cur.execute("""
            SELECT COUNT(*) as count_2025_plus
            FROM payments
            WHERE payment_id = ANY(%s)
            AND payment_date >= '2025-01-01'
        """, (list(local_only),))
        count_2025 = cur.fetchone()['count_2025_plus']
        print(f"2025+ Payments: {count_2025:>6,}")
        print(f"Pre-2025:       {summary['payment_count'] - count_2025:>6,}")

print()
print("✅ Verification complete")

local_conn.close()
neon_conn.close()
