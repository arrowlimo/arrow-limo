import argparse
import psycopg2
from datetime import datetime

def get_db_connection():
    import os
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        dbname=os.environ.get('DB_NAME', 'almsdata'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD', '***REMOVED***')
    )

def print_header(mode):
    print("="*90)
    print("Recalculate GST for Gratuity Receipts (taxable)")
    print(f"Generated: {datetime.now():%Y-%m-%d %H:%M:%S} | Mode: {mode}")
    print("="*90)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--write', action='store_true', help='Apply changes')
    args = parser.parse_args()
    mode = 'WRITE' if args.write else 'DRY-RUN'
    print_header(mode)

    conn = get_db_connection()
    cur = conn.cursor()

    # Identify gratuity receipts with gst_amount = 0 (or NULL) but gross_amount > 0
    cur.execute(
        """
        SELECT receipt_id, receipt_date, vendor_name, description, category,
               gross_amount, gst_amount, net_amount
        FROM receipts
        WHERE gross_amount > 0
          AND (LOWER(category) = 'gratuity' OR LOWER(description) LIKE '%gratuity%')
          AND COALESCE(gst_amount, 0) = 0
        ORDER BY receipt_date ASC
        """
    )
    rows = cur.fetchall()
    count = len(rows)
    total_gross = sum(r[5] for r in rows) if rows else 0
    print(f"Found {count} gratuity receipts with GST=0 | Total gross: ${float(total_gross):,.2f}")

    if count == 0:
        print("No updates needed.")
        cur.close()
        conn.close()
        return

    # Preview first 10
    print("\nSample (first 10):")
    for r in rows[:10]:
        rid, rdate, vendor, desc, cat, gross, gst, net = r
        expected_gst = float(gross) * 0.05 / 1.05
        expected_net = float(gross) - expected_gst
        print(f"  {rid} | {rdate} | {vendor or ''} | {cat or ''} | gross=${float(gross):,.2f} | gst=${expected_gst:,.2f} | net=${expected_net:,.2f}")

    if args.write:
        # Backup affected rows before update
        backup_name = f"receipts_gratuity_backup_{datetime.now():%Y%m%d_%H%M%S}"
        cur.execute(f"""
            CREATE TABLE {backup_name} AS
            SELECT * FROM receipts
            WHERE gross_amount > 0
              AND (LOWER(category) = 'gratuity' OR LOWER(description) LIKE '%gratuity%')
              AND COALESCE(gst_amount, 0) = 0
        """)
        print(f"Backup created: {backup_name} ({count} rows)")

        # Apply GST included recalculation
        cur.execute(
            """
            UPDATE receipts
            SET gst_amount = ROUND(gross_amount * 0.05 / 1.05, 2),
                net_amount = ROUND(gross_amount - (gross_amount * 0.05 / 1.05), 2)
            WHERE gross_amount > 0
              AND (LOWER(category) = 'gratuity' OR LOWER(description) LIKE '%gratuity%')
              AND COALESCE(gst_amount, 0) = 0
            """
        )
        updated = cur.rowcount
        conn.commit()
        print(f"Updated {updated} gratuity receipts with GST included (AB 5%)")

        # Post-check totals
        cur.execute(
            """
            SELECT COUNT(*), SUM(gst_amount), SUM(net_amount)
            FROM receipts
            WHERE gross_amount > 0
              AND (LOWER(category) = 'gratuity' OR LOWER(description) LIKE '%gratuity%')
              AND gst_amount > 0
            """
        )
        c2, sum_gst, sum_net = cur.fetchone()
        print(f"Now {c2} gratuity receipts show GST > 0 | GST sum=${float(sum_gst or 0):,.2f} | Net sum=${float(sum_net or 0):,.2f}")
    else:
        print("\nDRY-RUN only. Re-run with --write to apply updates.")

    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
