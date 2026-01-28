import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api import get_db_connection

conn = get_db_connection()
cur = conn.cursor()

cur.execute("""
    SELECT transaction_date, debit_amount, credit_amount, description 
    FROM banking_transactions 
    WHERE account_number = '903990106011' 
    AND transaction_date BETWEEN '2013-06-24' AND '2013-06-30'
    ORDER BY transaction_date
""")

rows = cur.fetchall()
print(f"\nFound {len(rows)} transactions for June 24-30, 2013:\n")
for r in rows:
    d = f"${r[1]:.2f}" if r[1] else ""
    c = f"${r[2]:.2f}" if r[2] else ""
    print(f"{r[0]} | Debit: {d:>10} Credit: {c:>10} | {r[3][:50]}")

conn.close()
