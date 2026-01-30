import os
import psycopg2


def get_conn():
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        dbname=os.environ.get("DB_NAME", "almsdata"),
        user=os.environ.get("DB_USER", "postgres"),
        password=os.environ.get("DB_PASSWORD", "***REDACTED***"),
    )


conn = get_conn()
cur = conn.cursor()

print("=== ALL MISCLASSIFIED TRANSACTIONS (1615 from GL 1000) ===\n")
cur.execute(
    """
    SELECT COUNT(*) 
    FROM banking_transactions 
    WHERE source_file ILIKE '%general_ledger%1000%1615%'
    """
)
print(f"Total count: {cur.fetchone()[0]}\n")

cur.execute(
    """
    SELECT transaction_id, transaction_date, description, account_number, bank_id, 
           credit_amount, debit_amount, balance, source_file
    FROM banking_transactions 
    WHERE source_file ILIKE '%general_ledger%1000%1615%'
    ORDER BY transaction_date, transaction_id
    """
)
print("transaction_id | date       | description                              | acct | bank_id | debit   | credit  | balance")
print("-" * 140)
for r in cur.fetchall():
    desc = (r[2] or '')[:40].ljust(40)
    debit_str = str(r[6]) if r[6] is not None else 'NULL'
    credit_str = str(r[5]) if r[5] is not None else 'NULL'
    balance_str = str(r[7]) if r[7] is not None else 'NULL'
    print(f"{r[0]:<14} | {r[1]} | {desc} | {r[3]:<4} | {str(r[4] or 'NULL'):<7} | {debit_str:<7} | {credit_str:<7} | {balance_str}")

conn.close()
