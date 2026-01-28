import os
import sys
from decimal import Decimal, ROUND_HALF_UP
import psycopg2
from psycopg2.extras import DictCursor

GST_RATE = Decimal('0.05')  # Alberta GST


def gst_included(amount: Decimal) -> Decimal:
    if amount is None:
        return Decimal('0.00')
    return (amount * GST_RATE / (Decimal('1.0') + GST_RATE)).quantize(Decimal('0.01'), ROUND_HALF_UP)


def get_conn():
    host = os.getenv('DB_HOST', 'localhost')
    db = os.getenv('DB_NAME', 'almsdata')
    user = os.getenv('DB_USER', 'postgres')
    password = os.getenv('DB_PASSWORD', '***REMOVED***')
    return psycopg2.connect(host=host, dbname=db, user=user, password=password)


def ensure_columns(cur, apply_changes: bool):
    needed = {
        'gratuity_type': "ALTER TABLE charter_charges ADD COLUMN gratuity_type VARCHAR(20)",
        'gst_amount': "ALTER TABLE charter_charges ADD COLUMN gst_amount NUMERIC(12,2)",
        'tax_rate': "ALTER TABLE charter_charges ADD COLUMN tax_rate NUMERIC(5,4)"
    }
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'charter_charges'
    """)
    existing = {r[0] for r in cur.fetchall()}
    to_add = [c for c in needed if c not in existing]
    if not to_add:
        return []
    if apply_changes:
        for c in to_add:
            cur.execute(needed[c])
    return to_add


def fetch_controlled_gratuity(cur):
    # Identify invoiced/controlled gratuity lines
    cur.execute(
        """
        SELECT cc.charge_id, cc.charter_id, cc.description, cc.amount, c.charter_date
        FROM charter_charges cc
        JOIN charters c ON c.charter_id = cc.charter_id
        WHERE cc.amount IS NOT NULL
          AND cc.amount > 0
          AND LOWER(cc.description) LIKE '%gratuity%'
        ORDER BY c.charter_date
        """
    )
    return cur.fetchall()


def main():
    apply_flag = '--apply' in sys.argv
    limit = None
    for i, arg in enumerate(sys.argv):
        if arg == '--limit' and i + 1 < len(sys.argv):
            try:
                limit = int(sys.argv[i + 1])
            except ValueError:
                pass

    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=DictCursor)
        added_cols = ensure_columns(cur, apply_flag)

        rows = fetch_controlled_gratuity(cur)
        if limit:
            rows = rows[:limit]

        total_gross = Decimal('0.00')
        total_gst = Decimal('0.00')
        updates = []
        for r in rows:
            amt = Decimal(str(r['amount']))
            gst_val = gst_included(amt)
            total_gross += amt
            total_gst += gst_val
            updates.append((r['charge_id'], gst_val, amt))

        print("Controlled Gratuity Lines Found:", len(rows))
        print(f"Total Gross Controlled Gratuity: {total_gross:.2f}")
        print(f"GST Included (5%): {total_gst:.2f}")
        if added_cols:
            print("Added columns:", ", ".join(added_cols) if apply_flag else f"(would add: {', '.join(added_cols)})")

        if apply_flag:
            # Update lines that are not yet classified (only where gst_amount IS NULL OR =0)
            update_sql = """
            UPDATE charter_charges
               SET gst_amount = %s,
                   tax_rate = %s,
                   gratuity_type = 'controlled'
             WHERE charge_id = %s
               AND (gst_amount IS NULL OR gst_amount = 0)
            """
            for charge_id, gst_val, gross in updates:
                cur.execute(update_sql, (str(gst_val), str(GST_RATE), charge_id))
            conn.commit()
            print(f"Applied GST classification to {len(updates)} lines.")
        else:
            print("Dry-run: no database updates applied. Use --apply to commit.")

    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == '__main__':
    main()
