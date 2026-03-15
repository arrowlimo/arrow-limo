#!/usr/bin/env python3
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

# Check all CO-OP receipts and their banking descriptions for keywords
cur.execute("""
    SELECT 
        r.vendor_name,
        bt.description as banking_desc,
        COUNT(*) as cnt
    FROM receipts r
    LEFT JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
    WHERE (r.vendor_name ILIKE '%co-op%' OR r.vendor_name ILIKE '%coop%')
      AND r.vendor_name NOT ILIKE '%insurance%'
      AND bt.description IS NOT NULL
    GROUP BY r.vendor_name, bt.description
    ORDER BY cnt DESC
""")

print("CO-OP TRANSACTION PATTERNS")
print("=" * 100)
print(f"{'Count':<8} | {'Vendor':<30} | {'Banking Description'}")
print("-" * 100)

gas_bar_count = 0
hgc_count = 0
liquor_count = 0
store_count = 0
other_count = 0

for row in cur.fetchall():
    vendor, banking_desc, cnt = row
    print(f"{cnt:<8} | {vendor:<30} | {banking_desc[:65]}")
    
    # Categorize based on keywords
    desc_upper = banking_desc.upper()
    if 'GAETZ G' in desc_upper or 'GAS' in desc_upper or 'FUEL' in desc_upper:
        gas_bar_count += cnt
    elif 'LIQUOR' in desc_upper or 'WINE' in desc_upper or 'BEER' in desc_upper:
        liquor_count += cnt
    elif 'HGC' in desc_upper or 'HOME' in desc_upper or 'GARDEN' in desc_upper:
        hgc_count += cnt
    elif 'FOOD' in desc_upper or 'GROCERY' in desc_upper or 'STORE' in desc_upper:
        store_count += cnt
    else:
        other_count += cnt

print("\n" + "=" * 100)
print("CATEGORY SUMMARY")
print("=" * 100)
print(f"Gas Bar receipts: {gas_bar_count}")
print(f"Liquor receipts: {liquor_count}")
print(f"HGC receipts: {hgc_count}")
print(f"Store receipts: {store_count}")
print(f"Other/Unknown: {other_count}")

cur.close()
conn.close()
