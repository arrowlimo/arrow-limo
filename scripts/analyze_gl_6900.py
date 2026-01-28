#!/usr/bin/env python
"""Analyze GL 6900 entries to propose GL code remapping."""
import psycopg2, os

DB_HOST = os.environ.get('DB_HOST','localhost')
DB_NAME = os.environ.get('DB_NAME','almsdata')
DB_USER = os.environ.get('DB_USER','postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD','***REMOVED***')

def main():
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    
    print("=" * 100)
    print("GL 6900 ANALYSIS FOR REMAPPING")
    print("=" * 100)
    
    # Count and breakdown by category
    cur.execute("""
        SELECT COUNT(*) FROM receipts WHERE gl_account_code = '6900'
    """)
    total = cur.fetchone()[0]
    print(f"\nTotal GL 6900 receipts: {total}")
    
    cur.execute("""
        SELECT COALESCE(category, '(uncategorized)'), COUNT(*) cnt
        FROM receipts
        WHERE gl_account_code = '6900'
        GROUP BY category
        ORDER BY cnt DESC
    """)
    print("\nBreakdown by category:")
    for r in cur.fetchall():
        print(f"  {r[0]}: {r[1]}")
    
    # Sample by category
    categories = ['BANKING', 'TRANSFERS', 'internal_transfer', 'Bank Deposit', 'Cheque', None]
    for cat in categories:
        if cat is None:
            cur.execute("""
                SELECT receipt_id, receipt_date, vendor_name, gross_amount, category, canonical_vendor, description
                FROM receipts
                WHERE gl_account_code = '6900' AND category IS NULL
                ORDER BY receipt_date DESC
                LIMIT 5
            """)
        else:
            cur.execute("""
                SELECT receipt_id, receipt_date, vendor_name, gross_amount, category, canonical_vendor, description
                FROM receipts
                WHERE gl_account_code = '6900' AND category = %s
                ORDER BY receipt_date DESC
                LIMIT 5
            """, (cat,))
        rows = cur.fetchall()
        if rows:
            print(f"\nSample GL 6900 with category={cat}:")
            for r in rows:
                print(f"  {r[0]} | {r[1]} | {r[2]} | ${r[3]} | {r[5]} | {r[6][:50] if r[6] else ''}")
    
    cur.close(); conn.close()

if __name__ == '__main__':
    main()
