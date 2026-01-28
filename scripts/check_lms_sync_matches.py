"""
Check if recent LMS Sync Import payments match existing charters.
"""

import psycopg2
import os

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 100)
    print("CHECKING LMS SYNC IMPORT PAYMENTS")
    print("=" * 100)
    print()
    
    # Get 2025 unmatched payments with reserve numbers
    cur.execute("""
        SELECT 
            p.payment_id,
            p.payment_date,
            p.account_number,
            p.reserve_number,
            p.amount,
            p.notes
        FROM payments p
        WHERE (p.charter_id IS NULL OR p.charter_id = 0)
        AND EXTRACT(YEAR FROM p.payment_date) = 2025
        AND p.reserve_number IS NOT NULL
        ORDER BY p.payment_date DESC
        LIMIT 50
    """)
    
    lms_payments = cur.fetchall()
    print(f"Found {len(lms_payments)} unmatched 2025 payments with reserve numbers")
    print()
    
    matched_count = 0
    not_found_count = 0
    
    for payment_id, pdate, account, reserve, amount, notes in lms_payments:
        # Check if charter exists
        cur.execute("""
            SELECT charter_id, charter_date, status
            FROM charters
            WHERE reserve_number = %s
        """, (reserve,))
        
        charter_row = cur.fetchone()
        
        if charter_row:
            charter_id, cdate, status = charter_row
            print(f"[OK] MATCH FOUND:")
            print(f"   Payment {payment_id}: {pdate} | Reserve {reserve} | ${amount:,.2f}")
            print(f"   → Charter {charter_id}: {cdate} | Status: {status or 'None'}")
            print(f"   Notes: {notes[:80] if notes else 'None'}")
            print()
            matched_count += 1
        else:
            print(f"[FAIL] NO CHARTER FOUND:")
            print(f"   Payment {payment_id}: {pdate} | Reserve {reserve} | ${amount:,.2f}")
            print(f"   Account: {account} | Notes: {notes[:80] if notes else 'None'}")
            print()
            not_found_count += 1
    
    print("=" * 100)
    print(f"Summary:")
    print(f"  Payments checked: {len(lms_payments)}")
    print(f"  Charters found: {matched_count}")
    print(f"  Charters NOT found: {not_found_count}")
    print("=" * 100)
    
    if matched_count > 0:
        print()
        print(f"[OK] Found {matched_count} payments that CAN be matched!")
        print("   These payments have reserve numbers but charter_id is not set.")
        print("   Would you like to apply these matches?")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
