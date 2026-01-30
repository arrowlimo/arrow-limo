#!/usr/bin/env python3
"""List staged receipt PDFs with extracted amounts and vendors, plus totals"""
import os
import psycopg2

DSN = dict(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REDACTED***"),
    port=int(os.environ.get("DB_PORT", "5432")),
)

conn = psycopg2.connect(**DSN)
cur = conn.cursor()

print("\n" + "="*70)
print("STAGED RECEIPTS (from pdf_staging)")
print("="*70)

cur.execute("""
    SELECT file_name, extracted_data
    FROM pdf_staging
    WHERE category='receipt' AND extracted_data IS NOT NULL
    ORDER BY file_name
    LIMIT 50
""")

rows = cur.fetchall()
print(f"Found {len(rows)} sample rows (showing up to 50):\n")
print(f"{'File Name':<50} {'Amount':>12}  {'Vendor':<30}")
print("-"*95)

total = 0.0
count = 0
for file_name, data in rows:
    amt = 0.0
    vendor = ''
    if isinstance(data, dict):
        if 'amount' in data:
            try:
                amt = float(data['amount'])
            except Exception:
                amt = 0.0
        vendor = (data.get('vendor') or '')[:30]
    count += 1
    total += amt
    print(f"{file_name[:48]:<50} {amt:>12.2f}  {vendor:<30}")

# Totals across all receipts with amount
cur.execute("""
    SELECT COUNT(*), SUM(CAST(extracted_data->>'amount' AS FLOAT))
    FROM pdf_staging
    WHERE category='receipt' AND extracted_data->>'amount' IS NOT NULL
""")
all_count, all_sum = cur.fetchone()
print("-"*95)
print(f"Shown: {count}   Sum: {total:.2f}")
print(f"ALL RECEIPTS WITH AMOUNT -> Count: {all_count}   Sum: {all_sum or 0:.2f}")

cur.close()
conn.close()
