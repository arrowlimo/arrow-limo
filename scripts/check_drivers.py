#!/usr/bin/env python
"""Check LARRY TAYLOR and JESSE GORDON - are they drivers?"""

import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

for name in ['LARRY TAYLOR', 'JESSE GORDON']:
    print(f"\n{'='*80}")
    print(f"{name} - GL 9999 Entries")
    print(f"{'='*80}")
    
    cur.execute("""
        SELECT COUNT(*), ROUND(SUM(COALESCE(gross_amount, 0))::numeric, 2), 
               MIN(receipt_date), MAX(receipt_date)
        FROM receipts
        WHERE vendor_name = %s AND gl_account_code = '9999'
    """, (name,))
    
    count, total, min_date, max_date = cur.fetchone()
    if count:
        print(f"Count: {count}")
        print(f"Total: ${float(total):.2f}")
        print(f"Date range: {min_date} to {max_date}")
        print(f"\n→ {name} is a DRIVER → GL 5000 (Driver Pay/Reimbursement)")
    else:
        print(f"No entries found")

cur.close()
conn.close()
