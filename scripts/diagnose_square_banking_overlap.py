#!/usr/bin/env python3
import os
import psycopg2
from datetime import date, timedelta

DB_NAME = os.environ.get('DB_NAME', 'almsdata')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', '***REMOVED***')
DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_PORT = int(os.environ.get('DB_PORT', '5432'))

LOOKBACK_DAYS = int(os.environ.get('SQUARE_LOOKBACK_DAYS', '120'))
VENDOR_HINTS = [h.strip() for h in os.environ.get('SQUARE_RECON_VENDOR_HINTS', 'SQUARE,SQ ,SQUARE CANADA,SQC').split(',') if h.strip()]

conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT)
cur = conn.cursor()

print('=== Ranges ===')
cur.execute("SELECT MIN(arrival_date), MAX(arrival_date), COUNT(*) FROM square_payouts")
print('square_payouts:', cur.fetchone())
cur.execute("SELECT MIN(receipt_date), MAX(receipt_date), COUNT(*) FROM receipts WHERE created_from_banking=true")
print('receipts(banking):', cur.fetchone())
try:
    cur.execute("SELECT MIN(transaction_date), MAX(transaction_date), COUNT(*) FROM banking_transactions")
    print('banking_transactions:', cur.fetchone())
except Exception as e:
    print('banking_transactions table check error:', e)

print('\n=== Recent deposits in receipts_finance_view (inflow>0) ===')
cur.execute("""
SELECT COUNT(*), SUM(inflow_amount)
  FROM receipts_finance_view
 WHERE receipt_date >= CURRENT_DATE - INTERVAL %s
   AND inflow_amount > 0
""", (f"{LOOKBACK_DAYS} days",))
print('deposits count,sum:', cur.fetchone())

print('\n=== Square-like banking_transactions credits (last 120d) ===')
try:
    like_expr = " OR ".join(["description ILIKE %s" for _ in VENDOR_HINTS])
    params = [f"%{h}%" for h in VENDOR_HINTS]
    cur.execute(f"""
        SELECT COUNT(*), COALESCE(SUM(credit_amount),0)
          FROM banking_transactions
         WHERE transaction_date >= CURRENT_DATE - INTERVAL %s
           AND credit_amount IS NOT NULL AND credit_amount > 0
           AND ({like_expr})
    """, [f"{LOOKBACK_DAYS} days", *params])
    print('square-like credits count,sum:', cur.fetchone())
    cur.execute(f"""
        SELECT transaction_date, account_number, account_name, credit_amount, description
          FROM banking_transactions
         WHERE transaction_date >= CURRENT_DATE - INTERVAL %s
           AND credit_amount IS NOT NULL AND credit_amount > 0
           AND ({like_expr})
         ORDER BY transaction_date DESC
         LIMIT 20
    """, [f"{LOOKBACK_DAYS} days", *params])
    rows = cur.fetchall()
    for r in rows:
        print(r)
except Exception as e:
    print('banking_transactions query error:', e)

conn.close()
print('\nDone.')
