"""
Analyze unmatched payments in detail to understand what's left.
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
    print("DETAILED ANALYSIS OF REMAINING UNMATCHED PAYMENTS")
    print("=" * 100)
    print()
    
    # Overall count
    cur.execute("""
        SELECT COUNT(*) as total
        FROM payments
        WHERE (charter_id IS NULL OR charter_id = 0)
        AND EXTRACT(YEAR FROM payment_date) BETWEEN 2007 AND 2024
    """)
    total = cur.fetchone()[0]
    print(f"Total unmatched (2007-2024): {total:,}")
    print()
    
    # By year and source
    print("=" * 100)
    print("BREAKDOWN BY YEAR AND SOURCE:")
    print("=" * 100)
    print()
    
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM payment_date) as year,
            CASE 
                WHEN notes ILIKE '%LMS Deposit%' THEN 'LMS Deposit'
                WHEN notes ILIKE '%LMS Sync Import%' THEN 'LMS Sync Import'
                WHEN notes ILIKE '%Square%' THEN 'Square'
                WHEN square_transaction_id IS NOT NULL THEN 'Square (txn_id)'
                WHEN payment_method = 'cash' THEN 'Cash (no notes)'
                WHEN payment_method = 'credit_card' THEN 'Credit Card (no notes)'
                WHEN payment_method = 'check' THEN 'Check'
                WHEN payment_method = 'bank_transfer' THEN 'Bank Transfer'
                ELSE 'Other/Unknown'
            END as source_type,
            COUNT(*) as count,
            SUM(amount) as total_amount
        FROM payments
        WHERE (charter_id IS NULL OR charter_id = 0)
        AND EXTRACT(YEAR FROM payment_date) BETWEEN 2007 AND 2024
        GROUP BY EXTRACT(YEAR FROM payment_date), source_type
        ORDER BY year DESC, count DESC
    """)
    
    results = cur.fetchall()
    
    current_year = None
    for year, source, count, amount in results:
        if year != current_year:
            if current_year is not None:
                print()
            print(f"Year {int(year)}:")
            current_year = year
        print(f"  {source:<25} {count:>6,} payments  ${amount:>12,.2f}")
    
    # Sample of each type
    print()
    print("=" * 100)
    print("SAMPLE PAYMENTS BY TYPE:")
    print("=" * 100)
    print()
    
    # LMS Deposit type
    print("1. LMS Deposit (with reserve numbers in notes but no charter found):")
    print("-" * 100)
    cur.execute("""
        SELECT 
            payment_id,
            payment_date,
            amount,
            payment_method,
            account_number,
            reserve_number,
            LEFT(notes, 80) as notes_sample
        FROM payments
        WHERE (charter_id IS NULL OR charter_id = 0)
        AND notes ILIKE '%LMS Deposit%'
        AND EXTRACT(YEAR FROM payment_date) BETWEEN 2007 AND 2024
        ORDER BY payment_date DESC
        LIMIT 10
    """)
    
    for row in cur.fetchall():
        pid, pdate, amount, method, account, reserve, notes = row
        print(f"Payment {pid}: {pdate} | ${amount:,.2f} | {method or 'N/A'}")
        print(f"  Reserve: {reserve or 'None'} | Account: {account or 'None'}")
        print(f"  Notes: {notes}")
        print()
    
    # Cash with no notes
    print("2. Cash payments (no notes - likely manual entries):")
    print("-" * 100)
    cur.execute("""
        SELECT 
            p.payment_id,
            p.payment_date,
            p.amount,
            p.account_number,
            p.reserve_number,
            cl.client_name,
            COALESCE(p.notes, 'NO NOTES') as notes_sample
        FROM payments p
        LEFT JOIN clients cl ON p.client_id = cl.client_id
        WHERE (p.charter_id IS NULL OR p.charter_id = 0)
        AND p.payment_method = 'cash'
        AND (p.notes IS NULL OR p.notes = '')
        AND EXTRACT(YEAR FROM p.payment_date) BETWEEN 2007 AND 2024
        ORDER BY p.payment_date DESC
        LIMIT 10
    """)
    
    for row in cur.fetchall():
        pid, pdate, amount, account, reserve, client, notes = row
        print(f"Payment {pid}: {pdate} | ${amount:,.2f}")
        print(f"  Client: {client or 'Unknown'} | Reserve: {reserve or 'None'}")
        print(f"  Account: {account or 'None'}")
        print()
    
    # Credit card with no notes
    print("3. Credit Card payments (no notes - likely manual entries):")
    print("-" * 100)
    cur.execute("""
        SELECT 
            p.payment_id,
            p.payment_date,
            p.amount,
            p.account_number,
            p.reserve_number,
            cl.client_name,
            COALESCE(p.notes, 'NO NOTES') as notes_sample
        FROM payments p
        LEFT JOIN clients cl ON p.client_id = cl.client_id
        WHERE (p.charter_id IS NULL OR p.charter_id = 0)
        AND p.payment_method = 'credit_card'
        AND (p.notes IS NULL OR p.notes = '')
        AND EXTRACT(YEAR FROM p.payment_date) BETWEEN 2007 AND 2024
        ORDER BY p.payment_date DESC
        LIMIT 10
    """)
    
    for row in cur.fetchall():
        pid, pdate, amount, account, reserve, client, notes = row
        print(f"Payment {pid}: {pdate} | ${amount:,.2f}")
        print(f"  Client: {client or 'Unknown'} | Reserve: {reserve or 'None'}")
        print(f"  Account: {account or 'None'}")
        print()
    
    # Payments with future/invalid dates
    print("4. Payments with unusual dates:")
    print("-" * 100)
    cur.execute("""
        SELECT 
            payment_id,
            payment_date,
            amount,
            payment_method,
            LEFT(notes, 60) as notes_sample
        FROM payments
        WHERE (charter_id IS NULL OR charter_id = 0)
        AND (
            EXTRACT(YEAR FROM payment_date) > 2024 OR
            EXTRACT(YEAR FROM payment_date) < 2007
        )
        ORDER BY payment_date DESC
        LIMIT 10
    """)
    
    for row in cur.fetchall():
        pid, pdate, amount, method, notes = row
        print(f"Payment {pid}: {pdate} | ${amount:,.2f} | {method or 'N/A'}")
        print(f"  Notes: {notes or 'None'}")
        print()
    
    # Summary recommendations
    print("=" * 100)
    print("RECOMMENDATIONS:")
    print("=" * 100)
    print()
    print("1. LMS Deposits with reserve numbers:")
    print("   These have reserve numbers in notes but charters don't exist")
    print("   → Likely old/cancelled/deleted charters from LMS")
    print("   → May need manual verification")
    print()
    print("2. Cash/Credit Card with no notes:")
    print("   Manual entries without proper documentation")
    print("   → Cross-reference with banking transactions")
    print("   → Review original source documents")
    print()
    print("3. Future-dated payments:")
    print("   Likely data entry errors or placeholders")
    print("   → Verify dates and correct")
    print()
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
