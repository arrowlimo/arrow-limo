#!/usr/bin/env python3
"""
Reconcile Square deposits (net after fees) to banking receipts and export results to CSV.
For each deposit date, sum net_amount from square_processing_fees, match to receipts (banking deposits), and report mismatches.
Output: reports/square_banking_reconciliation.csv
"""
import os
import psycopg2
import csv
from datetime import date

DB_NAME = os.environ.get('DB_NAME', 'almsdata')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', '***REMOVED***')
DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_PORT = int(os.environ.get('DB_PORT', '5432'))

CSV_PATH = r"l:/limo/reports/square_banking_reconciliation.csv"

def main():
    with psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT) as conn:
        with conn.cursor() as cur:
            # 1. Get all Square deposit dates and net amounts
            cur.execute("""
                SELECT fee_date, SUM(net_amount) AS total_net, COUNT(*) AS deposit_count
                FROM square_processing_fees
                GROUP BY fee_date
                ORDER BY fee_date DESC
            """)
            square_deposits = cur.fetchall()

            # 2. For each deposit date, find matching banking receipt(s)
            results = []
            for fee_date, total_net, deposit_count in square_deposits:
                # Find receipts with matching date and similar amount (±$2 tolerance)
                cur.execute("""
                    SELECT id, receipt_date, vendor_name, gross_amount, expense, category
                    FROM receipts
                    WHERE receipt_date = %s
                      AND category IN ('DEPOSITS','TRANSFERS')
                      AND ABS(gross_amount - %s) <= 2.00
                    ORDER BY ABS(gross_amount - %s) ASC
                """, (fee_date, total_net, total_net))
                matches = cur.fetchall()
                matched = bool(matches)
                results.append({
                    'fee_date': fee_date,
                    'square_total_net': float(total_net),
                    'deposit_count': deposit_count,
                    'banking_receipt_id': matches[0][0] if matched else '',
                    'banking_receipt_date': matches[0][1] if matched else '',
                    'banking_vendor': matches[0][2] if matched else '',
                    'banking_gross_amount': float(matches[0][3]) if matched else '',
                    'banking_expense': float(matches[0][4]) if matched else '',
                    'banking_category': matches[0][5] if matched else '',
                    'matched': 'Y' if matched else 'N',
                    'amount_diff': (float(matches[0][3]) - float(total_net)) if matched else '',
                })

            # 3. Write results to CSV
            with open(CSV_PATH, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    'fee_date','square_total_net','deposit_count',
                    'banking_receipt_id','banking_receipt_date','banking_vendor',
                    'banking_gross_amount','banking_expense','banking_category',
                    'matched','amount_diff'])
                writer.writeheader()
                for row in results:
                    writer.writerow(row)
            print(f"Reconciliation complete. CSV written: {CSV_PATH}")

if __name__ == '__main__':
    main()