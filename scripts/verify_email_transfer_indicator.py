import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print("CHECKING EMAIL TRANSFER INDICATOR AFTER EXTRACTION")
print("="*100)

# Check what happened to EMAIL TRANSFER vendor names
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
    LIMIT 30
""")

print("\nVendor names for EMAIL TRANSFER transactions:")
print(f"{'Vendor Name':<50} | {'Count':>6}")
print("-"*60)

results = cur.fetchall()
for vendor, count in results:
    print(f"{vendor[:48]:<50} | {count:>6}")

# Count how many still say "EMAIL TRANSFER" vs extracted names
still_generic = sum(c for v, c in results if v in ('EMAIL TRANSFER', 'E-TRANSFER'))
extracted = sum(c for v, c in results if v not in ('EMAIL TRANSFER', 'E-TRANSFER'))

print(f"\n{'='*100}")
print(f"PROBLEM IDENTIFIED:")
print(f"{'='*100}")
print(f"""
Still generic "EMAIL TRANSFER": {still_generic} receipts
Extracted recipient names: {extracted} receipts

⚠️  We lost the "EMAIL TRANSFER" transaction type indicator!
   Now we just have recipient names, but can't easily identify which were email transfers.
""")

# Check if receipts table has payment_method field
cur.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name = 'receipts' 
      AND column_name LIKE '%method%' OR column_name LIKE '%type%'
""")

method_columns = cur.fetchall()
print(f"Existing method/type columns in receipts table:")
for col in method_columns:
    print(f"  - {col[0]}")

if not method_columns:
    print(f"  (none found)")

print(f"\n{'='*100}")
print(f"SOLUTION:")
print(f"{'='*100}")
print(f"""
Option 1: Keep vendor_name format as "EMAIL TRANSFER - [Recipient]"
  - Preserves transaction type indicator
  - Searchable by recipient name
  - Example: "EMAIL TRANSFER - Richard Gursky"

Option 2: Add payment_method column
  - vendor_name = recipient name only
  - payment_method = 'EMAIL_TRANSFER', 'CHEQUE', 'CASH', 'CARD', etc.
  - Clean separation of concerns

RECOMMENDED: Option 1 (simpler, no schema change required)
""")

cur.close()
conn.close()
