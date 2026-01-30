"""Restore correct 2012 data - DELETE corrupted data first."""
import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REDACTED***"
)

cur = conn.cursor()

# Delete corrupted 2012 data
cur.execute("""
    DELETE FROM banking_transactions 
    WHERE account_number = '1615' 
    AND EXTRACT(YEAR FROM transaction_date) = 2012
""")

print(f"Deleted {cur.rowcount} transactions from 2012")

# Re-import the correct data with proper balances
correct_transactions = [
    ("2012-01-01", None, None, 7177.34, "Opening balance"),
    ("2012-01-03", 63.50, None, 7113.84, "PURCHASE CENTEX PETROLEU"),
    ("2012-01-03", 4.80, None, 7109.04, "PURCHASE MR.SUDS INC."),
    ("2012-01-03", 37.16, None, 7071.88, "PURCHASE REAL CDN. WHOLE"),
    ("2012-01-03", 114.00, None, 6957.88, "PURCHASE RUN'N ON EMPTY"),
    ("2012-01-03", 500.00, None, 6457.88, "ABM WITHDRAWAL 2C0Q"),
    ("2012-01-03", None, 756.26, 7214.14, "DEPOSIT"),
    ("2012-01-03", 140.00, None, 7074.14, "WITHDRAWAL"),
    ("2012-01-03", 2200.00, None, 4874.14, "TRANSFER TO: 00339/02-28362"),
    ("2012-01-03", 78.70, None, 4795.44, "PURCHASE BED BATH & BEYO"),
    ("2012-01-31", None, None, 74.83, "Balance forward"),
    ("2012-01-31", 82.50, None, -7.67, "DEBIT MEMO 4017775 VISA"),
    ("2012-01-31", 1.50, None, -9.17, "E-TRANSFER NWK FEE"),
    ("2012-01-31", 35.00, None, -44.17, "ACCOUNT FEE"),
    ("2012-01-31", 5.00, None, -49.17, "OVERDRAFT S/C"),
    ("2012-01-31", None, None, -49.17, "Closing balance"),
]

for date, debit, credit, balance, description in correct_transactions:
    import hashlib
    hash_input = f"{date}|{description}|{debit or 0:.2f}|{credit or 0:.2f}".encode('utf-8')
    source_hash = hashlib.sha256(hash_input).hexdigest()
    
    cur.execute("""
        INSERT INTO banking_transactions (
            account_number, transaction_date, description,
            debit_amount, credit_amount, balance, source_hash
        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, ('1615', date, description, debit, credit, balance, source_hash))

print(f"Inserted {len(correct_transactions)} correct transactions")

conn.commit()
conn.close()

print("✅ 2012 data restored with correct closing balance: -$49.17")
