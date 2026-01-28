#!/usr/bin/env python
"""Match CORRECTION entries to banking transactions by dollar amount."""

import psycopg2
import os
import csv

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("\n" + "="*100)
print("CORRECTION 00339 - MATCH TO BANKING TRANSACTIONS (Cancelled/Stopped)")
print("="*100)

# Get CORRECTION entries
cur.execute("""
    SELECT receipt_id, receipt_date, gross_amount, description
    FROM receipts
    WHERE vendor_name = 'CORRECTION 00339' AND gl_account_code = '9999'
    ORDER BY receipt_date DESC
    LIMIT 20
""")

corrections = cur.fetchall()
print(f"\nFound {len(corrections)} CORRECTION entries\n")

matches = []
for rec_id, rec_date, rec_amount, rec_desc in corrections:
    # Try to find matching banking transaction by amount
    abs_amount = abs(float(rec_amount))
    cur.execute("""
        SELECT bt.transaction_id, bt.transaction_date, 
               COALESCE(bt.debit_amount, 0) as db_amt, COALESCE(bt.credit_amount, 0) as cr_amt,
               bt.description, bt.reconciliation_status
        FROM banking_transactions bt
        WHERE (COALESCE(bt.debit_amount, 0) = %s OR COALESCE(bt.credit_amount, 0) = %s)
        AND bt.transaction_date BETWEEN %s - INTERVAL '5 days' AND %s + INTERVAL '5 days'
        ORDER BY bt.transaction_date DESC
        LIMIT 3
    """, (abs_amount, abs_amount, rec_date, rec_date))

    banking = cur.fetchall()
    
    print(f"Receipt {rec_id}: {rec_date} | ${rec_amount:.2f}")
    if banking:
        for bt in banking:
            bank_amt = bt[2] if bt[2] > 0 else bt[3]
            print(f"  ✓ Match: {bt[1]} | ${bank_amt:.2f} | {bt[5]} | {bt[4][:50]}")
            matches.append({
                'receipt_id': rec_id,
                'receipt_date': rec_date.isoformat(),
                'receipt_amount': float(rec_amount),
                'banking_id': bt[0],
                'banking_date': bt[1].isoformat(),
                'banking_amount': bank_amt,
                'banking_status': bt[5],
                'banking_desc': bt[4]
            })
    else:
        print(f"  ✗ No banking match found")
    print()

# Export matches
if matches:
    csv_path = f"reports/correction_banking_matches_{len(matches)}_of_{len(corrections)}.csv"
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=matches[0].keys())
        writer.writeheader()
        writer.writerows(matches)
    print(f"\n✅ Exported {len(matches)} matches to {csv_path}")

cur.close()
conn.close()

print(f"\n📊 Summary: {len(matches)}/{len(corrections)} CORRECTION entries matched to banking")
