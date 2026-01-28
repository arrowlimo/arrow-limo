import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)

cur = conn.cursor()

# Search for FAS GAS receipts on 2012-11-14
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
    WHERE vendor_name ILIKE '%FAS GAS%' 
      AND receipt_date = '2012-11-14'
    ORDER BY gross_amount, receipt_id
""")

rows = cur.fetchall()

print('\n=== ALL FAS GAS receipts on 2012-11-14 ===\n')
print(f"{'ID':<8} {'Amount':<10} {'GL Category':<40} {'Description':<40} {'Banking':<10}")
print('-' * 120)

for r in rows:
    print(f"{r[0]:<8} ${r[3]:>7.2f}   {r[4]:<40} {r[5][:38]:<40} {str(r[6]) if r[6] else 'None':<10}")

print(f"\nTotal FAS GAS receipts: {len(rows)}")
print(f"Total amount: ${sum(r[3] for r in rows):.2f}")

cur.close()
conn.close()
