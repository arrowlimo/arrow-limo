#!/usr/bin/env python3
"""Inspect payments table for Square/transaction identifier columns and sample data."""
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

cur.execute(
    """
    SELECT column_name
    FROM information_schema.columns
    WHERE table_schema='public'
      AND table_name='payments'
      AND (
        column_name ILIKE '%square%'
        OR column_name ILIKE '%transaction%'
        OR column_name ILIKE '%payment_id%'
      )
    ORDER BY column_name
    """
)
cols = [r[0] for r in cur.fetchall()]
print('Columns:', cols)

cur.execute(
    """
    SELECT payment_id, payment_date, amount,
           square_payment_id,
           square_transaction_id,
      square_notes,
           square_customer_name
    FROM payments
    WHERE square_payment_id IS NOT NULL
  OR square_transaction_id IS NOT NULL
  OR square_notes IS NOT NULL
    ORDER BY payment_date DESC
    LIMIT 20
    """
)
rows = cur.fetchall()
print('\nSample rows (latest 20):')
for row in rows:
    print(row)

cur.close()
conn.close()
