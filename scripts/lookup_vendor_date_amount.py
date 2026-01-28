#!/usr/bin/env python3
"""
Lookup receipts and banking transactions for a vendor substring on a specific date
and amount. Example: Liquor Barn on 2012-12-31 for 204.26 with GST ≈ 9.56 included.
Usage:
  python scripts/lookup_vendor_date_amount.py "liquor barn" 2012-12-31 204.26
"""
import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor

def connect():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        database=os.environ.get('DB_NAME', 'almsdata'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD', '***REMOVED***'),
    )

def main():
    if len(sys.argv) < 4:
        print("Usage: python scripts/lookup_vendor_date_amount.py <vendor_substring> <YYYY-MM-DD> <amount>")
        sys.exit(1)

    vendor = sys.argv[1].strip()
    date = sys.argv[2].strip()
    try:
        amount = float(sys.argv[3])
    except ValueError:
        print("Amount must be a number, e.g., 204.26")
        sys.exit(1)

    tol = 0.02  # tolerance for amount comparisons

    conn = connect()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    print(f"=== Receipts on {date} for ~{amount:.2f} vendor like '{vendor}' ===")
    cur.execute(
        f"""
        SELECT id, receipt_date, vendor_name, category, gross_amount, gst_amount, description
        FROM receipts
        WHERE receipt_date = %s
          AND ABS(COALESCE(gross_amount,0) - %s) <= %s
          AND (
                LOWER(COALESCE(vendor_name,'')) LIKE %s
             OR LOWER(COALESCE(description,'')) LIKE %s
          )
        ORDER BY id
        """,
        (date, amount, tol, f"%{vendor.lower()}%", f"%{vendor.lower()}%")
    )
    rows = cur.fetchall()
    if rows:
        for r in rows:
            print(dict(r))
    else:
        print("No receipt found on the exact date; widening window ±7 days...")

        cur.execute(
            f"""
            SELECT id, receipt_date, vendor_name, category, gross_amount, gst_amount, description
            FROM receipts
            WHERE receipt_date BETWEEN (%s::date - INTERVAL '7 day') AND (%s::date + INTERVAL '7 day')
              AND ABS(COALESCE(gross_amount,0) - %s) <= %s
              AND (
                    LOWER(COALESCE(vendor_name,'')) LIKE %s
                 OR LOWER(COALESCE(description,'')) LIKE %s
              )
            ORDER BY receipt_date, id
            """,
            (date, date, amount, tol, f"%{vendor.lower()}%", f"%{vendor.lower()}%")
        )
        for r in cur.fetchall():
            print(dict(r))

        # Fallback: exact date, any vendor, matching amount
        print(f"\n=== Receipts on {date} any vendor with amount ~{amount:.2f} ===")
        cur.execute(
            """
            SELECT id, receipt_date, vendor_name, category, gross_amount, gst_amount, description
            FROM receipts
            WHERE receipt_date = %s
              AND ABS(COALESCE(gross_amount,0) - %s) <= %s
            ORDER BY vendor_name, id
            """,
            (date, amount, tol)
        )
        for r in cur.fetchall():
            print(dict(r))

        # Fallback: exact date, vendor ~ 'liquor' (broadened)
        print(f"\n=== Receipts on {date} vendor contains 'liquor' amount ~{amount:.2f} (±7 days if none) ===")
        cur.execute(
            """
            SELECT id, receipt_date, vendor_name, category, gross_amount, gst_amount, description
            FROM receipts
            WHERE receipt_date = %s
              AND (
                     LOWER(COALESCE(vendor_name,'')) LIKE %s
                  OR LOWER(COALESCE(description,'')) LIKE %s
              )
              AND ABS(COALESCE(gross_amount,0) - %s) <= %s
            ORDER BY id
            """,
            (date, '%liquor%', '%liquor%', amount, tol)
        )
        more = cur.fetchall()
        if not more:
            cur.execute(
                """
                SELECT id, receipt_date, vendor_name, category, gross_amount, gst_amount, description
                FROM receipts
                WHERE receipt_date BETWEEN (%s::date - INTERVAL '7 day') AND (%s::date + INTERVAL '7 day')
                  AND (
                         LOWER(COALESCE(vendor_name,'')) LIKE %s
                      OR LOWER(COALESCE(description,'')) LIKE %s
                  )
                  AND ABS(COALESCE(gross_amount,0) - %s) <= %s
                ORDER BY receipt_date, id
                """,
                (date, date, '%liquor%', '%liquor%', amount, tol)
            )
            more = cur.fetchall()
        for r in more:
            print(dict(r))

    # Fallback: GST proximity on exact date (could be deposits/non-tax lines affecting net)
        print(f"\n=== Receipts on {date} with gst_amount ≈ 9.56 (±0.10) ===")
        cur.execute(
            """
            SELECT id, receipt_date, vendor_name, category, gross_amount, gst_amount, description
            FROM receipts
            WHERE receipt_date = %s
              AND ABS(COALESCE(gst_amount,0) - %s) <= 0.10
            ORDER BY vendor_name, id
            """,
            (date, 9.56)
        )
        for r in cur.fetchall():
            print(dict(r))

        # Broaden further: ±14 days any vendor with amount within ±0.50
        print(f"\n=== Receipts ±14 days any vendor with amount ~{amount:.2f} (±0.50) ===")
        cur.execute(
            """
            SELECT id, receipt_date, vendor_name, category, gross_amount, gst_amount, description
            FROM receipts
            WHERE receipt_date BETWEEN (%s::date - INTERVAL '14 day') AND (%s::date + INTERVAL '14 day')
              AND ABS(COALESCE(gross_amount,0) - %s) <= 0.50
            ORDER BY receipt_date, id
            """,
            (date, date, amount)
        )
        for r in cur.fetchall():
            print(dict(r))

        # Exact date, any vendor, contains 'liquor' regardless of amount
        print(f"\n=== Receipts on {date} vendor/description contains 'liquor' (any amount) ===")
        cur.execute(
            """
            SELECT id, receipt_date, vendor_name, category, gross_amount, gst_amount, description
            FROM receipts
            WHERE receipt_date = %s
              AND (
                     LOWER(COALESCE(vendor_name,'')) LIKE %s
                  OR LOWER(COALESCE(description,'')) LIKE %s
              )
            ORDER BY id
            """,
            (date, '%liquor%', '%liquor%')
        )
        for r in cur.fetchall():
            print(dict(r))

        # Broaden keywords across ±14 days
        keywords = ['liquor', 'depot', 'wine', 'beyond', 'spirits', 'sobeys', 'co-op']
        like_clauses = " OR ".join(["LOWER(COALESCE(vendor_name,'')) LIKE %s OR LOWER(COALESCE(description,'')) LIKE %s" for _ in keywords])
        params = []
        for k in keywords:
            pat = f"%{k}%"
            params.extend([pat, pat])
        print(f"\n=== Receipts ±14 days vendor/description contains any of {keywords} (any amount, limit 50) ===")
        cur.execute(
            f"""
            SELECT id, receipt_date, vendor_name, category, gross_amount, gst_amount, description
            FROM receipts
            WHERE receipt_date BETWEEN (%s::date - INTERVAL '14 day') AND (%s::date + INTERVAL '14 day')
              AND ( {like_clauses} )
            ORDER BY receipt_date, id
            LIMIT 50
            """,
            (date, date, *params)
        )
        for r in cur.fetchall():
            print(dict(r))

    print(f"\n=== Banking on {date} for ~{amount:.2f} vendor like '{vendor}' ===")
    cur.execute(
        f"""
        SELECT transaction_id, transaction_date, description, debit_amount, credit_amount
        FROM banking_transactions
        WHERE transaction_date = %s
          AND (
                ABS(COALESCE(debit_amount,0) - %s) <= %s
             OR ABS(COALESCE(credit_amount,0) - %s) <= %s
          )
          AND LOWER(COALESCE(description,'')) LIKE %s
        ORDER BY transaction_date, transaction_id
        """,
        (date, amount, tol, amount, tol, f"%{vendor.lower()}%")
    )
    rows = cur.fetchall()
    if rows:
        for r in rows:
            print(dict(r))
    else:
        print("No banking match on exact date; widening window ±7 days...")
        cur.execute(
            f"""
            SELECT transaction_id, transaction_date, description, debit_amount, credit_amount
            FROM banking_transactions
            WHERE transaction_date BETWEEN (%s::date - INTERVAL '7 day') AND (%s::date + INTERVAL '7 day')
              AND (
                    ABS(COALESCE(debit_amount,0) - %s) <= %s
                 OR ABS(COALESCE(credit_amount,0) - %s) <= %s
              )
              AND LOWER(COALESCE(description,'')) LIKE %s
            ORDER BY transaction_date, transaction_id
            """,
            (date, date, amount, tol, amount, tol, f"%{vendor.lower()}%")
        )
        for r in cur.fetchall():
            print(dict(r))

        # Fallback: any banking with description containing 'liquor' on exact date irrespective of amount
        print(f"\n=== Banking on {date} description contains 'liquor' (any amount) ===")
        cur.execute(
            """
            SELECT transaction_id, transaction_date, description, debit_amount, credit_amount
            FROM banking_transactions
            WHERE transaction_date = %s
              AND LOWER(COALESCE(description,'')) LIKE %s
            ORDER BY transaction_date, transaction_id
            """,
            (date, '%liquor%')
        )
        for r in cur.fetchall():
            print(dict(r))

        # Broaden banking: ±14 days description contains 'liquor' (any amount)
        print(f"\n=== Banking ±14 days description contains 'liquor' (any amount) ===")
        cur.execute(
            """
            SELECT transaction_id, transaction_date, description, debit_amount, credit_amount
            FROM banking_transactions
            WHERE transaction_date BETWEEN (%s::date - INTERVAL '14 day') AND (%s::date + INTERVAL '14 day')
              AND LOWER(COALESCE(description,'')) LIKE %s
            ORDER BY transaction_date, transaction_id
            """,
            (date, date, '%liquor%')
        )
        for r in cur.fetchall():
            print(dict(r))

        # Banking keywords
        print(f"\n=== Banking ±14 days description contains any of {keywords} (any amount, limit 50) ===")
        like_clauses_b = " OR ".join(["LOWER(COALESCE(description,'')) LIKE %s" for _ in keywords])
        params_b = [f"%{k}%" for k in keywords]
        cur.execute(
            f"""
            SELECT transaction_id, transaction_date, description, debit_amount, credit_amount
            FROM banking_transactions
            WHERE transaction_date BETWEEN (%s::date - INTERVAL '14 day') AND (%s::date + INTERVAL '14 day')
              AND ( {like_clauses_b} )
            ORDER BY transaction_date, transaction_id
            LIMIT 50
            """,
            (date, date, *params_b)
        )
        for r in cur.fetchall():
            print(dict(r))

    # If a receipt row was found, check GST reasonableness under 'included' model (AB 5%)
    if 'rows' in locals() and rows:
        pass

    # Year-wide scan as last resort
    print(f"\n=== Year 2012 receipts vendor/description contains 'liquor' (limit 100) ===")
    cur.execute(
        """
        SELECT id, receipt_date, vendor_name, category, gross_amount, gst_amount, description
        FROM receipts
        WHERE receipt_date BETWEEN '2012-01-01' AND '2012-12-31'
          AND (
                 LOWER(COALESCE(vendor_name,'')) LIKE '%liquor%'
              OR LOWER(COALESCE(description,'')) LIKE '%liquor%'
          )
        ORDER BY receipt_date, id
        LIMIT 100
        """
    )
    for r in cur.fetchall():
        print(dict(r))

    cur.close(); conn.close()

if __name__ == '__main__':
    main()
