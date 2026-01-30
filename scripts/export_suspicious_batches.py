"""
Export suspicious payment_key batches for manual review.
Suspicious = number of payments in batch != number of distinct charters referenced by reserve_number/charter_id.
Outputs CSV at reports/suspicious_batches_for_manual_review.csv
"""
import os
import csv
import psycopg2
from decimal import Decimal

DB = dict(host=os.getenv('DB_HOST','localhost'), database=os.getenv('DB_NAME','almsdata'), user=os.getenv('DB_USER','postgres'), password=os.getenv('DB_PASSWORD','***REDACTED***'))

FIELDS = [
    'payment_key', 'payment_count', 'distinct_reserves', 'distinct_charters', 'mismatch',
    'total_amount', 'min_payment_date', 'max_payment_date', 'penny_count', 'null_reserve_count',
    'null_charter_count', 'sample_reserves', 'sample_charter_ids'
]

def main():
    conn = psycopg2.connect(**DB)
    cur = conn.cursor()

    # Build batch metrics
    cur.execute(
        """
        WITH base AS (
            SELECT 
                payment_key,
                payment_id,
                reserve_number,
                charter_id,
                amount,
                payment_date
            FROM payments
            WHERE payment_key IS NOT NULL AND payment_key <> ''
        ),
        agg AS (
            SELECT 
                payment_key,
                COUNT(*) AS payment_count,
                COUNT(DISTINCT reserve_number) AS distinct_reserves,
                COUNT(DISTINCT charter_id) AS distinct_charters,
                SUM(amount) AS total_amount,
                MIN(payment_date) AS min_payment_date,
                MAX(payment_date) AS max_payment_date,
                SUM(CASE WHEN ABS(amount) = 0.01 THEN 1 ELSE 0 END) AS penny_count,
                SUM(CASE WHEN reserve_number IS NULL OR reserve_number = '' THEN 1 ELSE 0 END) AS null_reserve_count,
                SUM(CASE WHEN charter_id IS NULL THEN 1 ELSE 0 END) AS null_charter_count
            FROM base
            GROUP BY payment_key
        ),
        samples AS (
            SELECT payment_key,
                   STRING_AGG(DISTINCT COALESCE(reserve_number, 'NULL'), ', ' ORDER BY COALESCE(reserve_number, 'NULL')) AS sample_reserves,
                   STRING_AGG(DISTINCT COALESCE(charter_id::text, 'NULL'), ', ' ORDER BY COALESCE(charter_id::text, 'NULL')) AS sample_charter_ids
            FROM (
                SELECT payment_key, reserve_number, charter_id,
                       ROW_NUMBER() OVER (PARTITION BY payment_key ORDER BY payment_id) AS rn
                FROM base
            ) s
            WHERE rn <= 50  -- limit to avoid overly long cells
            GROUP BY payment_key
        )
        SELECT 
            a.payment_key,
            a.payment_count,
            a.distinct_reserves,
            a.distinct_charters,
            (a.payment_count - GREATEST(a.distinct_reserves, a.distinct_charters)) AS mismatch,
            a.total_amount,
            a.min_payment_date,
            a.max_payment_date,
            a.penny_count,
            a.null_reserve_count,
            a.null_charter_count,
            COALESCE(s.sample_reserves, '') AS sample_reserves,
            COALESCE(s.sample_charter_ids, '') AS sample_charter_ids
        FROM agg a
        LEFT JOIN samples s USING (payment_key)
        WHERE a.payment_count > 1
          AND a.payment_count <> GREATEST(a.distinct_reserves, a.distinct_charters)
        ORDER BY mismatch DESC, a.payment_count DESC
        """
    )

    rows = cur.fetchall()

    os.makedirs('reports', exist_ok=True)
    out_path = 'reports/suspicious_batches_for_manual_review.csv'
    with open(out_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(FIELDS)
        for r in rows:
            # r matches FIELDS order
            w.writerow(r)

    print(f"✓ Exported {len(rows)} suspicious batches to {out_path}")

    # also print a tiny preview
    for r in rows[:5]:
        print(r[:6], '...')

    cur.close(); conn.close()

if __name__ == '__main__':
    main()
