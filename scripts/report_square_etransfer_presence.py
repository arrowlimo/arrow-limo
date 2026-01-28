#!/usr/bin/env python3
"""
Report whether Square and Interac e-Transfer data exist in the receipts table.

Outputs counts, revenue sums, and a few recent sample rows for each.
Looks at created_from_banking=true and common description/vendor patterns.
"""
import os
import psycopg2

DB_NAME = os.environ.get('DB_NAME', 'almsdata')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', '***REMOVED***')
DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_PORT = int(os.environ.get('DB_PORT', '5432'))


def query(cur, sql, params=None):
    cur.execute(sql, params or [])
    return cur.fetchall()


def main() -> None:
    conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT)
    try:
        cur = conn.cursor()

        print("=== SQUARE PRESENCE ===")
        # Square patterns (as imported we typically prefix vendor_name with 'REVENUE - ')
        square_count_sum = query(cur, """
            SELECT COUNT(*), COALESCE(SUM(revenue),0)
            FROM receipts
            WHERE created_from_banking = true
              AND (
                    vendor_name ILIKE 'REVENUE - SQUARE%'
                 OR vendor_name ILIKE 'REVENUE - SQ *%'
                 OR vendor_name ILIKE 'REVENUE - SQ %'
                 OR vendor_name ILIKE 'SQUARE%'
                 OR vendor_name ILIKE 'SQ *%'
              )
        """)
        print(f"Square rows: {square_count_sum[0][0]}, revenue total: ${square_count_sum[0][1]:,.2f}")

        square_samples = query(cur, """
            SELECT receipt_date, vendor_name, revenue, expense, category
            FROM receipts
            WHERE created_from_banking = true AND (
                vendor_name ILIKE 'REVENUE - SQUARE%'
             OR vendor_name ILIKE 'REVENUE - SQ *%'
             OR vendor_name ILIKE 'REVENUE - SQ %'
             OR vendor_name ILIKE 'SQUARE%'
             OR vendor_name ILIKE 'SQ *%'
            )
            ORDER BY receipt_date DESC
            LIMIT 5
        """)
        for r in square_samples:
            print("  ", r)

        print("\n=== E-TRANSFER PRESENCE ===")
        # Interac e-Transfer patterns
        et_count_sum = query(cur, """
            SELECT COUNT(*), COALESCE(SUM(revenue),0)
            FROM receipts
            WHERE created_from_banking = true
              AND (
                    vendor_name ILIKE '%INTERAC E-TRANSFER%'
                 OR vendor_name ILIKE '%E-TRANSFER%'
                 OR vendor_name ILIKE '%EMT%'
                 OR vendor_name ILIKE 'REVENUE - INTERNET BANKING%'
                 OR vendor_name ILIKE '%INTERAC ETRF%'
              )
        """)
        print(f"e-Transfer rows: {et_count_sum[0][0]}, revenue total: ${et_count_sum[0][1]:,.2f}")

        et_samples = query(cur, """
            SELECT receipt_date, vendor_name, revenue, expense, category
            FROM receipts
            WHERE created_from_banking = true AND (
                vendor_name ILIKE '%INTERAC E-TRANSFER%'
             OR vendor_name ILIKE '%E-TRANSFER%'
             OR vendor_name ILIKE '%EMT%'
             OR vendor_name ILIKE 'REVENUE - INTERNET BANKING%'
             OR vendor_name ILIKE '%INTERAC ETRF%'
            )
            ORDER BY receipt_date DESC
            LIMIT 5
        """)
        for r in et_samples:
            print("  ", r)

        cur.close()
    finally:
        conn.close()


if __name__ == '__main__':
    main()
