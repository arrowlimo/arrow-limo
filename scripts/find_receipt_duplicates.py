#!/usr/bin/env python3
"""
Report potential duplicate receipts, with a focus on Rent (6800) and Utilities (6820).
- Duplicates by bank_id: same bank transaction linked to >1 receipt
- Duplicates by (receipt_date, vendor_name, gross_amount): exact duplicates
- Near-duplicates by (receipt_date, rounded gross_amount, vendor_name) within small tolerance

READ-ONLY: Does not modify data. Designed to be idempotent and safe after a crash.
"""
import psycopg2
from collections import defaultdict

DSN = dict(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')

RENT_CODES = {'6800', 'Rent', 'rent'}
UTIL_CODES = {'6820', 'Utilities', 'utilities'}


def fetchall(cur, sql, params=None):
    cur.execute(sql, params or ())
    return cur.fetchall()


def main():
    conn = psycopg2.connect(**DSN)
    cur = conn.cursor()

    print("\n=== DUPLICATES BY BANK TRANSACTION (via banking_receipt_matching_ledger) ===")
    rows = fetchall(cur, """
        SELECT l.banking_transaction_id, COUNT(*) AS cnt
        FROM banking_receipt_matching_ledger l
        GROUP BY l.banking_transaction_id
        HAVING COUNT(*) > 1
        ORDER BY cnt DESC
    """)
    print(f"Groups: {len(rows)}")
    for txn_id, cnt in rows[:50]:
        print(f"\nBank txn {txn_id} -> {cnt} receipts")
        det = fetchall(cur, """
            SELECT r.id, r.receipt_date, r.vendor_name, r.gross_amount, r.category, r.source_system, r.source_reference
            FROM banking_receipt_matching_ledger l
            JOIN receipts r ON r.id = l.receipt_id
            WHERE l.banking_transaction_id = %s
            ORDER BY r.receipt_date, r.id
        """, (txn_id,))
        for r in det:
            rid, rdate, vendor, gross, cat, src_sys, src_ref = r
            print(f"  receipt {rid}  {rdate}  {vendor or ''}  ${gross or 0:.2f}  {cat or ''}  {src_sys or ''}  {src_ref or ''}")

    print("\n=== EXACT DUPLICATES BY (date, vendor, gross_amount) ===")
    rows = fetchall(cur, """
        SELECT receipt_date, UPPER(COALESCE(vendor_name,'')) AS v, gross_amount, COUNT(*) AS cnt
        FROM receipts
        GROUP BY receipt_date, v, gross_amount
        HAVING COUNT(*) > 1
        ORDER BY cnt DESC, receipt_date DESC
    """)
    print(f"Groups: {len(rows)}")
    for rdate, v, gross, cnt in rows[:50]:
        print(f"\n{rdate}  {v}  ${gross or 0:.2f}  -> {cnt} receipts")
        det = fetchall(cur, """
            SELECT id, category, source_system, source_reference, created_from_banking
            FROM receipts
            WHERE receipt_date = %s AND UPPER(COALESCE(vendor_name,'')) = %s AND COALESCE(gross_amount,0) = %s
            ORDER BY id
        """, (rdate, v, gross or 0))
        for rid, cat, src_sys, src_ref, cfb in det:
            print(f"  receipt {rid}  category={cat or ''}  {src_sys or ''}  {src_ref or ''}  from_banking={cfb}")

    print("\n=== RENT/UTILITIES FOCUS (category 6800/6820) POSSIBLE DUPES ===")
    # IMPORTANT: Avoid literal % in query string when passing params; use placeholders to prevent
    # Python string-formatting from interpreting %r/%u etc. We parameterize the ILIKE patterns.
    rows = fetchall(cur, """
        SELECT id, receipt_date, vendor_name, gross_amount, category
        FROM receipts
        WHERE COALESCE(category,'') ILIKE %s
           OR COALESCE(category,'') ILIKE %s
           OR COALESCE(category,'') ILIKE %s
        ORDER BY receipt_date DESC
    """, ('%rent%', '%6820%', '%util%'))
    # Bucket by (date, rounded amount, normalized vendor)
    buckets = defaultdict(list)
    for rid, rdate, vendor, gross, cat in rows:
        key = (rdate, round(float(gross or 0), 2), (vendor or '').strip().upper())
        buckets[key].append((rid, None, cat))
    dup_keys = {k: v for k, v in buckets.items() if len(v) > 1}
    print(f"Buckets with >1 receipt: {len(dup_keys)}")
    count_printed = 0
    for (rdate, amt, vend), items in sorted(dup_keys.items(), key=lambda x: x[0][0], reverse=True):
        print(f"\n{rdate}  {vend}  ${amt:,.2f} -> {len(items)} receipts")
        for rid, bank_id, cat in items:
            print(f"  receipt {rid}  category={cat or ''}")
        count_printed += 1
        if count_printed >= 50:
            break

    cur.close(); conn.close()

if __name__ == '__main__':
    main()
