import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

print("CHECKING 2019 RECEIPTS AND SPLIT PATTERN")
print("="*80)

# Check 2019 receipt count
cur.execute("SELECT COUNT(*) FROM receipts WHERE EXTRACT(YEAR FROM receipt_date) = 2019")
total_2019 = cur.fetchone()[0]
print(f"\nTotal 2019 receipts: {total_2019:,}")

# Check if you mean something else by "split"
cur.execute("""
    SELECT 
        vendor_name,
        COUNT(*) as count,
        COUNT(DISTINCT banking_transaction_id) as unique_banking
    FROM receipts
    WHERE EXTRACT(YEAR FROM receipt_date) = 2019
      AND vendor_name LIKE '%SPLIT%'
    GROUP BY vendor_name
""")

split_named = cur.fetchall()
if split_named:
    print(f"\nReceipts with 'SPLIT' in vendor name:")
    for vendor, count, unique_banking in split_named:
        print(f"  {vendor}: {count} receipts, {unique_banking} banking TXs")
else:
    print("\nNo receipts with 'SPLIT' in vendor name")

# Check for duplicate amounts on same date (manual splits?)
cur.execute("""
    SELECT 
        receipt_date,
        gross_amount,
        COUNT(*) as count,
        STRING_AGG(vendor_name, ' | ') as vendors,
        STRING_AGG(receipt_id::text, ', ') as receipt_ids
    FROM receipts
    WHERE EXTRACT(YEAR FROM receipt_date) = 2019
    GROUP BY receipt_date, gross_amount
    HAVING COUNT(*) > 1
    ORDER BY COUNT(*) DESC, gross_amount DESC
    LIMIT 20
""")

same_date_amount = cur.fetchall()
if same_date_amount:
    print(f"\n2019 receipts with same date + amount (possible manual splits):")
    print(f"{'Date':<12} | {'Amount':>10} | Count | Vendors")
    print("-"*80)
    for date, amount, count, vendors, receipt_ids in same_date_amount[:10]:
        print(f"{str(date):<12} | ${float(amount):>9,.2f} | {count:>5} | {vendors[:50]}")

# Check notes/description fields
cur.execute("""
    SELECT COUNT(*) 
    FROM receipts
    WHERE EXTRACT(YEAR FROM receipt_date) = 2019
      AND (notes ILIKE '%split%' OR vendor_name ILIKE '%split%')
""")

split_in_notes = cur.fetchone()[0]
if split_in_notes:
    print(f"\n2019 receipts with 'split' in notes/vendor: {split_in_notes}")
    
    cur.execute("""
        SELECT receipt_id, vendor_name, gross_amount, notes
        FROM receipts
        WHERE EXTRACT(YEAR FROM receipt_date) = 2019
          AND (notes ILIKE '%split%' OR vendor_name ILIKE '%split%')
        LIMIT 10
    """)
    
    for receipt_id, vendor, amount, notes in cur.fetchall():
        print(f"  Receipt {receipt_id}: {vendor} ${float(amount):,.2f}")
        if notes:
            print(f"    Notes: {notes[:100]}")

cur.close()
conn.close()
