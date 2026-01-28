#!/usr/bin/env python3
"""Mark NSF (Non-Sufficient Funds) receipts with appropriate flags."""

import psycopg2
import os

conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REMOVED***")
)
cur = conn.cursor()

print("=" * 100)
print("MARKING NSF RECEIPTS")
print("=" * 100)

# Find all NSF-related receipts from banking transactions
print("\n1. Finding NSF receipts via banking transaction descriptions...")
cur.execute("""
    SELECT r.receipt_id, r.vendor_name, r.gross_amount, r.description, 
           bt.description as banking_desc, bt.transaction_date
    FROM receipts r
    JOIN banking_transactions bt ON bt.receipt_id = r.receipt_id
    WHERE bt.description ILIKE '%NSF%' 
       OR bt.description ILIKE '%NON-SUFFICIENT%'
       OR bt.description ILIKE '%RETURNED%'
       OR bt.description ILIKE '%REVERSAL%'
    ORDER BY bt.transaction_date
""")
nsf_candidates = cur.fetchall()
print(f"   Found {len(nsf_candidates)} receipts linked to NSF banking transactions")

# Update receipts with NSF flag in description
updated_count = 0
for receipt_id, vendor, amount, current_desc, banking_desc, tx_date in nsf_candidates:
    # Check if already marked
    if current_desc and '[NSF]' in current_desc:
        continue
    
    # Add NSF flag to description
    if current_desc:
        new_desc = f"[NSF] {current_desc}"
    else:
        new_desc = f"[NSF] NSF return from banking: {banking_desc[:100]}"
    
    cur.execute("""
        UPDATE receipts
        SET description = %s
        WHERE receipt_id = %s
    """, (new_desc, receipt_id))
    updated_count += 1
    amt_str = f"${amount:,.2f}" if amount else "NULL"
    print(f"   ✓ Receipt {receipt_id}: {vendor[:40]:40} {amt_str:>12} | {tx_date}")

conn.commit()

print(f"\n✅ Updated {updated_count} receipts with [NSF] flag")

# Now mark Heffner receipts that are likely NSF pairs
print("\n2. Marking Heffner NSF pairs (same date + amount reversals)...")

# Find Heffner transactions that appear twice on same date with same amount
cur.execute("""
    WITH heffner_pairs AS (
        SELECT 
            r.receipt_date::date as rdate,
            r.gross_amount,
            array_agg(r.receipt_id ORDER BY r.receipt_id) as receipt_ids,
            COUNT(*) as cnt
        FROM receipts r
        WHERE r.vendor_name LIKE '%HEFFNER%'
        AND r.gross_amount IS NOT NULL
        GROUP BY r.receipt_date::date, r.gross_amount
        HAVING COUNT(*) = 2
    )
    SELECT hp.rdate, hp.gross_amount, hp.receipt_ids, hp.cnt
    FROM heffner_pairs hp
    ORDER BY hp.rdate
""")
heffner_pairs = cur.fetchall()
print(f"   Found {len(heffner_pairs)} Heffner date+amount pairs")

pair_updated = 0
for rdate, amount, receipt_ids, cnt in heffner_pairs:
    # Mark both as potential NSF pairs
    if receipt_ids:  # Check if list is not empty
        for rid in receipt_ids:
            cur.execute("""
                UPDATE receipts
                SET description = CASE 
                    WHEN description IS NULL OR description NOT LIKE '%NSF%' 
                    THEN COALESCE('[NSF PAIR] ' || description, '[NSF PAIR] Heffner payment/reversal pair')
                    ELSE description
                END
                WHERE receipt_id = %s
                AND (description IS NULL OR description NOT LIKE '%NSF%')
            """, (rid,))
            if cur.rowcount > 0:
                pair_updated += 1

conn.commit()
print(f"   ✅ Updated {pair_updated} Heffner NSF pair receipts")

# Summary
print("\n" + "=" * 100)
print("SUMMARY")
print("=" * 100)
cur.execute("""
    SELECT COUNT(*), SUM(gross_amount)
    FROM receipts
    WHERE description LIKE '%NSF%'
""")
nsf_total, nsf_amount = cur.fetchone()
print(f"Total receipts with NSF flag: {nsf_total:,}")
print(f"Total NSF amount: ${nsf_amount if nsf_amount else 0:,.2f}")

cur.execute("""
    SELECT COUNT(*), SUM(gross_amount)
    FROM receipts
    WHERE vendor_name LIKE '%HEFFNER%'
    AND description LIKE '%NSF%'
""")
heffner_nsf, heffner_nsf_amt = cur.fetchone()
print(f"Heffner NSF receipts: {heffner_nsf:,}")
print(f"Heffner NSF amount: ${heffner_nsf_amt if heffner_nsf_amt else 0:,.2f}")

cur.close()
conn.close()
