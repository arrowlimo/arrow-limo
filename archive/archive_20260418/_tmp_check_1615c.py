import psycopg2

conn = psycopg2.connect(host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine')
cur = conn.cursor()

# Check vendor account 1615
cur.execute("SELECT account_id, canonical_vendor, display_name FROM vendor_accounts WHERE account_id = 1615 LIMIT 5")
rows = cur.fetchall()
print('Vendor account id=1615:', rows)

# Also check 61615
cur.execute("SELECT account_id, canonical_vendor, display_name FROM vendor_accounts WHERE account_id = 61615 LIMIT 5")
rows = cur.fetchall()
print('Vendor account id=61615:', rows)

# Receipts for vendor_account_id = 1615
cur.execute("SELECT COUNT(*), MIN(receipt_date), MAX(receipt_date), SUM(gross_amount) FROM receipts WHERE vendor_account_id = 1615")
row = cur.fetchone()
print('Receipts for acct 1615: count=%s, min=%s, max=%s, total=%s' % row)

# 2012 receipts for 1615
cur.execute("SELECT COUNT(*) FROM receipts WHERE vendor_account_id = 1615 AND receipt_date >= '2012-01-01' AND receipt_date < '2013-01-01'")
print('2012 receipts for acct 1615:', cur.fetchone()[0])

# 2012 banking links for 1615
cur.execute("""
    SELECT COUNT(*)
    FROM receipt_banking_links rbl
    JOIN receipts r ON r.receipt_id = rbl.receipt_id
    WHERE r.vendor_account_id = 1615
    AND r.receipt_date >= '2012-01-01' AND r.receipt_date < '2013-01-01'
""")
print('2012 banking links for vendor 1615:', cur.fetchone()[0])

# Also check receipt_banking_links table columns
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='receipt_banking_links' ORDER BY ordinal_position")
print('receipt_banking_links cols:', [r[0] for r in cur.fetchall()])

conn.close()
