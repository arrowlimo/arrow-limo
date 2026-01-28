#!/usr/bin/env python3
"""
Add a 'revenue' column to receipts and backfill it safely.

Rules for backfill:
- For banking imports (created_from_banking = true):
  • If expense < 0 (Epson convention for revenue), set revenue = ABS(expense).
  • Else (expense >= 0), leave revenue = 0.
- For any receipt that clearly looks like revenue (vendor_name starts with 'REVENUE - '
  or category in common revenue categories), set revenue = COALESCE(revenue, gross_amount)
  but only when revenue is NULL or 0.

Column is created if missing. Defaults to 0 and kept nullable False for consistency
with reports that expect numeric values. Adjust as needed.
"""
import os
import sys

try:
    import psycopg2  # type: ignore
except Exception as e:
    print("psycopg2 is required to run this script.")
    print(str(e))
    sys.exit(1)


def main() -> None:
    DB_NAME = os.environ.get('DB_NAME', 'almsdata')
    DB_USER = os.environ.get('DB_USER', 'postgres')
    DB_PASSWORD = os.environ.get('DB_PASSWORD', '***REMOVED***')
    DB_HOST = os.environ.get('DB_HOST', 'localhost')
    DB_PORT = int(os.environ.get('DB_PORT', '5432'))

    conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT)
    try:
        with conn, conn.cursor() as cur:
            print("Checking/adding receipts.revenue column...")
            cur.execute("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_schema = 'public' AND table_name = 'receipts' AND column_name = 'revenue'
                    ) THEN
                        ALTER TABLE receipts ADD COLUMN revenue NUMERIC DEFAULT 0;
                    END IF;
                END
                $$;
            """)

            # Ensure not null with default 0 (optional but helps reports)
            cur.execute("""
                ALTER TABLE receipts
                ALTER COLUMN revenue SET DEFAULT 0;
            """)

            # Backfill for banking revenue rows
            print("Backfilling revenue for banking transactions (expense < 0 -> revenue = ABS(expense))...")
            cur.execute(
                """
                UPDATE receipts
                SET revenue = ABS(expense)
                WHERE created_from_banking = true
                  AND expense < 0
                  AND COALESCE(revenue, 0) = 0
                """
            )
            print(f"  Updated {cur.rowcount} banking revenue rows")

            # Backfill for obvious revenue patterns outside of the negative-expense rule
            print("Backfilling revenue for obvious revenue indicators (vendor/category cues)...")
            cur.execute(
                """
                UPDATE receipts
                SET revenue = CASE
                    WHEN expense < 0 THEN ABS(expense)
                    WHEN gross_amount IS NOT NULL AND gross_amount > 0 THEN gross_amount
                    ELSE 0
                END
                WHERE COALESCE(revenue, 0) = 0
                  AND (
                        vendor_name ILIKE 'REVENUE - %'
                     OR category IN ('DEPOSITS','TRANSFERS','REVENUE','INCOME')
                  )
                """
            )
            print(f"  Updated {cur.rowcount} other revenue-like rows")

            # Optionally, set remaining NULL revenue to 0 and enforce NOT NULL
            cur.execute("UPDATE receipts SET revenue = 0 WHERE revenue IS NULL")
            cur.execute("ALTER TABLE receipts ALTER COLUMN revenue SET NOT NULL")

            # Show quick summary
            cur.execute(
                """
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE WHEN revenue > 0 THEN 1 END) as revenue_rows,
                    SUM(revenue) as total_revenue
                FROM receipts
                """
            )
            total, revenue_rows, total_revenue = cur.fetchone()
            print(f"Summary: total rows={total}, rows with revenue>0={revenue_rows}, total_revenue={total_revenue or 0}")

    finally:
        conn.close()


if __name__ == '__main__':
    main()
