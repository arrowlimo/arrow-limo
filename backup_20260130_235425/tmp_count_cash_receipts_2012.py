import psycopg2
import os

DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'almsdata')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', os.environ.get("DB_PASSWORD"))

def main():
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()

    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'receipts'
        ORDER BY ordinal_position
        """
    )
    cols = [r[0] for r in cur.fetchall()]
    print('Columns:', cols)

    payment_col = None
    for c in ['payment_method', 'payment_type', 'tender_type', 'payment_mode']:
        if c in cols:
            payment_col = c
            break

    if not payment_col:
        raise SystemExit('No payment column found on receipts table')

    print('Using payment column:', payment_col)

    cur.execute(
        f"""
        SELECT COUNT(*)
        FROM receipts
        WHERE {payment_col} = 'cash'
          AND receipt_date >= '2012-01-01'
          AND receipt_date < '2013-01-01'
        """
    )
    count = cur.fetchone()[0]
    print('Cash receipts in 2012:', count)

    conn.close()

if __name__ == '__main__':
    main()
