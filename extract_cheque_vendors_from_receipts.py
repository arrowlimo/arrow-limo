"""
Extract vendor names from receipts linked to banking transactions with "CHQ #" descriptions
These vendors should be used to update the banking transaction descriptions
"""

import psycopg2

conn = psycopg2.connect(
    dbname="almsdata",
    user="postgres",
    password="ArrowLimousine",
    host="localhost"
)
cur = conn.cursor()

# Get vendor names from receipts linked to banking transactions with CHQ descriptions
query = """
SELECT 
    SUBSTRING(bt.description FROM 'CHQ\\s+(\\d+)')::int as cheque_num,
    bt.transaction_id,
    bt.transaction_date,
    bt.description as current_description,
    r.vendor_name as receipt_vendor,
    bt.debit_amount
FROM banking_transactions bt
JOIN receipts r ON r.banking_transaction_id = bt.transaction_id
WHERE bt.debit_amount IS NOT NULL
  AND bt.description ILIKE '%chq%'
  AND (
    bt.description = 'CHQ' 
    OR bt.description ~ '^CHQ\\s+\\d+$'
    OR bt.description ~ '^CHEQUE\\s+\\d+$'
  )
  AND r.vendor_name IS NOT NULL
ORDER BY cheque_num, bt.transaction_date
"""

cur.execute(query)
results = cur.fetchall()

print("=" * 100)
print("CHEQUE VENDOR NAMES FROM RECEIPTS")
print("=" * 100)
print(f"\nFound {len(results)} cheques with vendor names in receipts:\n")

# Group by cheque number to handle duplicates
cheque_vendors = {}
for row in results:
    cheque_num, trans_id, date, current_desc, vendor, amount = row
    if cheque_num not in cheque_vendors:
        cheque_vendors[cheque_num] = []
    cheque_vendors[cheque_num].append({
        'trans_id': trans_id,
        'date': date,
        'vendor': vendor,
        'amount': amount,
        'current_desc': current_desc
    })

# Display organized by cheque number
print(f"{'Cheque #':<10} {'Date':<12} {'Trans ID':<10} {'Amount':<15} Vendor Name")
print("-" * 100)

for cheque_num in sorted(cheque_vendors.keys()):
    entries = cheque_vendors[cheque_num]
    for entry in entries:
        print(f"{cheque_num:<10} {str(entry['date']):<12} {entry['trans_id']:<10} ${entry['amount']:>12,.2f} {entry['vendor']}")

# Generate UPDATE statements
print("\n" + "=" * 100)
print("UPDATE STATEMENTS TO APPLY:")
print("=" * 100)

updates = []
for cheque_num in sorted(cheque_vendors.keys()):
    entries = cheque_vendors[cheque_num]
    # Get the most common vendor name for this cheque number
    vendors_for_cheque = [e['vendor'] for e in entries]
    vendor = max(set(vendors_for_cheque), key=vendors_for_cheque.count)
    
    for entry in entries:
        new_desc = f"CHQ {cheque_num} {vendor}"
        if entry['current_desc'] != new_desc:
            updates.append((entry['trans_id'], new_desc, cheque_num, vendor))

print(f"\nTotal updates needed: {len(updates)}\n")
for trans_id, new_desc, cheque_num, vendor in updates[:20]:
    print(f"UPDATE banking_transactions SET description = 'CHQ {cheque_num} {vendor}' WHERE transaction_id = {trans_id};")

if len(updates) > 20:
    print(f"\n... and {len(updates) - 20} more")

conn.close()
