#!/usr/bin/env python3
import csv
from datetime import datetime, timedelta
import psycopg2

REPORT_PATH = r"L:\limo\reports\lms_duplicate_candidates.csv"

conn = psycopg2.connect(
    dbname='almsdata', user='postgres', password='***REDACTED***', host='localhost'
)
cur = conn.cursor()

print("Scanning for LMS vs non-LMS duplicate payments (dry-run)...")

# Prepare CSV
import os
os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
cur.execute(
    """
    SELECT 
        p_lms.reserve_number,
        p_lms.payment_id    AS lms_payment_id,
        p_lms.payment_date  AS lms_payment_date,
        p_lms.amount        AS lms_amount,
        p_other.payment_id  AS other_payment_id,
        p_other.payment_key AS other_key,
        p_other.payment_date AS other_payment_date
    FROM payments p_lms
    JOIN payments p_other
      ON p_other.reserve_number = p_lms.reserve_number
     AND p_other.amount = p_lms.amount
     AND p_other.payment_id <> p_lms.payment_id
     AND (p_other.payment_key IS NULL OR p_other.payment_key NOT LIKE 'LMS:%')
     AND (
            (p_lms.payment_date IS NOT NULL AND p_other.payment_date IS NOT NULL 
             AND p_lms.payment_date::date BETWEEN p_other.payment_date::date - INTERVAL '3 days'
                                              AND p_other.payment_date::date + INTERVAL '3 days')
         OR (p_lms.payment_date IS NULL AND p_other.payment_date IS NULL)
         )
    WHERE p_lms.payment_key LIKE 'LMS:%'
      AND p_lms.reserve_number IS NOT NULL
      AND p_lms.amount IS NOT NULL
    ORDER BY p_lms.reserve_number, p_lms.payment_id
    """
)

rows = cur.fetchall()
print(f"Duplicate candidates found: {len(rows)}")

with open(REPORT_PATH, 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow([
        'reserve_number','lms_payment_id','lms_payment_date','lms_amount',
        'other_payment_id','other_key','other_payment_date','status'
    ])
    for r in rows:
        reserve, lms_id, lms_dt, lms_amt, other_id, other_key, other_dt = r
        w.writerow([
            reserve,
            lms_id,
            (lms_dt.strftime('%Y-%m-%d') if hasattr(lms_dt, 'strftime') and lms_dt else ''),
            f"{float(lms_amt):.2f}",
            other_id,
            other_key or '',
            (other_dt.strftime('%Y-%m-%d') if hasattr(other_dt, 'strftime') and other_dt else ''),
            'candidate'
        ])

print(f"CSV written: {REPORT_PATH}")

cur.close()
conn.close()
