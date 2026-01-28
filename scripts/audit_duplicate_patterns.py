#!/usr/bin/env python3
"""Audit potential duplicate receipts to find patterns and determine source."""

import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REMOVED***"
)

cur = conn.cursor()

print("=" * 120)
print("DUPLICATE RECEIPTS - DETAILED AUDIT")
print("=" * 120)

# Get a sample of duplicate groups with full details
cur.execute("""
    WITH grouped AS (
        SELECT 
            receipt_date,
            gross_amount,
            COALESCE(canonical_vendor, vendor_name) as vendor,
            ARRAY_AGG(receipt_id ORDER BY receipt_id) as receipt_ids
        FROM receipts
        WHERE exclude_from_reports = false OR exclude_from_reports IS NULL
        GROUP BY receipt_date, gross_amount, vendor
        HAVING COUNT(*) > 1
          AND (COUNT(DISTINCT banking_transaction_id) FILTER (WHERE banking_transaction_id IS NOT NULL) <= 1)
    )
    SELECT 
        receipt_date,
        gross_amount,
        vendor,
        receipt_ids[1] as receipt_id_1,
        receipt_ids[2] as receipt_id_2
    FROM grouped
    ORDER BY receipt_date
    LIMIT 10
""")

duplicate_pairs = cur.fetchall()

print(f"\nAnalyzing {len(duplicate_pairs)} sample duplicate pairs...\n")

for i, (date, amount, vendor, id1, id2) in enumerate(duplicate_pairs, 1):
    print("=" * 120)
    print(f"DUPLICATE PAIR #{i}: {vendor} | {date} | ${amount}")
    print("=" * 120)
    
    # Get full details for both receipts
    cur.execute("""
        SELECT 
            receipt_id,
            receipt_date,
            vendor_name,
            description,
            gross_amount,
            source_system,
            source_reference,
            banking_transaction_id,
            created_from_banking,
            created_at,
            source_file,
            event_batch_id
        FROM receipts
        WHERE receipt_id IN (%s, %s)
        ORDER BY receipt_id
    """, (id1, id2))
    
    receipts = cur.fetchall()
    
    for j, (rid, rdate, vname, desc, amt, src_sys, src_ref, bank_id, from_banking, created, src_file, batch_id) in enumerate(receipts, 1):
        print(f"\nReceipt #{j} (ID: {rid}):")
        print(f"  Date: {rdate}")
        print(f"  Vendor: {vname}")
        print(f"  Description: {desc[:80] if desc else 'None'}")
        print(f"  Amount: ${amt}")
        print(f"  Source System: {src_sys or 'None'}")
        print(f"  Source Reference: {src_ref or 'None'}")
        print(f"  Banking Transaction ID: {bank_id or 'None'}")
        print(f"  Created from Banking: {from_banking}")
        print(f"  Created At: {created}")
        print(f"  Source File: {src_file or 'None'}")
        print(f"  Event Batch ID: {batch_id or 'None'}")
    
    # Determine pattern
    r1_system = receipts[0][5]
    r2_system = receipts[1][5]
    r1_banking = receipts[0][8]
    r2_banking = receipts[1][8]
    
    print(f"\n>>> PATTERN ANALYSIS:")
    if r1_system and r2_system and r1_system == r2_system:
        print(f"    Both from same source system: {r1_system}")
        if 'quickbooks' in str(r1_system).lower():
            print(f"    ⚠️  LIKELY QUICKBOOKS DUPLICATE")
    else:
        print(f"    Different sources: {r1_system or 'Unknown'} vs {r2_system or 'Unknown'}")
    
    if r1_banking == r2_banking and r1_banking == True:
        print(f"    Both auto-created from banking")
        print(f"    ⚠️  POSSIBLE BANKING IMPORT DUPLICATE")
    elif r1_banking == False and r2_banking == False:
        print(f"    Both manual entries (not from banking)")
        print(f"    ⚠️  LIKELY MANUAL/QUICKBOOKS DUPLICATE")
    else:
        print(f"    Mixed: One banking, one manual")
        print(f"    ⚠️  POSSIBLE DOUBLE ENTRY (banking + manual)")
    
    print()

# Summary by source system
print("\n" + "=" * 120)
print("DUPLICATE PATTERN SUMMARY")
print("=" * 120)

cur.execute("""
    WITH duplicate_receipts AS (
        SELECT r.receipt_id, r.source_system, r.created_from_banking
        FROM receipts r
        WHERE EXISTS (
            SELECT 1
            FROM receipts r2
            WHERE r2.receipt_date = r.receipt_date
              AND r2.gross_amount = r.gross_amount
              AND COALESCE(r2.canonical_vendor, r2.vendor_name) = COALESCE(r.canonical_vendor, r.vendor_name)
              AND r2.receipt_id != r.receipt_id
              AND (r2.exclude_from_reports = false OR r2.exclude_from_reports IS NULL)
        )
        AND (r.exclude_from_reports = false OR r.exclude_from_reports IS NULL)
    )
    SELECT 
        source_system,
        created_from_banking,
        COUNT(*) as count
    FROM duplicate_receipts
    GROUP BY source_system, created_from_banking
    ORDER BY count DESC
""")

print("\nSource System          | From Banking | Count")
print("-" * 60)
for src_sys, from_banking, count in cur.fetchall():
    src_display = (src_sys[:20] if src_sys else "None/Unknown")
    banking_str = "Yes" if from_banking else "No"
    print(f"{src_display:20s} | {banking_str:12s} | {count:>5,d}")

print("\n" + "=" * 120)

cur.close()
conn.close()
