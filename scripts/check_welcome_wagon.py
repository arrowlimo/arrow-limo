import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print("=" * 80)
print("RECEIPTS related to Welcome Wagon:")
print("=" * 80)
cur.execute("""
    SELECT receipt_id, receipt_date, vendor_name, gross_amount, 
           description, payment_method, category
    FROM receipts 
    WHERE vendor_name ILIKE '%welcome%wagon%'
       OR description ILIKE '%welcome%wagon%'
    ORDER BY receipt_date, receipt_id
""")
receipts = cur.fetchall()
for r in receipts:
    print(f"Receipt ID: {r[0]}")
    print(f"  Date: {r[1]}")
    print(f"  Vendor: {r[2]}")
    print(f"  Amount: ${r[3]}")
    print(f"  Payment Method: {r[4]}")
    print(f"  Category: {r[5]}")
    print(f"  Description: {r[6]}")
    print()

print("=" * 80)
print("BANKING TRANSACTIONS related to Welcome Wagon:")
print("=" * 80)
cur.execute("""
    SELECT transaction_id, transaction_date, description, 
           debit_amount, credit_amount
    FROM banking_transactions 
    WHERE description ILIKE '%welcome%wagon%'
    ORDER BY transaction_date, transaction_id
""")
banking = cur.fetchall()
for b in banking:
    print(f"Banking ID: {b[0]}")
    print(f"  Date: {b[1]}")
    print(f"  Description: {b[2]}")
    print(f"  Debit: ${b[3] if b[3] else 0}")
    print(f"  Credit: ${b[4] if b[4] else 0}")
    print()

print("=" * 80)
print("NSF-RELATED TRANSACTIONS (March 2012):")
print("=" * 80)
cur.execute("""
    SELECT transaction_id, transaction_date, description, 
           debit_amount, credit_amount
    FROM banking_transactions 
    WHERE transaction_date BETWEEN '2012-03-01' AND '2012-03-31'
      AND (description ILIKE '%nsf%' OR description ILIKE '%non-sufficient%')
    ORDER BY transaction_date, transaction_id
""")
nsf = cur.fetchall()
for n in nsf:
    print(f"NSF Transaction ID: {n[0]}")
    print(f"  Date: {n[1]}")
    print(f"  Description: {n[2]}")
    print(f"  Debit: ${n[3] if n[3] else 0}")
    print(f"  Credit: ${n[4] if n[4] else 0}")
    print()

conn.close()
