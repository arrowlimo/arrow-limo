#!/usr/bin/env python3
"""
Analyze duplicate receipts to check if invoice numbers/references match across duplicates.

For each duplicate group (by date, vendor, amount), check if:
1. All duplicates have the same source_reference / invoice number
2. Duplicates have different source_reference values (mismatched invoices)
3. Some have source_reference, others don't (partial data)

Focus on Rent/Utilities duplicates to understand the invoice matching patterns.
"""
import psycopg2
from collections import defaultdict

DSN = dict(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')


def main():
    conn = psycopg2.connect(**DSN)
    conn.autocommit = True
    cur = conn.cursor()

    print("=== DUPLICATE INVOICE NUMBER ANALYSIS ===\n")

    # Get all rent/utilities receipts
    cur.execute("""
        SELECT id, receipt_date, vendor_name, gross_amount, category,
               source_reference, source_system, source_hash, description,
               created_from_banking
        FROM receipts
        WHERE COALESCE(category,'') ILIKE %s
           OR COALESCE(category,'') ILIKE %s
           OR COALESCE(category,'') ILIKE %s
        ORDER BY receipt_date DESC, id
    """, ('%rent%', '%6820%', '%util%'))

    rows = cur.fetchall()
    print(f"Total Rent/Utilities receipts: {len(rows):,}\n")

    # Group by (date, vendor_norm, amount)
    buckets = defaultdict(list)
    for row in rows:
        rid, rdate, vendor, amount, cat, src_ref, src_sys, src_hash, desc, cfb = row
        key = (rdate, (vendor or '').strip().upper(), round(float(amount or 0), 2))
        buckets[key].append({
            'id': rid,
            'date': rdate,
            'vendor': vendor,
            'amount': round(float(amount or 0), 2),
            'category': cat,
            'source_reference': src_ref,
            'source_system': src_sys,
            'source_hash': src_hash,
            'description': desc,
            'created_from_banking': cfb,
        })

    # Filter to duplicates only
    dup_buckets = {k: v for k, v in buckets.items() if len(v) > 1}
    print(f"Duplicate groups: {len(dup_buckets):,}\n")

    # Analyze matching patterns
    matching_refs = 0
    mismatched_refs = 0
    partial_refs = 0
    no_refs = 0

    matching_examples = []
    mismatched_examples = []
    partial_examples = []

    for (rdate, vendor, amt), items in sorted(dup_buckets.items(), key=lambda x: (x[0][0], x[0][2]), reverse=True):
        refs = [it['source_reference'] for it in items]
        unique_refs = set(r for r in refs if r)
        has_null = None in refs or '' in refs

        if len(unique_refs) == 0:
            # All null/empty
            no_refs += 1
        elif len(unique_refs) == 1 and not has_null:
            # All same non-null reference
            matching_refs += 1
            if len(matching_examples) < 5:
                matching_examples.append((rdate, vendor, amt, items))
        elif len(unique_refs) == 1 and has_null:
            # Some have ref, some don't
            partial_refs += 1
            if len(partial_examples) < 5:
                partial_examples.append((rdate, vendor, amt, items))
        else:
            # Multiple different references
            mismatched_refs += 1
            if len(mismatched_examples) < 5:
                mismatched_examples.append((rdate, vendor, amt, items))

    print("=== INVOICE MATCHING PATTERNS ===\n")
    print(f"All duplicates have SAME invoice ref:      {matching_refs:,}")
    print(f"Duplicates have DIFFERENT invoice refs:    {mismatched_refs:,}")
    print(f"Some have ref, some don't (PARTIAL):       {partial_refs:,}")
    print(f"None have invoice refs (all null):         {no_refs:,}")
    print(f"TOTAL duplicate groups:                    {len(dup_buckets):,}")

    print("\n=== MATCHING INVOICE EXAMPLES (same ref across all duplicates) ===")
    for rdate, vendor, amt, items in matching_examples[:5]:
        print(f"\n{rdate}  {vendor}  ${amt:,.2f} -> {len(items)} receipts")
        ref = items[0]['source_reference']
        print(f"  Invoice ref: {ref}")
        for it in items:
            print(f"    receipt {it['id']}  {it['source_system'] or ''}  hash={it['source_hash'][:12] if it['source_hash'] else ''}")

    print("\n=== MISMATCHED INVOICE EXAMPLES (different refs in same group) ===")
    for rdate, vendor, amt, items in mismatched_examples[:5]:
        print(f"\n{rdate}  {vendor}  ${amt:,.2f} -> {len(items)} receipts")
        for it in items:
            print(f"    receipt {it['id']}  ref={it['source_reference'] or '(null)'}  {it['source_system'] or ''}  hash={it['source_hash'][:12] if it['source_hash'] else ''}")

    print("\n=== PARTIAL INVOICE DATA EXAMPLES (some have ref, some don't) ===")
    for rdate, vendor, amt, items in partial_examples[:5]:
        print(f"\n{rdate}  {vendor}  ${amt:,.2f} -> {len(items)} receipts")
        for it in items:
            has_ref = "✓" if it['source_reference'] else "✗"
            print(f"    receipt {it['id']}  {has_ref} ref={it['source_reference'] or '(null)'}  {it['source_system'] or ''}")

    # Deep dive: Check source_hash uniqueness within duplicate groups
    print("\n=== SOURCE_HASH ANALYSIS ===")
    unique_hash_groups = 0
    duplicate_hash_groups = 0

    for (rdate, vendor, amt), items in dup_buckets.items():
        hashes = [it['source_hash'] for it in items if it['source_hash']]
        unique_hashes = len(set(hashes))
        
        if unique_hashes == len(items):
            unique_hash_groups += 1
        else:
            duplicate_hash_groups += 1

    print(f"Groups where all duplicates have UNIQUE source_hash: {unique_hash_groups:,}")
    print(f"Groups where duplicates share same source_hash:      {duplicate_hash_groups:,}")

    # Check: Are mismatched refs correlated with different source_systems?
    print("\n=== SOURCE_SYSTEM CORRELATION ===")
    single_system_dups = 0
    multi_system_dups = 0

    for (rdate, vendor, amt), items in dup_buckets.items():
        systems = set(it['source_system'] for it in items if it['source_system'])
        if len(systems) <= 1:
            single_system_dups += 1
        else:
            multi_system_dups += 1

    print(f"Duplicate groups from SINGLE source_system:   {single_system_dups:,}")
    print(f"Duplicate groups from MULTIPLE source_systems: {multi_system_dups:,}")

    # Sample: Show a multi-system duplicate
    print("\n=== MULTI-SYSTEM DUPLICATE EXAMPLE ===")
    for (rdate, vendor, amt), items in dup_buckets.items():
        systems = set(it['source_system'] for it in items if it['source_system'])
        if len(systems) > 1:
            print(f"\n{rdate}  {vendor}  ${amt:,.2f} -> {len(items)} receipts from {len(systems)} systems")
            for it in items:
                print(f"  receipt {it['id']}  system={it['source_system'] or '(null)'}  ref={it['source_reference'] or '(null)'}")
            break

    cur.close()
    conn.close()


if __name__ == '__main__':
    main()
