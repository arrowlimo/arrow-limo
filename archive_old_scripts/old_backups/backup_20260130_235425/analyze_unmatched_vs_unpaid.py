"""
Analyze why unmatched payments don't match unpaid charters.
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
    print("ANALYZING UNMATCHED PAYMENTS VS UNPAID CHARTERS")
    print("=" * 100)
    print()
    
    # Check date ranges
    print("DATE RANGE ANALYSIS:")
    print("-" * 100)
    
    cur.execute("""
        SELECT 
            MIN(payment_date) as min_date,
            MAX(payment_date) as max_date,
            COUNT(*) as count
        FROM payments
        WHERE (charter_id IS NULL OR charter_id = 0)
    """)
    min_pay, max_pay, count_pay = cur.fetchone()
    print(f"Unmatched payments: {count_pay} payments from {min_pay} to {max_pay}")
    
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM payment_date) as year,
            COUNT(*) as count,
            SUM(amount) as total
        FROM payments
        WHERE (charter_id IS NULL OR charter_id = 0)
        GROUP BY EXTRACT(YEAR FROM payment_date)
        ORDER BY year DESC
        LIMIT 10
    """)
    print("\nUnmatched payments by year (recent):")
    for year, count, total in cur.fetchall():
        print(f"  {int(year)}: {count:,} payments (${total:,.2f})")
    
    cur.execute("""
        SELECT 
            MIN(c.charter_date) as min_date,
            MAX(c.charter_date) as max_date,
            COUNT(*) as count
        FROM charters c
        LEFT JOIN (
            SELECT charter_id, SUM(COALESCE(amount, 0)) as total_charges
            FROM charter_charges
            GROUP BY charter_id
        ) cc ON c.charter_id = cc.charter_id
        WHERE NOT EXISTS (
            SELECT 1 FROM payments p 
            WHERE p.charter_id = c.charter_id
        )
        AND COALESCE(c.payment_excluded, FALSE) = FALSE
        AND COALESCE(cc.total_charges, 0) > 0
    """)
    min_charter, max_charter, count_charter = cur.fetchone()
    print(f"\nUnpaid charters: {count_charter} charters from {min_charter} to {max_charter}")
    
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM c.charter_date) as year,
            COUNT(*) as count,
            SUM(COALESCE(cc.total_charges, 0)) as total
        FROM charters c
        LEFT JOIN (
            SELECT charter_id, SUM(COALESCE(amount, 0)) as total_charges
            FROM charter_charges
            GROUP BY charter_id
        ) cc ON c.charter_id = cc.charter_id
        WHERE NOT EXISTS (
            SELECT 1 FROM payments p 
            WHERE p.charter_id = c.charter_id
        )
        AND COALESCE(c.payment_excluded, FALSE) = FALSE
        AND COALESCE(cc.total_charges, 0) > 0
        GROUP BY EXTRACT(YEAR FROM c.charter_date)
        ORDER BY year DESC
    """)
    print("\nUnpaid charters by year:")
    for year, count, total in cur.fetchall():
        print(f"  {int(year)}: {count} charters (${total:,.2f})")
    
    print()
    print("=" * 100)
    print("SAMPLE UNMATCHED PAYMENTS (Recent):")
    print("=" * 100)
    
    cur.execute("""
        SELECT 
            p.payment_id,
            p.payment_date,
            p.account_number,
            p.reserve_number,
            p.amount,
            p.payment_method,
            cl.client_name,
            LEFT(p.notes, 80) as notes_sample
        FROM payments p
        LEFT JOIN clients cl ON p.client_id = cl.client_id
        WHERE (p.reserve_number IS NULL OR p.charter_id = 0)
        AND EXTRACT(YEAR FROM p.payment_date) >= 2019
        ORDER BY p.payment_date DESC
        LIMIT 20
    """)
    
    for row in cur.fetchall():
        payment_id, pdate, account, reserve, amount, method, client, notes = row
        print(f"\nPayment {payment_id}: {pdate} | ${amount:,.2f} | {method or 'N/A'}")
        print(f"  Account: {account or 'None'} | Reserve: {reserve or 'None'}")
        print(f"  Client: {client or 'Unknown'}")
        if notes:
            print(f"  Notes: {notes}")
    
    print()
    print("=" * 100)
    print("SAMPLE UNPAID CHARTERS:")
    print("=" * 100)
    
    cur.execute("""
        SELECT 
            c.charter_id,
            c.reserve_number,
            c.charter_date,
            c.account_number,
            cl.client_name,
            COALESCE(cc.total_charges, 0) as total_charges,
            c.status
        FROM charters c
        LEFT JOIN clients cl ON c.client_id = cl.client_id
        LEFT JOIN (
            SELECT charter_id, SUM(COALESCE(amount, 0)) as total_charges
            FROM charter_charges
            GROUP BY charter_id
        ) cc ON c.charter_id = cc.charter_id
        WHERE NOT EXISTS (
            SELECT 1 FROM payments p 
            WHERE p.charter_id = c.charter_id
        )
        AND COALESCE(c.payment_excluded, FALSE) = FALSE
        AND COALESCE(cc.total_charges, 0) > 0
        ORDER BY total_charges DESC
        LIMIT 20
    """)
    
    for row in cur.fetchall():
        charter_id, reserve, cdate, account, client, charges, status = row
        print(f"\nCharter {charter_id} (Reserve {reserve}): {cdate} | ${charges:,.2f}")
        print(f"  Account: {account or 'None'} | Client: {client or 'Unknown'}")
        print(f"  Status: {status}")
    
    print()
    print("=" * 100)
    print("ACCOUNT NUMBER COMPARISON:")
    print("=" * 100)
    
    cur.execute("""
        SELECT DISTINCT account_number
        FROM payments
        WHERE (charter_id IS NULL OR charter_id = 0)
        AND account_number IS NOT NULL
        AND EXTRACT(YEAR FROM payment_date) >= 2019
        LIMIT 10
    """)
    print("\nSample unmatched payment account numbers:")
    for (account,) in cur.fetchall():
        print(f"  {account}")
    
    cur.execute("""
        SELECT DISTINCT c.account_number
        FROM charters c
        LEFT JOIN (
            SELECT charter_id, SUM(COALESCE(amount, 0)) as total_charges
            FROM charter_charges
            GROUP BY charter_id
        ) cc ON c.charter_id = cc.charter_id
        WHERE NOT EXISTS (
            SELECT 1 FROM payments p 
            WHERE p.charter_id = c.charter_id
        )
        AND COALESCE(c.payment_excluded, FALSE) = FALSE
        AND COALESCE(cc.total_charges, 0) > 0
        AND c.account_number IS NOT NULL
        LIMIT 10
    """)
    print("\nSample unpaid charter account numbers:")
    for (account,) in cur.fetchall():
        print(f"  {account}")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
