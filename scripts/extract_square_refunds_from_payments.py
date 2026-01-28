#!/usr/bin/env python3
"""
Extract Square refunds from payments table and populate charter_refunds.
Heuristics:
- amount < 0
- or status/notes indicate refund
- or square_status in ('REFUNDED','CANCELED') with negative adjustment

This ensures refund tracking is in place even if external XLS files are not present.
"""
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv('l:/limo/.env'); load_dotenv()

DB_HOST = os.getenv('DB_HOST','localhost')
DB_PORT = int(os.getenv('DB_PORT','5432'))
DB_NAME = os.getenv('DB_NAME','almsdata')
DB_USER = os.getenv('DB_USER','postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD','')

SQL_SELECT = """
SELECT p.payment_id,
       p.payment_date::date,
       COALESCE(p.amount, p.payment_amount) AS amount,
       p.reserve_number,
       p.charter_id,
       p.square_payment_id,
       p.square_status,
       COALESCE(p.notes,'') AS notes
FROM payments p
WHERE (
    COALESCE(p.amount, p.payment_amount) < 0
    OR UPPER(COALESCE(p.square_status,'')) LIKE '%REFUND%'
    OR UPPER(COALESCE(p.notes,'')) LIKE '%REFUND%'
)
"""

SQL_CREATE = """
CREATE TABLE IF NOT EXISTS charter_refunds (
    id SERIAL PRIMARY KEY,
    refund_date DATE NOT NULL,
    amount NUMERIC(12,2) NOT NULL,
    reserve_number VARCHAR(20),
    charter_id INTEGER,
    payment_id INTEGER,
    square_payment_id VARCHAR(100),
    description TEXT,
    customer TEXT,
    source_file TEXT,
    source_row INTEGER,
    reference TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_charter_refunds_reserve ON charter_refunds(reserve_number);
CREATE INDEX IF NOT EXISTS idx_charter_refunds_date ON charter_refunds(refund_date);
CREATE OR REPLACE VIEW charter_refund_summary AS
SELECT c.reserve_number,
       c.charter_id,
       COALESCE(SUM(cr.amount),0) AS total_refunded,
       COUNT(*) AS refund_count
FROM charters c
LEFT JOIN charter_refunds cr ON cr.reserve_number = c.reserve_number
GROUP BY c.reserve_number, c.charter_id;
"""

SQL_INSERT = """
INSERT INTO charter_refunds
(refund_date, amount, reserve_number, charter_id, payment_id, square_payment_id, description, customer, source_file, source_row, reference)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
"""

SQL_EXISTS = """
SELECT 1 FROM charter_refunds
WHERE refund_date = %s AND amount = %s AND COALESCE(reserve_number,'') = COALESCE(%s,'') AND payment_id = %s
"""

def main():
    conn = psycopg2.connect(host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    cur.execute(SQL_CREATE)
    conn.commit()

    cur.execute(SQL_SELECT)
    rows = cur.fetchall()
    inserted = 0
    for row in rows:
        payment_id, refund_date, amount, reserve_number, charter_id, square_payment_id, square_status, notes = row
        # Normalize amount as positive refund magnitude stored as positive or keep sign?
        # Store as positive refunded amount for clarity
        amount_pos = abs(amount) if amount is not None else None
        cur.execute(SQL_EXISTS, (refund_date, amount_pos, reserve_number, payment_id))
        if cur.fetchone():
            continue
        cur.execute(SQL_INSERT, (
            refund_date,
            amount_pos,
            reserve_number,
            charter_id,
            payment_id,
            square_payment_id,
            f"{square_status or ''} | {notes or ''}",
            None,
            'payments.table',
            payment_id,
            square_payment_id or str(payment_id)
        ))
        inserted += 1

    conn.commit()
    print(f"✓ Inserted {inserted} refund rows from payments into charter_refunds")

    # Print quick summary
    cur.execute("SELECT COUNT(*), COALESCE(SUM(amount),0) FROM charter_refunds")
    total_count, total_amount = cur.fetchone()
    print(f"Current charter_refunds: {total_count} rows, total amount ${total_amount:,.2f}")

    cur.close(); conn.close()

if __name__ == '__main__':
    main()
