import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

# Insert the missing 2014-12-29 transaction
cur.execute("""
    INSERT INTO banking_transactions (
        account_number, transaction_date, description,
        debit_amount, credit_amount, balance,
        source_file, import_batch, created_at
    ) VALUES (
        '903990106011',
        '2014-12-29',
        '12/29/2014 G-49416-90399 ATTACHMENT ORDER',
        390.80,
        NULL,
        0.00,
        'verified_2013_2014_scotia',
        'scotia_verified_manual_correction',
        NOW()
    )
    RETURNING transaction_id
""")

new_id = cur.fetchone()[0]
conn.commit()

print(f"✅ Added missing transaction:")
print(f"   Transaction ID: {new_id}")
print(f"   Date: 2014-12-29")
print(f"   Description: 12/29/2014 G-49416-90399 ATTACHMENT ORDER")
print(f"   Debit: $390.80")
print(f"   Balance: $0.00")

# Verify total count
cur.execute("""
    SELECT COUNT(*) 
    FROM banking_transactions 
    WHERE account_number = '903990106011' 
      AND EXTRACT(YEAR FROM transaction_date) IN (2013, 2014)
""")
count = cur.fetchone()[0]
print(f"\n📊 Total 2013-2014 Scotia transactions: {count}")

cur.close()
conn.close()
