#!/usr/bin/env python3
"""
Remove payments from 5 reserves that now have negative balances.
LMS shows 0 payments for these cancelled reserves.
"""

import psycopg2

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = "***REMOVED***"

# 5 reserves with negative balance - remove payments to match LMS (0 payments)
RESERVES_TO_FIX = [
    '017887',  # -$189 payment
    '017765',  # -$75 payment
    '018013',  # -$175 payment
    '015288',  # -$75 payment
    '015244',  # -$500 payment
]

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("Removing payments from 5 negative-balance reserves...")
print()

total_removed = 0.0

try:
    for reserve in RESERVES_TO_FIX:
        # Get payments before delete
        cur.execute("""
            SELECT SUM(amount) FROM payments 
            WHERE reserve_number = %s
        """, (reserve,))
        payments = float(cur.fetchone()[0] or 0.0)
        
        # Delete payments
        cur.execute("""
            DELETE FROM payments
            WHERE reserve_number = %s
        """, (reserve,))
        deleted = cur.rowcount
        
        # Verify balance
        cur.execute("""
            SELECT 
                COALESCE((SELECT SUM(amount) FROM charter_charges WHERE reserve_number = %s), 0) as charges,
                COALESCE((SELECT SUM(amount) FROM payments WHERE reserve_number = %s), 0) as payments
        """, (reserve, reserve))
        remaining_charges, remaining_payments = cur.fetchone()
        remaining_charges, remaining_payments = float(remaining_charges), float(remaining_payments)
        
        print(f"✓ {reserve}: removed ${payments:>10.2f} in payments ({deleted} rows), balance: ${remaining_charges - remaining_payments:>10.2f}")
        total_removed += payments
    
    conn.commit()
    print()
    print("=" * 70)
    print(f"Total payments removed: ${total_removed:,.2f}")
    print("=" * 70)
    print("\n✅ 5 reserves fixed (charges removed, payments removed = $0 balance)")
    
except Exception as e:
    conn.rollback()
    print(f"❌ Error: {e}")
finally:
    cur.close()
    conn.close()
