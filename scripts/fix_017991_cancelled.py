#!/usr/bin/env python3
"""
Fix 017991: Mark as cancelled, remove charges, zero balance.
"""

import psycopg2

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = os.environ.get("DB_PASSWORD")

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

try:
    # Mark as cancelled
    cur.execute("""
        UPDATE charters 
        SET status = 'Cancelled'
        WHERE reserve_number = '017991'
    """)
    print(f"✓ Marked 017991 as Cancelled: {cur.rowcount} rows")
    
    # Get charges before delete
    cur.execute("""
        SELECT SUM(amount) FROM charter_charges 
        WHERE reserve_number = '017991'
    """)
    charges_to_remove = cur.fetchone()[0] or 0
    
    # Delete charges
    cur.execute("""
        DELETE FROM charter_charges
        WHERE reserve_number = '017991'
    """)
    print(f"✓ Deleted charges: {cur.rowcount} rows (total: ${charges_to_remove:,.2f})")
    
    # Verify balance
    cur.execute("""
        SELECT 
            COALESCE((SELECT SUM(amount) FROM charter_charges WHERE reserve_number = '017991'), 0) as charges,
            COALESCE((SELECT SUM(amount) FROM payments WHERE reserve_number = '017991'), 0) as payments,
            COALESCE((SELECT SUM(amount) FROM charter_charges WHERE reserve_number = '017991'), 0) - 
            COALESCE((SELECT SUM(amount) FROM payments WHERE reserve_number = '017991'), 0) as balance
    """)
    charges, payments, balance = cur.fetchone()
    print(f"✓ Verified 017991 balance: charges=${charges:,.2f}, payments=${payments:,.2f}, balance=${balance:,.2f}")
    
    conn.commit()
    print("\n✅ 017991 fixed and committed")
    
except Exception as e:
    conn.rollback()
    print(f"❌ Error: {e}")
finally:
    cur.close()
    conn.close()
