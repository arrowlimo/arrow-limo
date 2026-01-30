#!/usr/bin/env python3
"""
Lookup Petro‑Canada receipt context for amount $43.45 on 2012‑12‑29 and decode code '007130'.
Searches receipts and banking_transactions around the date/amount, and scans for '007130'.
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor

def connect():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        database=os.environ.get('DB_NAME', 'almsdata'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD', '***REDACTED***')
    )

def main():
    conn = connect()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    target_amount = 43.45
    # Core focus window and a wider exploratory window
    start = '2012-12-28'
    end = '2012-12-30'
    wide_start = '2012-12-15'
    wide_end = '2013-01-15'

    print('=== Receipts: Petro‑Canada near 2012‑12‑29 for $43.45 ===')
    cur.execute(
        f"""
        SELECT id, receipt_date, vendor_name, category, gross_amount, gst_amount, description
        FROM receipts
        WHERE receipt_date BETWEEN '{start}' AND '{end}'
            AND ABS(COALESCE(gross_amount,0) - {target_amount}) <= 0.01
            AND (
                     LOWER(COALESCE(vendor_name,'')) LIKE '%petro%'
                OR LOWER(COALESCE(description,'')) LIKE '%petro%'
            )
        ORDER BY receipt_date, id
        """
    )
    rows = cur.fetchall()
    if rows:
        for r in rows:
            print(dict(r))
    else:
        print('No direct Petro‑Canada receipt match by date+amount.')

        print('\n=== Receipts mentioning 007130 around that date ===')
        cur.execute(
                f"""
                SELECT id, receipt_date, vendor_name, gross_amount, description
                FROM receipts
                WHERE receipt_date BETWEEN '{start}' AND '{end}'
                    AND (
                             COALESCE(description,'') LIKE '%007130%'
                        OR COALESCE(vendor_name,'') LIKE '%007130%'
                    )
                ORDER BY receipt_date, id
                """
        )
    rows = cur.fetchall()
    if rows:
        for r in rows:
            print(dict(r))
    else:
        print('No 007130 mention in receipts for that window.')

    print('\n=== Banking: Petro around that date/amount ===')
    cur.execute(
        f"""
        SELECT transaction_id, transaction_date, description, debit_amount, credit_amount
        FROM banking_transactions
        WHERE transaction_date BETWEEN '{start}' AND '{end}'
          AND (
               ABS(COALESCE(debit_amount,0) - {target_amount}) <= 0.01
            OR ABS(COALESCE(credit_amount,0) - {target_amount}) <= 0.01
          )
          AND LOWER(COALESCE(description,'')) LIKE '%petro%'
        ORDER BY transaction_date, transaction_id
        """
    )
    rows = cur.fetchall()
    if rows:
        for r in rows:
            print(dict(r))
    else:
        print('No banking transaction with Petro and $43.45 in that window.')

    print('\n=== Banking: any description containing 007130 around that date ===')
    cur.execute(
        f"""
        SELECT transaction_id, transaction_date, description, debit_amount
        FROM banking_transactions
        WHERE transaction_date BETWEEN '{start}' AND '{end}'
          AND COALESCE(description,'') LIKE '%007130%'
        ORDER BY transaction_date, transaction_id
        """
    )
    rows = cur.fetchall()
    if rows:
        for r in rows:
            print(dict(r))
    else:
        print('No 007130 mention in banking in that window.')

    # Broader exploratory queries
    print('\n=== Receipts: Any Petro in ±14 days (limit 25) ===')
    cur.execute(
        f"""
        SELECT id, receipt_date, vendor_name, category, gross_amount, description
        FROM receipts
        WHERE receipt_date BETWEEN '{wide_start}' AND '{wide_end}'
          AND (
               LOWER(COALESCE(vendor_name,'')) LIKE '%petro%'
            OR LOWER(COALESCE(description,'')) LIKE '%petro%'
          )
        ORDER BY receipt_date, id
        LIMIT 25
        """
    )
    for r in cur.fetchall():
        print(dict(r))

    print('\n=== Banking: Any Petro in ±14 days (limit 25) ===')
    cur.execute(
        f"""
        SELECT transaction_id, transaction_date, description, debit_amount, credit_amount
        FROM banking_transactions
        WHERE transaction_date BETWEEN '{wide_start}' AND '{wide_end}'
          AND LOWER(COALESCE(description,'')) LIKE '%petro%'
        ORDER BY transaction_date, transaction_id
        LIMIT 25
        """
    )
    for r in cur.fetchall():
        print(dict(r))

    print('\n=== Banking: any description containing 007130/07130/7130 (all time, limit 25) ===')
    cur.execute(
        """
        SELECT transaction_id, transaction_date, description, debit_amount, credit_amount
        FROM banking_transactions
        WHERE COALESCE(description,'') ILIKE '%007130%'
           OR COALESCE(description,'') ILIKE '%07130%'
           OR COALESCE(description,'') ILIKE '%7130%'
        ORDER BY transaction_date
        LIMIT 25
        """
    )
    for r in cur.fetchall():
        print(dict(r))

    print('\n=== Receipts: any vendor but amount ≈ 43.45 in ±14 days ===')
    cur.execute(
        f"""
        SELECT id, receipt_date, vendor_name, category, gross_amount, description
        FROM receipts
        WHERE receipt_date BETWEEN '{wide_start}' AND '{wide_end}'
          AND ABS(COALESCE(gross_amount,0) - {target_amount}) <= 0.01
        ORDER BY receipt_date, id
        LIMIT 50
        """
    )
    for r in cur.fetchall():
        print(dict(r))

    # Broader lookback if nothing found
    print('\n=== Optional: any receipt mentioning 007130 (all time, limit 10) ===')
    cur.execute(
        """
        SELECT id, receipt_date, vendor_name, gross_amount, description
        FROM receipts
    WHERE COALESCE(description,'') LIKE '%007130%'
           OR COALESCE(vendor_name,'') LIKE '%007130%'
        ORDER BY receipt_date
        LIMIT 10
        """
    )
    for r in cur.fetchall():
        print(dict(r))

    cur.close(); conn.close()

if __name__ == '__main__':
    main()
