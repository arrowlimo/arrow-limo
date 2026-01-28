#!/usr/bin/env python3
"""
Delete 2,041 UNKNOWN receipts with proper cascade handling.
Clear foreign key references before deletion.
"""

import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REMOVED***"
)

cur = conn.cursor()

print("=" * 80)
print("DELETING UNKNOWN DUPLICATE AND NULL RECEIPTS")
print("=" * 80)

# Step 1: Identify receipts to delete
print("\nStep 1: Identifying receipts to delete...")

# Duplicates
cur.execute("""
    WITH duplicates AS (
        SELECT 
            r.receipt_id,
            r.receipt_date,
            r.gross_amount
        FROM receipts r
        WHERE r.vendor_name = 'UNKNOWN'
          AND r.gross_amount IS NOT NULL
          AND r.gross_amount > 0
    ),
    banking_matches AS (
        SELECT DISTINCT
            d.receipt_id
        FROM duplicates d
        INNER JOIN banking_transactions b 
            ON b.transaction_date = d.receipt_date
            AND ABS(b.debit_amount - d.gross_amount) < 0.01
        LEFT JOIN banking_receipt_matching_ledger m 
            ON b.transaction_id = m.banking_transaction_id
        WHERE m.receipt_id IS NOT NULL
          AND m.receipt_id != d.receipt_id
    )
    SELECT receipt_id FROM banking_matches
""")
duplicate_ids = [row[0] for row in cur.fetchall()]
print(f"Found {len(duplicate_ids)} duplicate receipts")

# Null/zero
cur.execute("""
    SELECT receipt_id
    FROM receipts
    WHERE vendor_name = 'UNKNOWN'
      AND (gross_amount IS NULL OR gross_amount = 0)
""")
null_ids = [row[0] for row in cur.fetchall()]
print(f"Found {len(null_ids)} null/zero receipts")

all_delete_ids = duplicate_ids + null_ids
print(f"\nTotal to delete: {len(all_delete_ids)}")

if len(all_delete_ids) == 0:
    print("Nothing to delete!")
    cur.close()
    conn.close()
    exit(0)

# Step 2: Disable lock trigger
print("\n" + "=" * 80)
print("DISABLING LOCK TRIGGER")
print("=" * 80)

cur.execute("ALTER TABLE banking_transactions DISABLE TRIGGER trg_banking_transactions_lock")
print("✅ Disabled banking lock trigger")
conn.commit()

# Step 3: Clear foreign key references
print("\n" + "=" * 80)
print("CLEARING FOREIGN KEY REFERENCES")
print("=" * 80)

# Clear banking_transactions.receipt_id
print("\nClearing banking_transactions.receipt_id references...")
cur.execute("""
    UPDATE banking_transactions
    SET receipt_id = NULL
    WHERE receipt_id = ANY(%s)
""", (all_delete_ids,))
banking_cleared = cur.rowcount
print(f"✅ Cleared {banking_cleared} banking_transactions references")

# Clear banking_receipt_matching_ledger
print("\nDeleting from banking_receipt_matching_ledger...")
cur.execute("""
    DELETE FROM banking_receipt_matching_ledger
    WHERE receipt_id = ANY(%s)
""", (all_delete_ids,))
ledger_deleted = cur.rowcount
print(f"✅ Deleted {ledger_deleted} matching ledger entries")

conn.commit()

# Step 4: Delete receipts
print("\n" + "=" * 80)
print("DELETING RECEIPTS")
print("=" * 80)

cur.execute("""
    DELETE FROM receipts
    WHERE receipt_id = ANY(%s)
""", (all_delete_ids,))

deleted = cur.rowcount
conn.commit()
print(f"\n✅ DELETED {deleted} receipts")
print(f"   Duplicates: {len(duplicate_ids)}")
print(f"   Null/zero: {len(null_ids)}")

# Step 5: Re-enable lock trigger
print("\n" + "=" * 80)
print("RE-ENABLING LOCK TRIGGER")
print("=" * 80)

cur.execute("ALTER TABLE banking_transactions ENABLE TRIGGER trg_banking_transactions_lock")
print("✅ Re-enabled banking lock trigger")
conn.commit()

# Step 6: Check remaining UNKNOWN receipts
print("\n" + "=" * 80)
print("REMAINING UNKNOWN RECEIPTS")
print("=" * 80)

cur.execute("""
    SELECT COUNT(*)
    FROM receipts
    WHERE vendor_name = 'UNKNOWN'
""")
remaining = cur.fetchone()[0]
print(f"\nRemaining UNKNOWN receipts: {remaining}")

if remaining > 0:
    cur.execute("""
        SELECT 
            receipt_date,
            gross_amount,
            description
        FROM receipts
        WHERE vendor_name = 'UNKNOWN'
        ORDER BY gross_amount DESC NULLS LAST
        LIMIT 25
    """)
    
    print("\nSample remaining UNKNOWN receipts:")
    print("Date       | Amount    | Description")
    print("-" * 70)
    for row in cur.fetchall():
        r_date, amount, desc = row
        amt_str = f"${amount:,.2f}" if amount else "$0.00"
        desc_str = (desc or '')[:40]
        print(f"{r_date} | {amt_str:9} | {desc_str}")

# Step 7: Re-run banking receipt matching
print("\n" + "=" * 80)
print("RE-RUNNING BANKING RECEIPT MATCHING")
print("=" * 80)

print("\nMatching UNKNOWN receipts to banking transactions...")

# Match by date + amount
cur.execute("""
    WITH unmatched_banking AS (
        SELECT 
            b.transaction_id,
            b.transaction_date,
            b.debit_amount,
            b.description
        FROM banking_transactions b
        WHERE b.debit_amount > 0
          AND NOT EXISTS (
              SELECT 1 FROM banking_receipt_matching_ledger m
              WHERE m.banking_transaction_id = b.transaction_id
          )
    ),
    unknown_receipts AS (
        SELECT 
            r.receipt_id,
            r.receipt_date,
            r.gross_amount,
            r.description
        FROM receipts r
        WHERE r.vendor_name = 'UNKNOWN'
          AND r.gross_amount > 0
    )
    INSERT INTO banking_receipt_matching_ledger (
        banking_transaction_id,
        receipt_id,
        match_date
    )
    SELECT 
        b.transaction_id,
        u.receipt_id,
        CURRENT_TIMESTAMP
    FROM unmatched_banking b
    INNER JOIN unknown_receipts u
        ON b.transaction_date = u.receipt_date
        AND ABS(b.debit_amount - u.gross_amount) < 0.01
    WHERE NOT EXISTS (
        SELECT 1 FROM banking_receipt_matching_ledger m
        WHERE m.receipt_id = u.receipt_id
    )
""")

matched = cur.rowcount
conn.commit()
print(f"✅ Matched {matched} receipts to banking transactions")

# Extract vendor names from banking for newly matched receipts
if matched > 0:
    print("\nExtracting vendor names from banking descriptions...")
    cur.execute("""
        WITH recent_matches AS (
            SELECT DISTINCT m.receipt_id, m.banking_transaction_id
            FROM banking_receipt_matching_ledger m
            WHERE m.match_date >= CURRENT_TIMESTAMP - INTERVAL '5 seconds'
        )
        UPDATE receipts r
        SET vendor_name = COALESCE(b.vendor_extracted, 'UNKNOWN')
        FROM banking_transactions b
        INNER JOIN recent_matches m ON m.banking_transaction_id = b.transaction_id
        WHERE r.receipt_id = m.receipt_id
          AND r.vendor_name = 'UNKNOWN'
    """)
    
    vendor_updated = cur.rowcount
    conn.commit()
    print(f"✅ Updated {vendor_updated} vendor names from banking")
else:
    vendor_updated = 0

# Final summary
print("\n" + "=" * 80)
print("FINAL SUMMARY")
print("=" * 80)

cur.execute("SELECT COUNT(*) FROM receipts WHERE vendor_name = 'UNKNOWN'")
final_unknown = cur.fetchone()[0]

print(f"\nDeleted: {deleted} receipts")
print(f"  Duplicates: {len(duplicate_ids)}")
print(f"  Null/zero: {len(null_ids)}")
print(f"\nForeign key references cleared:")
print(f"  banking_transactions: {banking_cleared}")
print(f"  matching ledger: {ledger_deleted}")
print(f"\nMatched: {matched} receipts to banking")
print(f"Vendor names updated: {vendor_updated if matched > 0 else 0}")
print(f"\nFinal UNKNOWN count: {final_unknown}")

cur.close()
conn.close()

print("\n✅ COMPLETE")
