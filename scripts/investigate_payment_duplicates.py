"""
Investigate why we have duplicate payments in the database.
Are they true duplicates or just same amounts?
"""

import psycopg2
import os

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 100)
    print("INVESTIGATING DUPLICATE PAYMENTS")
    print("=" * 100)
    print()
    
    # Check for true duplicates (same date, amount, method, notes)
    print("1. TRUE DUPLICATES (same date + amount + method + notes):")
    print("-" * 100)
    
    cur.execute("""
        SELECT 
            payment_date,
            amount,
            payment_method,
            LEFT(COALESCE(notes, 'NO NOTES'), 50) as notes_sample,
            COUNT(*) as duplicate_count,
            STRING_AGG(payment_id::text, ', ' ORDER BY payment_id) as payment_ids
        FROM payments
        WHERE (charter_id IS NULL OR charter_id = 0)
        AND EXTRACT(YEAR FROM payment_date) BETWEEN 2007 AND 2024
        GROUP BY payment_date, amount, payment_method, LEFT(COALESCE(notes, 'NO NOTES'), 50)
        HAVING COUNT(*) > 1
        ORDER BY COUNT(*) DESC, payment_date DESC
        LIMIT 20
    """)
    
    true_dupes = cur.fetchall()
    print(f"\nFound {len(true_dupes)} groups with potential duplicates")
    print()
    
    for pdate, amount, method, notes, count, ids in true_dupes:
        print(f"Date: {pdate} | Amount: ${amount if amount else 0:,.2f} | Method: {method or 'N/A'}")
        print(f"Notes: {notes}")
        print(f"Count: {count} duplicates | Payment IDs: {ids}")
        print()
    
    # Check specific payment details for one duplicate group
    if true_dupes:
        print("=" * 100)
        print("DETAILED COMPARISON OF FIRST DUPLICATE GROUP:")
        print("=" * 100)
        print()
        
        first_group = true_dupes[0]
        payment_ids = first_group[5].split(', ')
        
        for pid in payment_ids:
            cur.execute("""
                SELECT 
                    payment_id,
                    payment_date,
                    amount,
                    payment_method,
                    account_number,
                    reserve_number,
                    check_number,
                    square_transaction_id,
                    client_id,
                    notes,
                    created_at,
                    payment_key
                FROM payments
                WHERE payment_id = %s
            """, (int(pid),))
            
            row = cur.fetchone()
            if row:
                pid, pdate, amt, method, account, reserve, check, square, client_id, notes, created, key = row
                print(f"Payment ID: {pid}")
                print(f"  Date: {pdate}")
                print(f"  Amount: ${amt if amt else 0:,.2f}")
                print(f"  Method: {method or 'None'}")
                print(f"  Account: {account or 'None'} | Reserve: {reserve or 'None'}")
                print(f"  Check#: {check or 'None'} | Square: {square or 'None'}")
                print(f"  Client ID: {client_id or 'None'}")
                print(f"  Payment Key: {key or 'None'}")
                print(f"  Created: {created}")
                print(f"  Notes: {notes or 'None'}")
                print()
    
    # Check for same amount on same date but different payment records
    print("=" * 100)
    print("2. SAME AMOUNT ON SAME DATE (but potentially different sources):")
    print("=" * 100)
    print()
    
    cur.execute("""
        WITH amount_groups AS (
            SELECT 
                payment_date,
                amount,
                COUNT(*) as count,
                COUNT(DISTINCT payment_method) as distinct_methods,
                COUNT(DISTINCT COALESCE(notes, 'NO_NOTES')) as distinct_notes,
                COUNT(DISTINCT payment_key) as distinct_keys,
                STRING_AGG(DISTINCT payment_method, ', ') as methods,
                STRING_AGG(payment_id::text, ', ' ORDER BY payment_id) as payment_ids
            FROM payments
            WHERE (charter_id IS NULL OR charter_id = 0)
            AND EXTRACT(YEAR FROM payment_date) BETWEEN 2007 AND 2024
            GROUP BY payment_date, amount
            HAVING COUNT(*) > 1
        )
        SELECT * FROM amount_groups
        ORDER BY count DESC, payment_date DESC
        LIMIT 20
    """)
    
    amount_dupes = cur.fetchall()
    print(f"\nFound {len(amount_dupes)} dates with multiple payments of same amount")
    print()
    
    for pdate, amount, count, distinct_methods, distinct_notes, distinct_keys, methods, ids in amount_dupes:
        print(f"Date: {pdate} | Amount: ${amount if amount else 0:,.2f}")
        print(f"  {count} payments | {distinct_methods} different methods: {methods}")
        print(f"  {distinct_notes} different note patterns | {distinct_keys} different payment keys")
        print(f"  Payment IDs: {ids}")
        print()
    
    # Check for imported from multiple sources
    print("=" * 100)
    print("3. PAYMENTS IMPORTED FROM MULTIPLE SOURCES:")
    print("=" * 100)
    print()
    
    cur.execute("""
        SELECT 
            CASE 
                WHEN notes ILIKE '%LMS Deposit%' THEN 'LMS Deposit'
                WHEN notes ILIKE '%LMS Sync Import%' THEN 'LMS Sync Import'
                WHEN notes ILIKE '%Square%' THEN 'Square (notes)'
                WHEN square_transaction_id IS NOT NULL THEN 'Square (txn_id)'
                WHEN payment_key LIKE '00%' THEN 'LMS Payment Key'
                ELSE 'Manual/Other'
            END as source,
            COUNT(*) as count,
            MIN(payment_date) as earliest,
            MAX(payment_date) as latest
        FROM payments
        WHERE (charter_id IS NULL OR charter_id = 0)
        AND EXTRACT(YEAR FROM payment_date) BETWEEN 2007 AND 2024
        GROUP BY source
        ORDER BY count DESC
    """)
    
    print("\nUnmatched payments by import source:")
    print("-" * 100)
    for source, count, earliest, latest in cur.fetchall():
        print(f"{source:<25} {count:>6,} payments  ({earliest} to {latest})")
    
    # Check for duplicate payment_keys
    print()
    print("=" * 100)
    print("4. DUPLICATE PAYMENT KEYS (from LMS imports):")
    print("=" * 100)
    print()
    
    cur.execute("""
        SELECT 
            payment_key,
            COUNT(*) as count,
            STRING_AGG(payment_id::text, ', ' ORDER BY payment_id) as payment_ids,
            MIN(payment_date) as date,
            MIN(amount) as amount
        FROM payments
        WHERE payment_key IS NOT NULL
        AND payment_key != ''
        GROUP BY payment_key
        HAVING COUNT(*) > 1
        ORDER BY COUNT(*) DESC
        LIMIT 20
    """)
    
    key_dupes = cur.fetchall()
    
    if key_dupes:
        print(f"\nFound {len(key_dupes)} payment keys with duplicates!")
        print()
        for key, count, ids, date, amount in key_dupes:
            print(f"Payment Key: {key} | Count: {count}")
            print(f"  Date: {date} | Amount: ${amount if amount else 0:,.2f}")
            print(f"  Payment IDs: {ids}")
            print()
    else:
        print("\n[OK] No duplicate payment keys found")
        print("   (Each LMS payment key is unique)")
    
    # Summary
    print()
    print("=" * 100)
    print("SUMMARY:")
    print("=" * 100)
    print()
    print(f"True duplicates (exact match): {len(true_dupes)} groups")
    print(f"Same amount on same date: {len(amount_dupes)} groups")
    print()
    
    if len(true_dupes) > 0:
        print("[WARN]  TRUE DUPLICATES FOUND!")
        print("   These are likely duplicate imports from:")
        print("   - Multiple LMS import runs")
        print("   - Manual entry + automated import")
        print("   - Data migration issues")
        print()
        print("   Recommendation: Review and de-duplicate")
    
    if len(key_dupes) > 0:
        print("[WARN]  DUPLICATE PAYMENT KEYS FOUND!")
        print("   Payment keys should be unique from LMS")
        print("   This indicates multiple imports of same data")
        print()
        print("   Recommendation: Keep only one copy per payment_key")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
