#!/usr/bin/env python3
"""
Create or replace a view 'receipts_finance_view' that exposes revenue and expense side by side
and provides inflow_amount, outflow_amount, and signed_amount for simpler reporting/UI.

Definitions:
- inflow_amount: revenue-like amount (revenue>0 or ABS(expense) when expense<0 per Epson convention)
- outflow_amount: expense-like amount (expense>0)
- signed_amount: inflow positive, outflow negative
"""
import os
import psycopg2

DB_NAME = os.environ.get('DB_NAME', 'almsdata')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', '***REMOVED***')
DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_PORT = int(os.environ.get('DB_PORT', '5432'))

VIEW_SQL = """
CREATE OR REPLACE VIEW receipts_finance_view AS
SELECT
  id AS receipt_id,
  receipt_date,
  vendor_name,
  category,
  expense_account,
  gross_amount,
  gst_amount,
  net_amount,
  expense,
  revenue,
  CASE 
    WHEN COALESCE(revenue,0) > 0 THEN revenue
    WHEN expense < 0 THEN ABS(expense)
    ELSE 0
  END AS inflow_amount,
  CASE 
    WHEN expense > 0 THEN expense
    ELSE 0
  END AS outflow_amount,
  CASE 
    WHEN COALESCE(revenue,0) > 0 THEN COALESCE(revenue,0)
    WHEN expense < 0 THEN ABS(expense)
    WHEN expense > 0 THEN -expense
    ELSE 0
  END AS signed_amount
FROM receipts;
"""

def main() -> None:
    with psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT) as conn:
        with conn.cursor() as cur:
            cur.execute(VIEW_SQL)
            # Simple sanity
            cur.execute("SELECT COUNT(*), SUM(inflow_amount), SUM(outflow_amount), SUM(signed_amount) FROM receipts_finance_view")
            count, inflow, outflow, signed = cur.fetchone()
            print(f"View created. Rows={count}, Inflow={inflow or 0:.2f}, Outflow={outflow or 0:.2f}, Net={signed or 0:.2f}")

if __name__ == '__main__':
    main()
