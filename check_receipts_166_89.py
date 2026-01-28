import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)

cur = conn.cursor()

cur.execute("""
    SELECT 
        receipt_id, 
        receipt_date, 
        vendor_name, 
        gross_amount,
        COALESCE(gl_account_name, gl_account_code::text, '') as gl,
        COALESCE(description, '') as description,
        banking_transaction_id,
        COALESCE(split_group_id, 0) as split_group,
        COALESCE(reserve_number, '') as reserve_num
    FROM receipts 
    WHERE receipt_id IN (157740, 140762, 140761)
    ORDER BY receipt_id
""")

rows = cur.fetchall()

print('\n=== Receipt Details for $166.89 total ===\n')
print(f"{'ID':<8} {'Date':<12} {'Vendor':<10} {'Amount':<10} {'GL Category':<40} {'Description':<40} {'Banking':<10} {'Split':<6} {'Reserve':<10}")
print('-' * 160)

for r in rows:
    print(f"{r[0]:<8} {str(r[1]):<12} {r[2]:<10} ${r[3]:>7.2f}   {r[4]:<40} {r[5][:38]:<40} {str(r[6]) if r[6] else 'None':<10} {r[7]:<6} {r[8]:<10}")

print(f"\nTotal: ${sum(r[3] for r in rows):.2f}")

# Check if any share the same banking transaction
print("\n=== Banking Transaction Check ===")
banking_ids = [r[6] for r in rows if r[6]]
if len(banking_ids) != len(set(banking_ids)):
    print("⚠️  WARNING: Multiple receipts linked to the same banking transaction!")
    for bid in set(banking_ids):
        count = banking_ids.count(bid)
        if count > 1:
            print(f"   Banking ID {bid} is linked to {count} receipts")
else:
    print(f"✅ All {len(banking_ids)} receipts have unique banking links")

# Check split groups
print("\n=== Split Group Check ===")
split_groups = [(r[0], r[7]) for r in rows]
for rid, sg in split_groups:
    if sg > 0:
        print(f"Receipt {rid} is in split group {sg}")
    else:
        print(f"Receipt {rid} is NOT in a split group")

cur.close()
conn.close()
