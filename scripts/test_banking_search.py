import psycopg2

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='***REMOVED***'
)

# Simulate the exact search the user is doing:
# - Scotia bank (account 903990106011)
# - Date range: 2012-09-12 to 2012-09-20
# - Amount: 49.05
# - Vendor: (empty/not specified)

sql = """
    SELECT 
        bt.transaction_id,
        bt.transaction_date,
        bt.description,
        bt.debit_amount,
        bt.credit_amount,
        bt.check_number,
        bt.category,
        CASE 
            WHEN EXISTS (
                SELECT 1 FROM receipts r 
                WHERE r.banking_transaction_id = bt.transaction_id
            ) THEN '✅ Linked'
            ELSE '❌ Unlinked'
        END as link_status
    FROM banking_transactions bt
    WHERE 1=1
"""

params = []

# Bank account filter (Scotia = 2)
bank_account_id = 2
if bank_account_id == 2:
    sql += " AND bt.account_number = %s"
    params.append('903990106011')

# Date range filter
date_from = '2012-09-12'
date_to = '2012-09-20'
sql += " AND bt.transaction_date BETWEEN %s AND %s"
params.append(date_from)
params.append(date_to)

# Amount filter
amount = 49.05
if amount > 0:
    sql += " AND (ABS(bt.debit_amount - %s) < 0.01 OR ABS(bt.credit_amount - %s) < 0.01)"
    params.append(amount)
    params.append(amount)

# NO vendor filter (user says they tried without it)

# Order by date descending, limit to 100
sql += " ORDER BY bt.transaction_date DESC LIMIT 100"

print("SQL Query:")
print(sql)
print("\nParameters:")
print(params)
print("\n" + "="*80 + "\n")

cur = conn.cursor()
cur.execute(sql, params)
results = cur.fetchall()

print(f"Found {len(results)} transactions:\n")
for row in results:
    print(f"ID: {row[0]}")
    print(f"Date: {row[1]}")
    print(f"Description: {row[2]}")
    print(f"Debit: ${row[3] or 0:.2f}")
    print(f"Credit: ${row[4] or 0:.2f}")
    print(f"Check: {row[5]}")
    print(f"Category: {row[6]}")
    print(f"Status: {row[7]}")
    print("-" * 80)

conn.close()
