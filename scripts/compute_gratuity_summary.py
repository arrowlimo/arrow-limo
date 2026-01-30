import os
import sys
import psycopg2
from psycopg2.extras import DictCursor
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP


GST_RATE = Decimal('0.05')  # Alberta GST


def d(val):
    return Decimal(str(val))


def gst_included(amount: Decimal) -> Decimal:
    """Extract GST INCLUDED in gross amount using rate/(1+rate)."""
    return (amount * GST_RATE / (Decimal('1.0') + GST_RATE)).quantize(Decimal('0.01'), ROUND_HALF_UP)


def get_conn():
    # Environment variables (already used in existing codebase)
    host = os.getenv('DB_HOST', 'localhost')
    db = os.getenv('DB_NAME', 'almsdata')
    user = os.getenv('DB_USER', 'postgres')
    password = os.getenv('DB_PASSWORD', '***REDACTED***')
    return psycopg2.connect(host=host, dbname=db, user=user, password=password)


def fetch_invoiced_gratuity(cur):
    # Prefer explicit classification if columns exist, fallback to description pattern
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'charter_charges'
    """)
    cols = {r[0] for r in cur.fetchall()}
    if 'gratuity_type' in cols:
        cur.execute(
            """
            SELECT c.charter_date, cc.amount
            FROM charter_charges cc
            JOIN charters c ON cc.charter_id = c.charter_id
            WHERE cc.amount IS NOT NULL
              AND c.charter_date IS NOT NULL
              AND cc.gratuity_type = 'controlled'
            """
        )
    else:
        cur.execute(
            """
            SELECT c.charter_date, cc.amount
            FROM charter_charges cc
            JOIN charters c ON cc.charter_id = c.charter_id
            WHERE cc.amount IS NOT NULL
              AND c.charter_date IS NOT NULL
              AND LOWER(cc.description) LIKE '%gratuity%'
            """
        )
    return cur.fetchall()


def fetch_driver_gratuity(cur):
    # Driver gratuity actually allocated (money paid or earmarked to driver)
    # Field present in `charters` table: driver_gratuity_amount
    cur.execute(
        """
        SELECT charter_date, driver_gratuity_amount
        FROM charters
        WHERE driver_gratuity_amount IS NOT NULL
          AND driver_gratuity_amount > 0
          AND charter_date IS NOT NULL
        """
    )
    return cur.fetchall()


def fetch_gl_4150(cur):
    # Gratuity revenue from unified_general_ledger (account_code 4150 or name like gratuity)
    cur.execute(
        """
        SELECT transaction_date, COALESCE(credit_amount,0) - COALESCE(debit_amount,0) AS net
        FROM unified_general_ledger
        WHERE (account_code = '4150' OR LOWER(account_name) LIKE '%gratuity%')
          AND transaction_date IS NOT NULL
        """
    )
    return cur.fetchall()


def bucket(records):
    by_month = defaultdict(lambda: Decimal('0'))
    by_year = defaultdict(lambda: Decimal('0'))
    for dt, amt in records:
        if amt is None:
            continue
        year = dt.year
        month = f"{dt.year:04d}-{dt.month:02d}"
        by_month[month] += d(amt)
        by_year[year] += d(amt)
    return by_month, by_year


def format_money(val: Decimal) -> str:
    return f"{val.quantize(Decimal('0.01'), ROUND_HALF_UP):,.2f}"


def main():
    dry_run = '--dry-run' in sys.argv
    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=DictCursor)

        invoiced = fetch_invoiced_gratuity(cur)
        driver_paid = fetch_driver_gratuity(cur)
        gl_rows = fetch_gl_4150(cur)

        inv_month, inv_year = bucket(invoiced)
        drv_month, drv_year = bucket(driver_paid)
        gl_month, gl_year = bucket(gl_rows)

        # Aggregate totals
        total_invoiced = sum(inv_year.values())
        total_driver = sum(drv_year.values())
        total_gl = sum(gl_year.values())
        total_gst_included = sum(gst_included(d(a)) for a in inv_year.values())  # yearly GST sum (aggregate of yearly totals)

        # Exposure: GST on invoiced gratuity not recorded (assuming none captured yet)
        gst_exposure = sum(gst_included(dv) for dv in inv_year.values())

        print("=== Gratuity Summary ===")
        print(f"Total Invoiced Gratuity (charter_charges): {format_money(total_invoiced)}")
        print(f"Total Driver Gratuity (charters.driver_gratuity_amount): {format_money(total_driver)}")
        print(f"Total GL 4150 Recorded (unified_general_ledger): {format_money(total_gl)}")
        print(f"Estimated GST Included (5% rate, tax-included method): {format_money(gst_exposure)}")
        variance_gl_vs_invoiced = total_invoiced - total_gl
        print(f"Variance (Invoiced - GL 4150): {format_money(variance_gl_vs_invoiced)}")
        variance_invoiced_vs_driver = total_invoiced - total_driver
        print(f"Variance (Invoiced - Driver Paid): {format_money(variance_invoiced_vs_driver)}")
        print()

        print("--- Yearly Breakdown ---")
        years = sorted(set(list(inv_year.keys()) + list(drv_year.keys()) + list(gl_year.keys())))
        print("Year | Invoiced | Driver Paid | GL 4150 | GST Included | Invoiced-Driver | Invoiced-GL")
        for y in years:
            inv = inv_year.get(y, Decimal('0'))
            drv = drv_year.get(y, Decimal('0'))
            glv = gl_year.get(y, Decimal('0'))
            gst_val = gst_included(inv) if inv else Decimal('0')
            print(f"{y} | {format_money(inv)} | {format_money(drv)} | {format_money(glv)} | {format_money(gst_val)} | {format_money(inv-drv)} | {format_money(inv-glv)}")

        print()
        print("--- Top 12 Months (Invoiced Gratuity) ---")
        top_months = sorted(inv_month.items(), key=lambda x: x[1], reverse=True)[:12]
        print("Month | Invoiced | GST Included | Driver Paid | GL 4150")
        for m, amt in top_months:
            gst_val = gst_included(amt)
            drv = drv_month.get(m, Decimal('0'))
            glv = gl_month.get(m, Decimal('0'))
            print(f"{m} | {format_money(amt)} | {format_money(gst_val)} | {format_money(drv)} | {format_money(glv)}")

        if not dry_run:
            # Optionally write a concise markdown summary file
            summary_path = os.path.join('reports', 'gratuity_summary_latest.md')
            os.makedirs('reports', exist_ok=True)
            with open(summary_path, 'w', encoding='utf-8') as f:
                f.write("# Gratuity Summary\n\n")
                f.write(f"Total Invoiced Gratuity: {format_money(total_invoiced)}\n")
                f.write(f"Total Driver Gratuity: {format_money(total_driver)}\n")
                f.write(f"Total GL 4150 Recorded: {format_money(total_gl)}\n")
                f.write(f"Estimated GST Included: {format_money(gst_exposure)}\n")
                f.write(f"Variance Invoiced vs Driver: {format_money(variance_invoiced_vs_driver)}\n")
                f.write(f"Variance Invoiced vs GL: {format_money(variance_gl_vs_invoiced)}\n\n")
                f.write("## Yearly Breakdown\n")
                f.write("Year | Invoiced | Driver Paid | GL 4150 | GST Included | Invoiced-Driver | Invoiced-GL\n")
                for y in years:
                    inv = inv_year.get(y, Decimal('0'))
                    drv = drv_year.get(y, Decimal('0'))
                    glv = gl_year.get(y, Decimal('0'))
                    gst_val = gst_included(inv) if inv else Decimal('0')
                    f.write(f"{y} | {format_money(inv)} | {format_money(drv)} | {format_money(glv)} | {format_money(gst_val)} | {format_money(inv-drv)} | {format_money(inv-glv)}\n")
                f.write("\n## Top 12 Months (Invoiced)\n")
                f.write("Month | Invoiced | GST Included | Driver Paid | GL 4150\n")
                for m, amt in top_months:
                    gst_val = gst_included(amt)
                    drv = drv_month.get(m, Decimal('0'))
                    glv = gl_month.get(m, Decimal('0'))
                    f.write(f"{m} | {format_money(amt)} | {format_money(gst_val)} | {format_money(drv)} | {format_money(glv)}\n")
            print(f"\nWrote summary file: {summary_path}")

    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == '__main__':
    main()
