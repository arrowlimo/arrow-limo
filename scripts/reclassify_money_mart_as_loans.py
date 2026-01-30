"""
Reclassify Money Mart and payday loan receipts as Loan Proceeds (Withdrawal)
"""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

print("=" * 100)
print("RECLASSIFY MONEY MART / PAYDAY LOANS")
print("=" * 100)

# Update Money Mart and payday loan receipts
cur.execute("""
    UPDATE receipts
    SET category = 'Loan Proceeds',
        business_personal = 'Business'
    WHERE banking_transaction_id IN (
        SELECT transaction_id
        FROM banking_transactions
        WHERE bank_id = 1
        AND source_file = '2014-2017 CIBC 8362.xlsx'
    )
    AND (
        UPPER(vendor_name) LIKE '%MONEY MART%'
        OR UPPER(vendor_name) LIKE '%CASH MONEY%'
        OR UPPER(vendor_name) LIKE '%PAYDAY%'
    )
    RETURNING receipt_id, vendor_name, gross_amount, category, business_personal
""")

updated = cur.fetchall()

conn.commit()

print(f"\n✅ Updated {len(updated)} receipts\n")

if updated:
    print(f"{'Vendor':<40} {'Amount':<15} {'Category':<20} {'Type':<15}")
    print("-" * 100)
    for rid, vendor, amount, category, biz_personal in updated[:20]:
        print(f"{vendor[:40]:<40} ${amount:>13,.2f} {category:<20} {biz_personal:<15}")
    
    if len(updated) > 20:
        print(f"\n... and {len(updated) - 20} more")

cur.close()
conn.close()

print(f"\n✅ Reclassified {len(updated)} Money Mart/payday loan receipts as 'Loan Proceeds (Withdrawal)'")
