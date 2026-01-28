#!/usr/bin/env python3
"""
Revert GST adjustments made by financing updater scripts using the audit log.

Features:
- Filters by audit reason substring (case-insensitive)
- Optional vendor/description keyword filter to constrain affected receipts
- Dry-run by default; --apply to write changes
- Writes a new audit row per revert with before/after values

Usage examples:
  python -X utf8 scripts/revert_gst_adjustments.py --reason "Heffner auto loan" --dry-run
  python -X utf8 scripts/revert_gst_adjustments.py --reason "Financing GST included adjustment" --vendors "woodridge, cadillac, infiniti" --apply

Safety:
- Only updates receipts referenced in receipt_gst_adjustment_audit
- Restores gst_amount to before_gst and category to before_category from the latest matching audit row
"""

import argparse
import psycopg2
from collections import defaultdict

DB = dict(dbname='almsdata', user='postgres', password='***REMOVED***', host='localhost')


def find_latest_audits(conn, reason_substr: str):
    """Return latest audit row per receipt_id where reason ILIKE %substr%."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT a.receipt_id, a.before_gst, a.after_gst, a.before_category, a.after_category, a.rate_applied, a.reason, a.created_at
            FROM receipt_gst_adjustment_audit a
            WHERE a.reason ILIKE %s
            ORDER BY a.receipt_id, a.created_at DESC
            """,
            (f"%{reason_substr}%",),
        )
        rows = cur.fetchall()

    latest = {}
    for rid, before_gst, after_gst, before_cat, after_cat, rate, reason, created_at in rows:
        if rid not in latest:
            latest[rid] = {
                'receipt_id': rid,
                'before_gst': float(before_gst or 0.0),
                'after_gst': float(after_gst or 0.0),
                'before_category': before_cat,
                'after_category': after_cat,
                'rate_applied': float(rate or 0.0),
                'reason': reason,
                'created_at': created_at,
            }
    return latest


def filter_by_vendors(conn, receipt_ids, keywords):
    if not keywords:
        return set(receipt_ids)
    # detect id column first
    with conn.cursor() as cur:
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name='receipts' AND column_name IN ('receipt_id','id')
            ORDER BY ordinal_position LIMIT 1
        """)
        id_col = cur.fetchone()[0]
    like_clauses = []
    params = []
    for kw in keywords:
        like_clauses.append("LOWER(COALESCE(vendor_name,'')) LIKE %s")
        params.append(f"%{kw}%")
        like_clauses.append("LOWER(COALESCE(description,'')) LIKE %s")
        params.append(f"%{kw}%")
    where_like = " OR ".join(like_clauses)

    if not receipt_ids:
        return set()
    id_placeholders = ",".join(["%s"] * len(receipt_ids))
    params_ids = list(receipt_ids)
    query = f"""
        SELECT {id_col} AS rid
        FROM receipts r
        WHERE ( {where_like} )
          AND {id_col} IN ({id_placeholders})
    """
    with conn.cursor() as cur:
        cur.execute(query, params + params_ids)
        return {row[0] for row in cur.fetchall()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--reason', required=True, help='Substring to match in audit reason (case-insensitive)')
    ap.add_argument('--vendors', default='', help='Optional comma-separated vendor/description keywords')
    ap.add_argument('--apply', action='store_true', help='Apply changes (default: dry-run)')
    args = ap.parse_args()

    keywords = [kw.strip().lower() for kw in args.vendors.split(',') if kw.strip()]

    conn = psycopg2.connect(**DB)

    latest = find_latest_audits(conn, args.reason)
    if not latest:
        print("No audit rows found for reason substring:", args.reason)
        return

    candidate_ids = list(latest.keys())
    # Optional vendor filtering
    if keywords:
        allowed = filter_by_vendors(conn, candidate_ids, keywords)
    else:
        allowed = set(candidate_ids)

    # Prepare updates
    to_update = [latest[rid] for rid in candidate_ids if rid in allowed]

    total_remove_gst = sum(item['after_gst'] - item['before_gst'] for item in to_update)
    print("\n" + "="*96)
    print("GST REVERSION - DRY RUN" if not args.apply else "GST REVERSION - APPLYING")
    print("="*96)
    print(f"Reason contains: {args.reason}")
    if keywords:
        print(f"Vendor filters: {keywords}")
    print(f"Receipts to revert: {len(to_update):,}")
    print(f"GST to remove (sum of deltas): ${total_remove_gst:,.2f}")

    if not args.apply:
        print("\nDry run complete. Re-run with --apply to write changes.")
        conn.close()
        return

    # Detect id column
    with conn.cursor() as cur:
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='receipts' AND column_name IN ('receipt_id','id') ORDER BY ordinal_position LIMIT 1")
        id_col = cur.fetchone()[0]

    updated = 0
    with conn:
        with conn.cursor() as cur:
            for item in to_update:
                rid = item['receipt_id']
                before_gst = item['before_gst']
                after_gst = item['after_gst']
                before_cat = item['before_category']
                after_cat = item['after_category']

                # Update receipts: restore gst and category
                cur.execute(
                    f"UPDATE receipts SET gst_amount = %s, category = %s WHERE {id_col} = %s",
                    (before_gst, before_cat, rid),
                )
                updated += cur.rowcount

                # Write revert audit row
                cur.execute(
                    """
                    INSERT INTO receipt_gst_adjustment_audit
                        (receipt_id, before_gst, after_gst, before_category, after_category, rate_applied, reason)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (rid, after_gst, before_gst, after_cat, before_cat, 0.0, f"Revert GST adjustment (was: {item['reason']})"),
                )

    print(f"\nReverted {updated:,} receipts. Audit entries written.")
    conn.close()


if __name__ == '__main__':
    main()
