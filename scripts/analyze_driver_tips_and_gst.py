#!/usr/bin/env python3
"""
Analyze driver tips (gratuities) paid and estimated GST impact.
Sources:
- driver_payroll: fields possibly including driver_gratuity, driver_gratuity_amount
- unified_general_ledger: GL 4150 (Gratuity Revenue) per prior migration
- receipts: category 'gratuity' if present (optional)

GST model: Included tax (gst = total × rate / (1+rate)) for taxable gratuities.
We will compute:
1) Total gratuity revenue recorded (GL 4150)
2) Total driver gratuity paid (from payroll fields)
3) Net margin on gratuities (revenue - paid)
4) Estimated GST owing/not collected if gratuities are taxable

Outputs a summary by year and overall totals.
"""
import os
import sys
from datetime import datetime
import psycopg2

GST_RATE = 0.05  # Alberta


def get_conn():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        dbname=os.environ.get('DB_NAME', 'almsdata'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD', '***REMOVED***'),
    )


def fetch_gl_gratuity(cur):
    """Return dict year -> total gratuity revenue (GL 4150)"""
    cur.execute(
        """
        SELECT EXTRACT(YEAR FROM transaction_date)::int AS year,
               SUM(COALESCE(credit_amount,0) - COALESCE(debit_amount,0)) AS total
        FROM unified_general_ledger
        WHERE account_code = '4150'
        GROUP BY year
        ORDER BY year
        """
    )
    return {row[0]: float(row[1] or 0) for row in cur.fetchall()}


def fetch_payroll_gratuity(cur):
    """Return dict year -> total driver gratuity paid from driver_payroll"""
    # Try multiple possible column names (schema may vary)
    cur.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'driver_payroll'
        """
    )
    cols = {r[0] for r in cur.fetchall()}
    gratuity_cols = []
    for candidate in ['driver_gratuity', 'driver_gratuity_amount', 'gratuity', 'tips', 'tip_amount']:
        if candidate in cols:
            gratuity_cols.append(candidate)
    # If no explicit gratuity column, estimate from payroll net? We'll default to 0.
    if not gratuity_cols:
        return {}
    # Prefer first found column
    gcol = gratuity_cols[0]
    cur.execute(
        f"""
        SELECT year, SUM(COALESCE({gcol}, 0)) AS total
        FROM driver_payroll
        GROUP BY year
        ORDER BY year
        """
    )
    return {row[0]: float(row[1] or 0) for row in cur.fetchall()}


def fetch_receipt_gratuity(cur):
    """Optional: receipts categorized as gratuity (if such category exists)."""
    cur.execute(
        """
        SELECT COUNT(*) FROM information_schema.columns
        WHERE table_name = 'receipts' AND column_name = 'category'
        """
    )
    has_category = cur.fetchone()[0] > 0
    if not has_category:
        return {}
    cur.execute(
        """
        SELECT EXTRACT(YEAR FROM receipt_date)::int AS year,
               SUM(COALESCE(gross_amount,0))
        FROM receipts
        WHERE LOWER(COALESCE(category,'')) IN ('gratuity','tips','tip','gratuities')
        GROUP BY year
        ORDER BY year
        """
    )
    return {row[0]: float(row[1] or 0) for row in cur.fetchall()}


def calc_gst_included(total, rate=GST_RATE):
    if total is None:
        return 0.0
    return round(total * rate / (1 + rate), 2)


def main():
    conn = get_conn()
    cur = conn.cursor()

    gl = fetch_gl_gratuity(cur)
    payroll = fetch_payroll_gratuity(cur)
    receipts = fetch_receipt_gratuity(cur)

    years = sorted(set(gl.keys()) | set(payroll.keys()) | set(receipts.keys()))

    print("Driver Tips (Gratuity) and GST Impact Summary")
    print("Year | GL 4150 Revenue | Driver Gratuity Paid | Margin | GST (included) | Notes")
    print("-" * 90)

    total_gl = 0.0
    total_paid = 0.0
    total_gst = 0.0

    for y in years:
        gl_rev = gl.get(y, 0.0)
        paid = payroll.get(y, 0.0)
        margin = gl_rev - paid
        gst_included = calc_gst_included(gl_rev)
        total_gl += gl_rev
        total_paid += paid
        total_gst += gst_included
        note = []
        if y not in payroll:
            note.append('no payroll gratuity col')
        if receipts.get(y, 0.0) > 0:
            note.append(f"receipts_cat={receipts.get(y,0.0):.2f}")
        print(f"{y} | ${gl_rev:12,.2f} | ${paid:18,.2f} | ${margin:8,.2f} | ${gst_included:13,.2f} | {'; '.join(note)}")

    print("\nTotals:")
    print(f"GL 4150 Revenue:        ${total_gl:,.2f}")
    print(f"Driver Gratuity Paid:   ${total_paid:,.2f}")
    print(f"Margin (Rev - Paid):    ${total_gl - total_paid:,.2f}")
    print(f"GST (Included) on Rev:  ${total_gst:,.2f}")

    # If GST was not collected on gratuities but should have been (mandatory service charge), then GST liability ~ gst_included on GL 4150.
    print("\nInterpretation:")
    print("- If gratuities are mandatory service charges (not optional tips), they are GST taxable; GST is included in the collected total.")
    print("- Estimated GST component embedded in gratuity revenue above can be remitted; if not collected, this indicates potential shortfall.")
    print("- If gratuities are voluntary tips passed to drivers, typically GST does not apply; verify business practice per charter invoicing.")

    cur.close()
    conn.close()


if __name__ == '__main__':
    main()
