#!/usr/bin/env python3
"""
Generic updater: add GST to auto financing payments by vendor/description keywords.

Usage:
  python -X utf8 scripts/update_financing_gst_on_receipts.py --vendors "heffner,woodridge,woodridge ford,infiniti,cadillac,escalade" --dry-run
  python -X utf8 scripts/update_financing_gst_on_receipts.py --vendors "woodridge,woodridge ford" --apply --rate 0.05 --set-category "Vehicle Financing"

Notes:
- Matches receipts where vendor_name or description contains any provided keyword (case-insensitive)
- Only updates rows with gst_amount = 0 and gross_amount > 0
- GST model: included in gross (gst = gross * rate / (1 + rate))
- Writes audit to receipt_gst_adjustment_audit
"""

import argparse
import psycopg2

DB = dict(dbname='almsdata', user='postgres', password='***REDACTED***', host='localhost')


def get_cols(conn, table):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name=%s
            ORDER BY ordinal_position
        """, (table,))
        return {r[0] for r in cur.fetchall()}


def ensure_audit_table(conn):
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS receipt_gst_adjustment_audit (
                id SERIAL PRIMARY KEY,
                receipt_id INTEGER NOT NULL,
                before_gst NUMERIC(12,2),
                after_gst NUMERIC(12,2),
                before_category TEXT,
                after_category TEXT,
                rate_applied NUMERIC(6,4) NOT NULL,
                reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()


def find_targets(conn, keywords):
    # Detect id column
    with conn.cursor() as cur:
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='receipts' AND column_name IN ('receipt_id','id') ORDER BY ordinal_position LIMIT 1")
        id_col = cur.fetchone()
    if not id_col:
        raise SystemExit('receipts id column (receipt_id/id) not found')
    id_col = id_col[0]

    like_clauses = []
    params = []
    for kw in keywords:
        like_clauses.append("LOWER(COALESCE(vendor_name,'')) LIKE %s")
        params.append(f"%{kw}%")
        like_clauses.append("LOWER(COALESCE(description,'')) LIKE %s")
        params.append(f"%{kw}%")
    where_like = " OR ".join(like_clauses) if like_clauses else "FALSE"

    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT {id_col} AS rid, receipt_date, vendor_name, description, gross_amount, gst_amount, category
            FROM receipts
            WHERE ({where_like})
              AND COALESCE(gross_amount,0) > 0
              AND COALESCE(gst_amount,0) = 0
            ORDER BY receipt_date
            """,
            params,
        )
        return id_col, cur.fetchall()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--vendors', required=True, help='Comma-separated vendor/description keywords (case-insensitive)')
    ap.add_argument('--rate', type=float, default=0.05, help='GST/HST rate as decimal (default 0.05)')
    ap.add_argument('--apply', action='store_true', help='Apply updates (default dry-run)')
    ap.add_argument('--set-category', default='Vehicle Financing', help='Category to set on update')
    ap.add_argument('--keep-category', action='store_true', help='Do not change category on update')
    args = ap.parse_args()

    keywords = [kw.strip().lower() for kw in args.vendors.split(',') if kw.strip()]
    if not keywords:
        raise SystemExit('No vendor keywords provided')

    conn = psycopg2.connect(**DB)
    ensure_audit_table(conn)
    receipts_cols = get_cols(conn, 'receipts')
    id_col, rows = find_targets(conn, keywords)

    print("\n" + "="*96)
    print("FINANCING GST UPDATE - DRY RUN" if not args.apply else "FINANCING GST UPDATE - APPLYING")
    print("="*96)
    print(f"Keywords: {keywords}")
    print(f"Found {len(rows):,} receipts without GST matching keywords.")

    total_gross = 0.0
    total_gst_add = 0.0
    updates = []
    for rid, rdate, vendor, desc, gross, gst, category in rows:
        g = float(gross)
        gst_new = round(g * args.rate / (1 + args.rate), 2)
        total_gross += g
        total_gst_add += gst_new
        updates.append((rid, gst_new, category))

    print(f"Total gross impacted: ${total_gross:,.2f}")
    print(f"GST to add (@{args.rate*100:.1f}% included): ${total_gst_add:,.2f}")

    if not args.apply:
        print("\nDry run complete. Re-run with --apply to write changes.")
        conn.close()
        return

    set_category = (not args.keep_category) and ('category' in receipts_cols)
    set_clause = "gst_amount = %s" + (", category = %s" if set_category else "")

    updated = 0
    with conn:
        with conn.cursor() as cur:
            for rid, gst_new, prev_cat in updates:
                params = [gst_new]
                new_cat = prev_cat
                if set_category:
                    new_cat = args.set_category
                    params.append(new_cat)
                params.append(rid)
                cur.execute(
                    f"UPDATE receipts SET {set_clause} WHERE {id_col} = %s",
                    params,
                )
                updated += cur.rowcount
                cur.execute(
                    """
                    INSERT INTO receipt_gst_adjustment_audit
                        (receipt_id, before_gst, after_gst, before_category, after_category, rate_applied, reason)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (rid, 0.00, gst_new, prev_cat, new_cat, args.rate, f"Financing GST included adjustment: keywords={keywords}"),
                )

    print(f"\nUpdated {updated:,} receipts. Audit entries written.")
    conn.close()


if __name__ == '__main__':
    main()
