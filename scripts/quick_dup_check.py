import psycopg2
conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

cur.execute("""
    SELECT 
        receipt_date, vendor_name, gross_amount,
        ARRAY_AGG(receipt_id), ARRAY_AGG(banking_transaction_id)
    FROM receipts
    WHERE exclude_from_reports = FALSE
    GROUP BY receipt_date, vendor_name, gross_amount
    HAVING COUNT(*) > 1
    ORDER BY gross_amount DESC
    LIMIT 10
""")

print("Top 10 remaining duplicate sets:")
print("="*70)

for date, vendor, amount, rec_ids, bank_ids in cur.fetchall():
    unique_banks = [b for b in bank_ids if b is not None]
    unique_banks = list(set(unique_banks))
    
    print(f"\n{date} | {vendor} | ${amount}")
    print(f"  Receipts: {rec_ids}")
    print(f"  Banking IDs: {bank_ids}")
    
    if len(unique_banks) == len(rec_ids):
        print(f"  ✅ OK: Each has different banking TX")
    elif len(unique_banks) == 0:
        print(f"  ❌ DUPLICATES: No banking links")
    else:
        print(f"  ⚠️  {len(unique_banks)} banking for {len(rec_ids)} receipts")

cur.close()
conn.close()
