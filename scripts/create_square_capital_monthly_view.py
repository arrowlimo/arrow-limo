#!/usr/bin/env python3
"""
Create or replace a monthly summary view for Square Capital activity.

View: square_capital_monthly_summary
Columns:
- month (YYYY-MM-01 date)
- credits_total (sum of loan-related inflows)
- repayments_total (sum of automatic payment outflows)
- credits_count, repayments_count

Source: square_capital_activity (loaded via import_square_capital_activity.py)
"""
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv('l:/limo/.env'); load_dotenv()

DDL = """
CREATE OR REPLACE VIEW square_capital_monthly_summary AS
WITH sc AS (
  SELECT 
    activity_date::date AS activity_date,
    description,
    amount::numeric AS amount,
    CASE 
      WHEN description ILIKE '%automatic payment%' THEN 'repayment'
      ELSE 'credit'
    END AS kind
  FROM square_capital_activity
), agg AS (
  SELECT 
    date_trunc('month', activity_date)::date AS month,
    SUM(CASE WHEN kind='credit' THEN amount ELSE 0 END) AS credits_total,
    SUM(CASE WHEN kind='repayment' THEN -ABS(amount) ELSE 0 END) AS repayments_total,
    COUNT(*) FILTER (WHERE kind='credit') AS credits_count,
    COUNT(*) FILTER (WHERE kind='repayment') AS repayments_count
  FROM sc
  GROUP BY 1
)
SELECT * FROM agg
ORDER BY month;
"""

def main():
  conn = psycopg2.connect(
      host=os.getenv('DB_HOST'),
      port=os.getenv('DB_PORT'),
      database=os.getenv('DB_NAME'),
      user=os.getenv('DB_USER'),
      password=os.getenv('DB_PASSWORD')
  )
  try:
    with conn.cursor() as cur:
      cur.execute(DDL)
    conn.commit()
    print("Created/updated view square_capital_monthly_summary")
  finally:
    conn.close()

if __name__ == '__main__':
  main()
