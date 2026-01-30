"""
List remaining payment mismatch charters excluding already fixed ones.
Criteria: charter where ABS(paid_amount - SUM(payments.amount)) > 0.01 OR SUM(payments.amount) > total_amount_due * 2
Exclude reserves: 016461, 017350, 018864, 017631
Outputs a ranked list and a CSV file.
"""
import psycopg2, os, csv

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST','localhost'),
        database=os.getenv('DB_NAME','almsdata'),
        user=os.getenv('DB_USER','postgres'),
        password=os.getenv('DB_PASSWORD','***REDACTED***')
    )

def main():
    conn = get_db_connection(); cur = conn.cursor()
    exclude = ('016461','017350','018864','017631')
    cur.execute("""
        WITH payment_totals AS (
            SELECT reserve_number, ROUND(SUM(amount)::numeric,2) AS actual_paid
            FROM payments
            GROUP BY reserve_number
        )
        SELECT c.reserve_number, c.charter_date, c.total_amount_due, c.paid_amount,
               COALESCE(pt.actual_paid,0) AS actual_paid,
               (COALESCE(pt.actual_paid,0) - c.total_amount_due) AS overpay
        FROM charters c
        JOIN payment_totals pt ON pt.reserve_number = c.reserve_number
        WHERE c.reserve_number NOT IN %s
          AND (ABS(c.paid_amount - COALESCE(pt.actual_paid,0)) > 0.01 OR COALESCE(pt.actual_paid,0) > c.total_amount_due * 2)
        ORDER BY overpay DESC
    """, (exclude,))
    rows = cur.fetchall()
    print(f"Remaining mismatch charters: {len(rows)}")
    print("Top 15:")
    for r in rows[:15]:
        due = r[2] if r[2] is not None else 0
        charter_paid = r[3] if r[3] is not None else 0
        actual_paid = r[4] if r[4] is not None else 0
        over = r[5] if r[5] is not None else 0
        print(f"  {r[0]} | Due ${due:.2f} | c.paid ${charter_paid:.2f} | actual ${actual_paid:.2f} | over ${over:.2f}")
    out_path = 'l:/limo/data/remaining_payment_mismatches.csv'
    with open(out_path,'w',newline='') as f:
        w=csv.writer(f); w.writerow(['reserve_number','charter_date','total_due','charter_paid','actual_paid','overpay'])
        w.writerows(rows)
    print(f"CSV written: {out_path}")
    cur.close(); conn.close()

if __name__=='__main__':
    main()
