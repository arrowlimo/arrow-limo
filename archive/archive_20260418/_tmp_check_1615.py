import psycopg2

conn = psycopg2.connect(host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine')
cur = conn.cursor()

# Check vendor_accounts with id 1615
cur.execute("SELECT account_id, account_name, canonical_vendor FROM vendor_accounts WHERE account_id = 1615 LIMIT 5")
rows = cur.fetchall()
print('Vendor account id=1615:', rows)

# Count receipts for vendor_account_id=1615
cur.execute("SELECT COUNT(*), MIN(receipt_date), MAX(receipt_date), SUM(gross_amount) FROM receipts WHERE vendor_account_id = 1615")
row = cur.fetchone()
print('Receipts for acct 1615: count=%s, min_date=%s, max_date=%s, total=%s' % row)

# Check receipts for 2012 specifically
cur.execute("SELECT COUNT(*) FROM receipts WHERE vendor_account_id = 1615 AND receipt_date >= '2012-01-01' AND receipt_date < '2013-01-01'")
print('2012 receipts for acct 1615:', cur.fetchone()[0])

# Check receipt_banking_links for vendor 1615
cur.execute("""
    SELECT COUNT(*)
    FROM receipt_banking_links rbl
    JOIN receipts r ON r.receipt_id = rbl.receipt_id
    WHERE r.vendor_account_id = 1615
""")
print('Banking links for vendor 1615:', cur.fetchone()[0])

# Check 2012 receipt_banking_links
cur.execute("""
    SELECT COUNT(*)
    FROM receipt_banking_links rbl
    JOIN receipts r ON r.receipt_id = rbl.receipt_id
    WHERE r.vendor_account_id = 1615
    AND r.receipt_date >= '2012-01-01' AND r.receipt_date < '2013-01-01'
""")
print('2012 banking links for vendor 1615:', cur.fetchone()[0])

conn.close()
