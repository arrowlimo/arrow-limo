#!/usr/bin/env python3
"""
Analyze invoiced (controlled) tips from charter charges and compute GST included.
- Detect gratuity/tip line items from `charter_charges` via description patterns.
- Join to `charters` by reserve_number to get charter_date for period grouping.
- Reconcile totals with GL 4150 gratuity revenue.
Outputs monthly and yearly summaries + overall totals.
"""
import os
import psycopg2

GST_RATE = 0.05


def get_conn():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        dbname=os.environ.get('DB_NAME', 'almsdata'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD', '***REMOVED***'),
    )


def main():
    conn = get_conn()
    cur = conn.cursor()

    # Monthly invoiced tips from charter charges
    cur.execute(
        """
        SELECT 
            EXTRACT(YEAR FROM c.charter_date)::int AS year,
            EXTRACT(MONTH FROM c.charter_date)::int AS month,
            SUM(COALESCE(cc.amount,0)) AS tips_total,
            COUNT(*) AS lines
        FROM charter_charges cc
        JOIN charters c ON c.reserve_number = cc.reserve_number
        WHERE (
            LOWER(COALESCE(cc.description,'')) LIKE '%gratuity%'
            OR LOWER(COALESCE(cc.description,'')) LIKE '%tip%'
        )
        GROUP BY 1,2
        ORDER BY 1,2
        """
    )
    monthly = cur.fetchall()

    # Yearly totals
    cur.execute(
        """
        SELECT 
            EXTRACT(YEAR FROM c.charter_date)::int AS year,
            SUM(COALESCE(cc.amount,0)) AS tips_total,
            COUNT(*) AS lines
        FROM charter_charges cc
        JOIN charters c ON c.reserve_number = cc.reserve_number
        WHERE (
            LOWER(COALESCE(cc.description,'')) LIKE '%gratuity%'
            OR LOWER(COALESCE(cc.description,'')) LIKE '%tip%'
        )
        GROUP BY 1
        ORDER BY 1
        """
    )
    yearly = cur.fetchall()

    # GL 4150 reconciliation
    cur.execute(
        """
        SELECT EXTRACT(YEAR FROM transaction_date)::int AS year,
               SUM(COALESCE(credit_amount,0) - COALESCE(debit_amount,0)) AS total
        FROM unified_general_ledger
        WHERE account_code = '4150'
        GROUP BY 1
        ORDER BY 1
        """
    )
    gl = {row[0]: float(row[1] or 0) for row in cur.fetchall()}

    print("Controlled (Invoiced) Tips Monthly Summary")
    print("Year-Month | Tips Total | GST Included | Lines")
    print("-" * 60)
    monthly_total = 0.0
    monthly_gst = 0.0
    for y, m, total, lines in monthly:
        gst_inc = round(float(total or 0) * GST_RATE / (1 + GST_RATE), 2)
        monthly_total += float(total or 0)
        monthly_gst += gst_inc
        print(f"{y:04d}-{m:02d} | ${float(total or 0):10,.2f} | ${gst_inc:12,.2f} | {lines}")

    print("\nControlled Tips Yearly Summary")
    print("Year | Tips Total | GST Included | Lines | GL4150 | Diff")
    print("-" * 80)
    grand_total = 0.0
    grand_gst = 0.0
    for y, total, lines in yearly:
        total_f = float(total or 0)
        gst_inc = round(total_f * GST_RATE / (1 + GST_RATE), 2)
        gl_y = gl.get(y, 0.0)
        diff = round(gl_y - total_f, 2)
        grand_total += total_f
        grand_gst += gst_inc
        print(f"{y} | ${total_f:10,.2f} | ${gst_inc:12,.2f} | {lines:5d} | ${gl_y:10,.2f} | ${diff:8,.2f}")

    print("\nTotals:")
    print(f"Controlled Tips Total:  ${grand_total:,.2f}")
    print(f"GST Included (5%):     ${grand_gst:,.2f}")
    print(f"Monthly Sum Tips:      ${monthly_total:,.2f}")
    print(f"Monthly Sum GST:       ${monthly_gst:,.2f}")

    cur.close()
    conn.close()


if __name__ == '__main__':
    main()
