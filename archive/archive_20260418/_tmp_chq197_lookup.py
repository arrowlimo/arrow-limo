"""
Look up vendor account for 106.7 The Drive / Big 105 radio advertising,
and check if a receipt already exists for CHQ 197 $550 Jan 3 2012.
"""
import psycopg2

conn = psycopg2.connect(host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine')
cur = conn.cursor()

# Find vendor accounts matching radio / 106.7 / drive / big 105
cur.execute("""
    SELECT account_id, canonical_vendor, display_name, default_gl_code, default_category
    FROM vendor_accounts
    WHERE canonical_vendor ILIKE '%106%'
       OR canonical_vendor ILIKE '%drive%'
       OR canonical_vendor ILIKE '%big 10%'
       OR canonical_vendor ILIKE '%radio%'
       OR display_name ILIKE '%106%'
       OR display_name ILIKE '%drive%'
       OR display_name ILIKE '%radio%'
    ORDER BY canonical_vendor
""")
rows = cur.fetchall()
print("Matching vendor accounts:")
for r in rows:
    print(f"  id={r[0]}  canonical={r[1]}  display={r[2]}  gl={r[3]}  cat={r[4]}")

# Check if a receipt already exists for this
cur.execute("""
    SELECT receipt_id, receipt_date, gross_amount, description, vendor_name, vendor_account_id
    FROM receipts
    WHERE receipt_date = '2012-01-03'
    AND gross_amount = 550.00
""")
rows = cur.fetchall()
print("\nExisting receipts 2012-01-03 $550:")
for r in rows:
    print(f"  receipt_id={r[0]} date={r[1]} amount={r[2]} vendor={r[4]} acct_id={r[5]} desc={r[3]}")

# Also check for any 106.7/radio receipts in 2012
cur.execute("""
    SELECT receipt_id, receipt_date, gross_amount, description, vendor_name, vendor_account_id
    FROM receipts
    WHERE receipt_date >= '2012-01-01' AND receipt_date < '2013-01-01'
    AND (vendor_name ILIKE '%106%' OR vendor_name ILIKE '%drive%' OR vendor_name ILIKE '%radio%'
         OR description ILIKE '%106%' OR description ILIKE '%radio%')
    ORDER BY receipt_date
""")
rows = cur.fetchall()
print("\nRadio/106 receipts in 2012:")
for r in rows:
    print(f"  receipt_id={r[0]} date={r[1]} amount={r[2]} vendor={r[4]} desc={r[3]}")

conn.close()
