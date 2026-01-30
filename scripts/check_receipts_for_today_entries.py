"""
Verify whether receipts already exist for today's inserted entries.
- WCB invoices (account 4973477) for specific 2019 dates
- Recent Fibrenew receipts
- Receipts created today (if created_at available)
"""
import psycopg2
from datetime import date

DB = dict(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')

WCB_VENDOR = "WCB Alberta (Account 4973477)"
WCB_DATES = [date(2019,7,19), date(2019,9,19), date(2019,11,19)]


def main():
    cn = psycopg2.connect(**DB)
    try:
        cur = cn.cursor()
        
        print("\nChecking WCB receipts...")
        cur.execute(
            """
            SELECT id, source_system, source_reference, receipt_date, vendor_name, gross_amount
            FROM receipts
            WHERE vendor_name = %s AND receipt_date = ANY(%s)
            ORDER BY id
            """,
            (WCB_VENDOR, WCB_DATES)
        )
        rows = cur.fetchall()
        print(f"  Found {len(rows)} WCB receipts")
        for r in rows:
            print(f"    id={r[0]} | {r[1]}:{r[2]} | {r[3]} | ${r[5]:.2f}")
        
        print("\nRecent Fibrenew receipts (top 10)...")
        cur.execute(
            """
            SELECT id, receipt_date, vendor_name, gross_amount
            FROM receipts
            WHERE LOWER(vendor_name) LIKE '%fibrenew%'
            ORDER BY id DESC
            LIMIT 10
            """
        )
        fib = cur.fetchall()
        print(f"  Found {len(fib)} recent Fibrenew receipts")
        for r in fib:
            print(f"    id={r[0]} | {r[1]} | ${r[3]:.2f} | {r[2]}")
        
        print("\nReceipts created today (if available)...")
        try:
            cur.execute("SELECT COUNT(*) FROM receipts WHERE DATE(created_at)=CURRENT_DATE")
            c = cur.fetchone()[0]
            print(f"  Created today: {c}")
            if c:
                cur.execute(
                    """
                    SELECT id, vendor_name, receipt_date, gross_amount
                    FROM receipts
                    WHERE DATE(created_at)=CURRENT_DATE
                    ORDER BY id
                    LIMIT 20
                    """
                )
                for r in cur.fetchall():
                    print(f"    id={r[0]} | {r[1]} | {r[2]} | ${r[3]:.2f}")
        except Exception as e:
            print(f"  created_at not available: {e}")
    finally:
        cn.close()

if __name__ == '__main__':
    main()
