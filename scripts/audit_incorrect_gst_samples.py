import argparse
import psycopg2
from datetime import datetime

def get_db_connection():
    # Mirrors get_db_connection pattern used across repo
    import os
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        dbname=os.environ.get('DB_NAME', 'almsdata'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD', '***REMOVED***')
    )

def print_header():
    print("="*80)
    print("GST Audit - Sample Incorrect Calculations")
    print(f"Generated: {datetime.now():%Y-%m-%d %H:%M:%S}")
    print("="*80)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sample-size', type=int, default=100)
    args = parser.parse_args()

    print_header()
    conn = get_db_connection()
    cur = conn.cursor()

    # Identify receipts where gst_amount deviates from included formula by > $0.02
    # gst_expected = gross * 0.05 / 1.05 for Alberta
    cur.execute(
        """
        WITH calc AS (
            SELECT receipt_id, receipt_date, vendor_name, description, category,
                   gross_amount,
                   gst_amount,
                   ROUND(gross_amount * 0.05 / 1.05, 2) AS gst_expected,
                   ROUND(gross_amount - (gross_amount * 0.05 / 1.05), 2) AS net_expected,
                   net_amount
            FROM receipts
            WHERE gross_amount IS NOT NULL AND gross_amount > 0
              AND gst_amount IS NOT NULL AND net_amount IS NOT NULL
        )
        SELECT receipt_id, receipt_date, vendor_name, category,
               gross_amount, gst_amount, gst_expected, net_amount, net_expected,
               ABS(gst_amount - gst_expected) AS gst_diff
        FROM calc
        WHERE ABS(gst_amount - gst_expected) > 0.02
        ORDER BY gst_diff DESC
        LIMIT %s
        """,
        (args.sample_size,)
    )

    rows = cur.fetchall()
    if not rows:
        print("No incorrect GST samples found above threshold.")
        return

    # Tally by likely cause
    causes = {
        'possible_hst_or_other_province': 0,
        'legacy_import_expense_column': 0,
        'manual_entry_rounded': 0,
        'possible_gst_added_not_included': 0,
        'unknown': 0,
    }

    print("\nTop samples:")
    print("   Date       | Vendor                         | Gross     | GST      | Expected  | Diff   | Category")
    print("   -----------+-------------------------------+-----------+----------+----------+--------+----------------")
    for r in rows[:20]:
        rid, rdate, vendor, cat, gross, gst, expected, net, net_exp, diff = r
        vendor_disp = (vendor or 'UNKNOWN')[:30].ljust(30)
        print(f"   {rdate} | {vendor_disp} | {gross:>9,.2f} | {gst:>8,.2f} | {expected:>8,.2f} | {diff:>6.2f} | {cat or ''}")

        # Simple heuristic classification
        if cat and cat.lower() in ('insurance', 'insurance - vehicle liability', 'rent', 'charter_revenue'):
            causes['manual_entry_rounded'] += 1
        elif gst == 0 and gross > 100 and cat and cat.lower() in ('office_supplies','maintenance','fuel','communication','bank_fees'):
            causes['legacy_import_expense_column'] += 1
        # Ensure numeric comparison using float
        gf = float(gross)
        gstf = float(gst)
        if gstf > (gf * 0.06 / 1.06):
            causes['possible_hst_or_other_province'] += 1
        elif abs((gf * 0.05) - gstf) < 0.02:
            causes['possible_gst_added_not_included'] += 1
        else:
            causes['unknown'] += 1

    print("\nCause summary (heuristic):")
    for k, v in causes.items():
        print(f"   - {k}: {v}")

    # Provinces breakdown if available via vendor hints
    print("\nHints:")
    print("   - Alberta GST included method: gst = gross * 0.05 / 1.05")
    print("   - If receipts are from ON (HST 13%), expect gst≈gross * 0.13 / 1.13")
    print("   - Legacy imports may have gross_amount=0 and expense filled; already migrated in Nov 30 cleanup")

    cur.close()
    conn.close()
    print("\nDone.")

if __name__ == '__main__':
    main()
