import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

print("RESTORING EMAIL TRANSFER INDICATOR WITH RECIPIENT NAMES")
print("="*100)

# Update extracted recipient names to include "EMAIL TRANSFER - " prefix
cur.execute("""
    UPDATE receipts r
    SET vendor_name = 'EMAIL TRANSFER - ' || r.vendor_name
    FROM banking_transactions bt
    WHERE r.banking_transaction_id = bt.transaction_id
      AND r.exclude_from_reports = FALSE
      AND (bt.description ILIKE '%E-TRANSFER%' OR bt.description ILIKE '%EMAIL TRANSFER%')
      AND r.vendor_name NOT LIKE 'EMAIL TRANSFER%'
      AND r.vendor_name NOT LIKE 'E-TRANSFER%'
      AND r.vendor_name != 'EMAIL TRANSFER FEE'
      AND r.vendor_name != 'E-Transfer Fee'
""")

updated_count = cur.rowcount
print(f"Updated {updated_count} receipts to include 'EMAIL TRANSFER - ' prefix")

conn.commit()

# Verify results
cur.execute("""
    SELECT vendor_name, COUNT(*) 
    FROM receipts 
    WHERE exclude_from_reports=FALSE 
      AND banking_transaction_id IN (
          SELECT transaction_id 
          FROM banking_transactions 
          WHERE description ILIKE '%E-TRANSFER%' OR description ILIKE '%EMAIL TRANSFER%'
      )
    GROUP BY vendor_name 
    ORDER BY COUNT(*) DESC 
    LIMIT 20
""")

print(f"\nVendor names after restoration:")
print(f"{'Vendor Name':<60} | {'Count':>6}")
print("-"*70)

results = cur.fetchall()
for vendor, count in results:
    print(f"{vendor[:58]:<60} | {count:>6}")

# Count generic vs with names
still_generic = sum(c for v, c in results if v in ('EMAIL TRANSFER', 'E-TRANSFER', 'EMAIL TRANSFER FEE', 'E-Transfer Fee'))
with_names = sum(c for v, c in results if v.startswith('EMAIL TRANSFER - '))

print(f"\n{'='*100}")
print(f"RESULTS:")
print(f"{'='*100}")
print(f"""
Generic "EMAIL TRANSFER" (no recipient extracted): {still_generic} receipts
With recipient names "EMAIL TRANSFER - [Name]": {with_names} receipts

✅ Transaction type indicator restored!
   - Can search by recipient: vendor_name LIKE '%Richard Gursky%'
   - Can filter by type: vendor_name LIKE 'EMAIL TRANSFER%'
   - Fully searchable and categorizable
""")

cur.close()
conn.close()
