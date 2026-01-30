#!/usr/bin/env python3
"""
Investigate the 20 payment mismatches between charter.paid_amount and SUM(charter_payments).

For each mismatch, check:
1. What charter.paid_amount says
2. What SUM(charter_payments) shows
3. What exists in batch_deposit_allocations
4. What exists in charter_refunds
5. Any other payment sources
"""

import psycopg2
from psycopg2.extras import RealDictCursor
from decimal import Decimal
import os
from dotenv import load_dotenv

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
print("PAYMENT RECONCILIATION - INVESTIGATING 20 MISMATCHES")
print("="*100)

# Find all charters with mismatches
cur.execute("""
    SELECT 
        c.reserve_number,
        c.charter_date,
        c.client_display_name,
        c.total_amount_due,
        c.paid_amount,
        COALESCE(SUM(cp.amount), 0) as sum_payments,
        c.paid_amount - COALESCE(SUM(cp.amount), 0) as difference
    FROM charters c
    LEFT JOIN charter_payments cp ON cp.charter_id = c.reserve_number
    WHERE c.cancelled = FALSE
      AND c.charter_date >= '2012-01-01'
      AND c.paid_amount > 0
    GROUP BY c.reserve_number, c.charter_date, c.client_display_name, c.total_amount_due, c.paid_amount
    HAVING ABS(c.paid_amount - COALESCE(SUM(cp.amount), 0)) > 0.01
    ORDER BY ABS(c.paid_amount - COALESCE(SUM(cp.amount), 0)) DESC
    LIMIT 25
""")

mismatches = cur.fetchall()

print(f"\nFound {len(mismatches)} payment mismatches:")
print("\n" + "-"*100)

for i, mismatch in enumerate(mismatches, 1):
    reserve = mismatch['reserve_number']
    paid_amount = mismatch['paid_amount']
    sum_payments = mismatch['sum_payments']
    difference = mismatch['difference']
    
    print(f"\n{i}. Reserve {reserve} ({mismatch['client_display_name']})")
    print(f"   Charter date: {mismatch['charter_date']}")
    print(f"   Charter.paid_amount: ${paid_amount:,.2f}")
    print(f"   SUM(charter_payments): ${sum_payments:,.2f}")
    print(f"   Missing: ${difference:,.2f}")
    
    # Check batch_deposit_allocations
    cur.execute("""
        SELECT 
            SUM(allocation_amount) as total,
            COUNT(*) as count,
            method
        FROM batch_deposit_allocations
        WHERE reserve_number = %s
        GROUP BY method
    """, (reserve,))
    
    bda_rows = cur.fetchall()
    if bda_rows:
        print(f"\n   batch_deposit_allocations:")
        for row in bda_rows:
            print(f"     {row['method']}: {row['count']} allocations = ${row['total']:,.2f}")
    else:
        print(f"\n   batch_deposit_allocations: NO ROWS")
    
    # Check charter_refunds
    cur.execute("""
        SELECT 
            SUM(amount) as total,
            COUNT(*) as count
        FROM charter_refunds
        WHERE reserve_number = %s
    """, (reserve,))
    
    refund_row = cur.fetchone()
    if refund_row and refund_row['total']:
        print(f"   charter_refunds: {refund_row['count']} = ${refund_row['total']:,.2f}")
    else:
        print(f"   charter_refunds: NO ROWS")
    
    # Check what IS in charter_payments for this charter
    cur.execute("""
        SELECT 
            source, COUNT(*) as count, SUM(amount) as total
        FROM charter_payments
        WHERE charter_id = %s
        GROUP BY source
    """, (reserve,))
    
    payment_sources = cur.fetchall()
    if payment_sources:
        print(f"   charter_payments (by source):")
        for row in payment_sources:
            print(f"     {row['source'] or 'NULL'}: {row['count']} = ${row['total']:,.2f}")
    else:
        print(f"   charter_payments: NO ROWS")

print("\n" + "="*100)
print("\nSUMMARY:")
total_diff = sum(m['difference'] for m in mismatches)
print(f"  Total difference (missing payments): ${abs(total_diff):,.2f}")
print(f"  Average mismatch: ${abs(total_diff)/len(mismatches):,.2f}")

# Check if there are batch_deposit_allocations that haven't been migrated
cur.execute("""
    SELECT COUNT(*) as count
    FROM batch_deposit_allocations bda
    WHERE NOT EXISTS (
        SELECT 1 FROM charter_payments cp
        WHERE cp.charter_id = bda.reserve_number
          AND cp.payment_key LIKE 'BDA_%'
    )
""")
unmigrated = cur.fetchone()['count']
print(f"\nUnmigrated batch_deposit_allocations: {unmigrated:,} rows")

cur.close()
conn.close()

print("\n" + "="*100)
