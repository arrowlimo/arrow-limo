#!/usr/bin/env python3
"""
Backfill income_ledger from charter_payments for all years.
Idempotent: skips rows already posted via source_system='charter_payments'.
"""

import psycopg2

DB = {
    'host': 'localhost',
    'port': 5432,
    'database': 'almsdata',
    'user': 'postgres',
    'password': 'ArrowLimousine',
}

DRY_RUN = False


def main():
    conn = psycopg2.connect(**DB)
    cur = conn.cursor()

    # Candidate rows not yet posted.
    cur.execute(
        """
        WITH candidates AS (
            SELECT
                cp.id,
                cp.payment_id,
                cp.charter_id AS reserve_key,
                cp.amount,
                cp.payment_date,
                cp.payment_method,
                c.charter_id AS charter_id_int,
                c.client_id,
                c.reserve_number
            FROM charter_payments cp
            LEFT JOIN charters c
                ON c.reserve_number = cp.charter_id
            WHERE cp.payment_date IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1
                  FROM income_ledger il
                  WHERE il.source_system = 'charter_payments'
                    AND il.payment_reference = CONCAT('CP-', cp.id::text)
              )
        )
        SELECT
            COUNT(*) AS row_count,
            COALESCE(SUM(amount), 0) AS gross_total
        FROM candidates
        """
    )
    row_count, gross_total = cur.fetchone()

    print(f"Rows to post: {row_count}")
    print(f"Gross total to post: ${gross_total:,.2f}")

    if row_count == 0:
        print("Nothing to post. income_ledger is already up to date for charter_payments source.")
        cur.close()
        conn.close()
        return

    if DRY_RUN:
        print("DRY_RUN=True. No changes applied.")
        cur.close()
        conn.close()
        return

    cur.execute(
        """
        INSERT INTO income_ledger (
            payment_id,
            source_system,
            transaction_date,
            revenue_category,
            revenue_subcategory,
            gross_amount,
            gst_collected,
            is_taxable,
            tax_province,
            client_id,
            charter_id,
            reserve_number,
            payment_method,
            payment_reference,
            description,
            created_by
        )
        SELECT
            cp.payment_id,
            'charter_payments',
            cp.payment_date,
            'Operating Revenue',
            'Charter Services',
            cp.amount,
            ROUND((cp.amount * 5.0 / 105.0)::numeric, 2),
            TRUE,
            'AB',
            c.client_id,
            c.charter_id,
            c.reserve_number,
            cp.payment_method,
            CONCAT('CP-', cp.id::text),
            CASE
                WHEN c.charter_id IS NOT NULL
                    THEN CONCAT('Charter #', c.charter_id::text, ' - Res #', c.reserve_number, ' - ', COALESCE(cp.payment_method, 'unknown'))
                ELSE CONCAT('Charter payment reserve #', cp.charter_id, ' - ', COALESCE(cp.payment_method, 'unknown'))
            END,
            'backfill_income_ledger_from_charter_payments.py'
        FROM charter_payments cp
        LEFT JOIN charters c
            ON c.reserve_number = cp.charter_id
        WHERE cp.payment_date IS NOT NULL
          AND NOT EXISTS (
              SELECT 1
              FROM income_ledger il
              WHERE il.source_system = 'charter_payments'
                AND il.payment_reference = CONCAT('CP-', cp.id::text)
          )
        """
    )

    inserted = cur.rowcount
    conn.commit()

    print(f"Inserted rows: {inserted}")

    cur.execute(
        """
        SELECT COUNT(*), COALESCE(SUM(gross_amount), 0)
        FROM income_ledger
        WHERE source_system = 'charter_payments'
        """
    )
    count_posted, amount_posted = cur.fetchone()
    print(f"income_ledger posted total: {count_posted} rows, ${amount_posted:,.2f}")

    cur.close()
    conn.close()


if __name__ == '__main__':
    main()
