#!/usr/bin/env python3
import os
import psycopg2

def main():
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***'),
    )
    cur = conn.cursor()

    vendors = [
        ('GoDaddy', "vendor_name ILIKE 'godaddy%'", "description ILIKE '%GODADDY%'") ,
        ('Wix', "vendor_name ILIKE 'wix%'", "description ILIKE '%WIX%'") ,
        ('IONOS', "vendor_name ILIKE 'ionos%'", "description ILIKE '%IONOS%' OR description ILIKE '%1&1%'") ,
    ]

    print("RECEIPTS SUMMARY")
    for name, cond, _ in vendors:
        cur.execute(f"""
            SELECT COUNT(*), COALESCE(SUM(gross_amount),0), MIN(receipt_date), MAX(receipt_date), MIN(gross_amount), MAX(gross_amount)
            FROM receipts WHERE {cond}
        """)
        c,s,lo,hi,mn,mx = cur.fetchone()
        mn = mn or 0
        mx = mx or 0
        print(f"- {name:7}: {c:4} records, gross ${s:,.2f}, range {lo}..{hi}, min ${mn:.2f}, max ${mx:.2f}")

    print("\nBANKING SUMMARY (vendor-like descriptions)")
    for name, _, dcond in vendors:
        cur.execute(f"""
            SELECT COUNT(*), COALESCE(SUM(debit_amount),0), MIN(transaction_date), MAX(transaction_date), MIN(debit_amount), MAX(debit_amount)
            FROM banking_transactions WHERE ({dcond}) AND debit_amount>0
        """)
        c,s,lo,hi,mn,mx = cur.fetchone()
        mn = mn or 0
        mx = mx or 0
        print(f"- {name:7}: {c:4} debits, total ${s:,.2f}, range {lo}..{hi}, min ${mn:.2f}, max ${mx:.2f}")

    print("\nSAMPLE BANKING DESCRIPTIONS (5 each)")
    for name, _, dcond in vendors:
        print(f"\n{name}:")
        cur.execute(f"""
            SELECT transaction_date, description, debit_amount 
            FROM banking_transactions 
            WHERE ({dcond}) AND debit_amount>0 
            ORDER BY transaction_date DESC 
            LIMIT 5
        """)
        rows = cur.fetchall()
        for r in rows:
            print(r)

    cur.close(); conn.close()

if __name__ == '__main__':
    main()
