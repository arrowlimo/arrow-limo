import psycopg2

MONTH_END_SQL = """
WITH m AS (
    SELECT transaction_date, description, balance, debit_amount, credit_amount,
                 date_trunc('month', transaction_date) AS mth,
                 ROW_NUMBER() OVER (
                         PARTITION BY date_trunc('month', transaction_date)
                         ORDER BY transaction_date DESC, transaction_id DESC
                 ) AS rn
    FROM banking_transactions
    WHERE account_number = %s
        AND transaction_date BETWEEN %s AND %s
)
SELECT to_char(mth,'YYYY-MM') AS month,
             transaction_date,
             description,
             balance,
             debit_amount,
             credit_amount
FROM m
WHERE rn = 1
ORDER BY month;
"""

COUNT_SQL = """
SELECT to_char(date_trunc('month', transaction_date),'YYYY-MM') AS month,
             COUNT(*) AS rows,
             MIN(transaction_date) AS first_date,
             MAX(transaction_date) AS last_date,
             MIN(balance) AS min_balance,
             MAX(balance) AS max_balance
FROM banking_transactions
WHERE account_number = %s
    AND transaction_date BETWEEN %s AND %s
GROUP BY 1
ORDER BY 1;
"""

ACCOUNT = '903990106011'
START = '2012-01-01'
END = '2012-03-31'

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='ArrowLimousine')
cur = conn.cursor()

print('Month-end rows:')
cur.execute(MONTH_END_SQL, (ACCOUNT, START, END))
for row in cur.fetchall():
        print(row)

print('\nCounts by month:')
cur.execute(COUNT_SQL, (ACCOUNT, START, END))
for row in cur.fetchall():
        print(row)

cur.close()
conn.close()
