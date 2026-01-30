#!/usr/bin/env python3
"""
Prepare proposed de-duplication actions for Rent (6800) and Utilities (6820) receipts.

READ-ONLY: Emits a suggested KEEP/DELETE plan based on conservative rules:
  - Group by (receipt_date, UPPER(vendor_name), gross_amount)
  - Consider only receipts where category ILIKE '%rent%' OR '%6820%' OR '%util%'
  - Prefer keeping a receipt that is linked to a banking transaction via
    banking_receipt_matching_ledger (if any). If multiple are linked, keep the
    one with the smallest id. If none are linked, keep the one with the smallest id.

Outputs a human-reviewable plan and a CSV with columns:
  group_key, receipt_date, vendor, gross_amount, keep_id, delete_ids

Does NOT execute any DELETE/UPDATE.
"""
import csv
import sys
from collections import defaultdict

import psycopg2

DSN = dict(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')


def fetchall(cur, sql, params=None):
    cur.execute(sql, params or ())
    return cur.fetchall()


def main(out_csv_path: str = None, limit_groups: int = None):
    conn = psycopg2.connect(**DSN)
    cur = conn.cursor()

    rows = fetchall(cur, """
        SELECT r.id,
               r.receipt_date,
               UPPER(COALESCE(r.vendor_name,'')) AS vendor_norm,
               COALESCE(r.gross_amount, 0) AS gross_amount,
               r.category,
               r.created_from_banking,
               CASE WHEN l.receipt_id IS NOT NULL THEN TRUE ELSE FALSE END AS linked_to_bank
        FROM receipts r
        LEFT JOIN banking_receipt_matching_ledger l ON l.receipt_id = r.id
        WHERE COALESCE(r.category,'') ILIKE %s
           OR COALESCE(r.category,'') ILIKE %s
           OR COALESCE(r.category,'') ILIKE %s
        ORDER BY r.receipt_date DESC, r.id DESC
    """, ('%rent%', '%6820%', '%util%'))

    # Bucket duplicates by signature
    buckets = defaultdict(list)
    for rid, rdate, vendor_norm, gross, cat, cfb, linked in rows:
        key = (rdate, round(float(gross or 0), 2), vendor_norm)
        buckets[key].append({
            'id': rid,
            'date': rdate,
            'vendor': vendor_norm,
            'gross': round(float(gross or 0), 2),
            'category': cat,
            'from_banking': bool(cfb),
            'linked': bool(linked),
        })

    # Only consider buckets with >1
    dup_items = [(k, v) for k, v in buckets.items() if len(v) > 1]
    dup_items.sort(key=lambda kv: (kv[0][0], kv[0][2], kv[0][1]), reverse=True)

    print(f"Duplicate buckets (Rent/Utilities): {len(dup_items)}")

    # Prepare optional CSV writer
    writer = None
    if out_csv_path:
        f = open(out_csv_path, 'w', newline='', encoding='utf-8')
        writer = csv.writer(f)
        writer.writerow(['group_key', 'receipt_date', 'vendor', 'gross_amount', 'keep_id', 'delete_ids'])
    else:
        f = None

    printed = 0
    for (rdate, amt, vend), items in dup_items:
        # Choose keep_id: prefer linked to bank; else smallest id
        linked_items = [it for it in items if it['linked']]
        if linked_items:
            keep_id = min(linked_items, key=lambda it: it['id'])['id']
        else:
            keep_id = min(items, key=lambda it: it['id'])['id']

        delete_ids = [it['id'] for it in items if it['id'] != keep_id]

        print(f"\n{rdate}  {vend}  ${amt:,.2f} -> {len(items)} receipts")
        print(f"  KEEP:   {keep_id}")
        print(f"  DELETE: {', '.join(map(str, delete_ids))}")

        if writer:
            writer.writerow([f"{rdate}|{vend}|{amt}", rdate, vend, amt, keep_id, ';'.join(map(str, delete_ids))])

        printed += 1
        if limit_groups and printed >= limit_groups:
            break

    if f:
        f.close()

    cur.close(); conn.close()


if __name__ == '__main__':
    # Usage: python prepare_rent_utilities_dedup_actions.py [out_csv_path] [limit]
    out_csv = sys.argv[1] if len(sys.argv) > 1 else None
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else None
    main(out_csv, limit)
