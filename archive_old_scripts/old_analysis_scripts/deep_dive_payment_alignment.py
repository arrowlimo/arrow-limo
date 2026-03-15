#!/usr/bin/env python3
"""
Deep dive into payment alignment - verify what happened.
"""
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import os

load_dotenv()

local_conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password=os.getenv("POSTGRES_PASSWORD")
)

neon_conn = psycopg2.connect(os.getenv("NEON_DATABASE_URL"))

print("=" * 80)
print("DEEP DIVE: PAYMENT DATABASE ALIGNMENT")
print("=" * 80)
print()

# Check row counts
print("📊 ROW COUNTS:")
with local_conn.cursor() as cur:
    cur.execute("SELECT COUNT(*) FROM payments")
    local_count = cur.fetchone()[0]
    print(f"   Local:  {local_count:,}")

with neon_conn.cursor() as cur:
    cur.execute("SELECT COUNT(*) FROM payments")
    neon_count = cur.fetchone()[0]
    print(f"   Neon:   {neon_count:,}")

# Check if payment_ids are identical
print()
print("🔍 CHECKING PAYMENT_ID ALIGNMENT:")
with local_conn.cursor() as cur:
    cur.execute("SELECT payment_id FROM payments ORDER BY payment_id")
    local_ids = {row[0] for row in cur.fetchall()}

with neon_conn.cursor() as cur:
    cur.execute("SELECT payment_id FROM payments ORDER BY payment_id")
    neon_ids = {row[0] for row in cur.fetchall()}

in_both = local_ids & neon_ids
local_only = local_ids - neon_ids
neon_only = neon_ids - local_ids

print(f"   In both:    {len(in_both):,}")
print(f"   Local only: {len(local_only):,}")
print(f"   Neon only:  {len(neon_only):,}")

# Check min/max IDs
print()
print("📈 PAYMENT_ID RANGES:")
print(f"   Local:  {min(local_ids):,} to {max(local_ids):,}")
print(f"   Neon:   {min(neon_ids):,} to {max(neon_ids):,}")

# Check dates
print()
print("📅 DATE RANGES:")
with local_conn.cursor() as cur:
    cur.execute("SELECT MIN(payment_date), MAX(payment_date) FROM payments")
    local_dates = cur.fetchone()
    print(f"   Local:  {local_dates[0]} to {local_dates[1]}")

with neon_conn.cursor() as cur:
    cur.execute("SELECT MIN(payment_date), MAX(payment_date) FROM payments")
    neon_dates = cur.fetchone()
    print(f"   Neon:   {neon_dates[0]} to {neon_dates[1]}")

# Check totals
print()
print("💰 TOTAL AMOUNTS:")
with local_conn.cursor() as cur:
    cur.execute("SELECT SUM(amount) FROM payments")
    local_total = cur.fetchone()[0]
    print(f"   Local: ${local_total:,.2f}")

with neon_conn.cursor() as cur:
    cur.execute("SELECT SUM(amount) FROM payments")
    neon_total = cur.fetchone()[0]
    print(f"   Neon:  ${neon_total:,.2f}")

# Sample 10 payments to verify data matches
print()
print("🔬 SAMPLE DATA COMPARISON (first 10 payment_ids):")
sample_ids = sorted(list(in_both))[:10]

print("\n   Local:")
with local_conn.cursor(cursor_factory=RealDictCursor) as cur:
    cur.execute("""
        SELECT payment_id, reserve_number, payment_date, amount
        FROM payments
        WHERE payment_id = ANY(%s)
        ORDER BY payment_id
    """, (sample_ids,))
    for row in cur.fetchall():
        print(f"   {row['payment_id']:>6} | {row['reserve_number']} | {row['payment_date']} | ${row['amount']:>10,.2f}")

print("\n   Neon:")
with neon_conn.cursor(cursor_factory=RealDictCursor) as cur:
    cur.execute("""
        SELECT payment_id, reserve_number, payment_date, amount
        FROM payments
        WHERE payment_id = ANY(%s)
        ORDER BY payment_id
    """, (sample_ids,))
    for row in cur.fetchall():
        print(f"   {row['payment_id']:>6} | {row['reserve_number']} | {row['payment_date']} | ${row['amount']:>10,.2f}")

print()
print("=" * 80)
print("✅ Analysis complete")
print("=" * 80)

local_conn.close()
neon_conn.close()
