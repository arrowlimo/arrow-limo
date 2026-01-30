#!/usr/bin/env python3
"""Show receipt PDFs and extracted data"""
import psycopg2
import os

DSN = dict(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REDACTED***"),
    port=int(os.environ.get("DB_PORT", "5432")),
)

conn = psycopg2.connect(**DSN)
cur = conn.cursor()

print("\n" + "="*90)
print("RECEIPT PDFs - EXTRACTED DATA")
print("="*90)

cur.execute("""
    SELECT file_name, extracted_data, year_detected
    FROM pdf_staging 
    WHERE category='receipt' 
    AND extracted_data IS NOT NULL
    ORDER BY file_name
""")

receipts = cur.fetchall()

print(f"\n📋 Found {len(receipts)} receipt PDFs\n")
print(f"{'File Name':<50} {'Amount':>12} {'Vendor':<25}")
print("-"*90)

total_amount = 0
count_with_amount = 0

for file_name, data, year in receipts:
    if data and 'amount' in data:
        amount = data.get('amount', 0)
        vendor = data.get('vendor', 'N/A')[:23]
        date = data.get('date', 'N/A')
        invoice = data.get('invoice_number', '')
        
        print(f"{file_name[:48]:<50} ${amount:>11.2f} {vendor:<25}")
        
        if invoice:
            print(f"  → Invoice: {invoice}, Date: {date}")
        
        total_amount += amount
        count_with_amount += 1

print("-"*90)
print(f"{'TOTAL':<50} ${total_amount:>11.2f} ({count_with_amount} receipts with amounts)")

print(f"\n📊 Receipt Types Detected:")
cur.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(CASE WHEN extracted_data->>'amount' IS NOT NULL THEN 1 END) as has_amount,
        COUNT(CASE WHEN extracted_data->>'vendor' IS NOT NULL THEN 1 END) as has_vendor,
        COUNT(CASE WHEN extracted_data->>'date' IS NOT NULL THEN 1 END) as has_date,
        COUNT(CASE WHEN extracted_data->>'invoice_number' IS NOT NULL THEN 1 END) as has_invoice
    FROM pdf_staging
    WHERE category = 'receipt'
""")

stats = cur.fetchone()
print(f"  Total receipts:     {stats[0]}")
print(f"  With amounts:       {stats[1]}")
print(f"  With vendor names:  {stats[2]}")
print(f"  With dates:         {stats[3]}")
print(f"  With invoice #:     {stats[4]}")

cur.close()
conn.close()
