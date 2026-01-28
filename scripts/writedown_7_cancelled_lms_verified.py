#!/usr/bin/env python3
"""
Write down 7 cancelled reserves confirmed from LMS review.
User verified these are marked cancelled in LMS and should have charges removed.
"""

import psycopg2

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = "***REMOVED***"

# 7 reserves to write down (confirmed cancelled in LMS)
WRITEDOWN_RESERVES = [
    '015940',  # cancelled, zero balanced by GST = discount in LMS
    '017765',  # marked cancelled, no charges
    '018013',  # marked cancelled, no charges
    '017887',  # marked cancelled (was UNCLOSED, now cancelled)
    '014189',  # now cancelled, charges deleted
    '015288',  # cancelled
    '015244',  # cancelled (NRD)
]

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("Writing down 7 cancelled reserves confirmed from LMS...")
print()

total_removed = 0.0

try:
    for reserve in WRITEDOWN_RESERVES:
        # Get charges before delete
        cur.execute("""
            SELECT SUM(amount) FROM charter_charges 
            WHERE reserve_number = %s
        """, (reserve,))
        charges = float(cur.fetchone()[0] or 0.0)
        
        # Delete charges
        cur.execute("""
            DELETE FROM charter_charges
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
        
        print(f"✓ {reserve}: removed ${charges:>10.2f} ({deleted} rows), balance: ${remaining_charges - remaining_payments:>10.2f}")
        total_removed += charges
    
    conn.commit()
    print()
    print("=" * 70)
    print(f"Total removed: ${total_removed:,.2f}")
    print("=" * 70)
    print("\n✅ 7 cancelled reserves written down and committed")
    
except Exception as e:
    conn.rollback()
    print(f"❌ Error: {e}")
finally:
    cur.close()
    conn.close()
