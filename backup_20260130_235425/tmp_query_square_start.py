import psycopg2

def main():
    conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='ArrowLimousine')
    cur = conn.cursor()
    cur.execute("SELECT MIN(transaction_date) FROM banking_transactions WHERE description ILIKE '%SQUARE%'")
    min_date = cur.fetchone()[0]
    print(f"First Square transaction date: {min_date}")
    cur.execute("""
        SELECT transaction_id, transaction_date, description,
               COALESCE(credit_amount, debit_amount) AS amt
        FROM banking_transactions
        WHERE description ILIKE '%SQUARE%'
        ORDER BY transaction_date ASC
        LIMIT 10
    """)
    rows = cur.fetchall()
    print("Earliest 10 Square entries:")
    for r in rows:
        print(f"{r[1]} | ID={r[0]} | amt={r[3]} | {r[2]}")
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
