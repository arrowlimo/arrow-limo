#!/usr/bin/env python3
"""Continue review - analyze remaining created_from_banking receipts"""
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

password = os.getenv('LOCAL_DB_PASSWORD') or os.getenv('DB_PASSWORD') or os.getenv('POSTGRES_PASSWORD')

conn = psycopg2.connect(
    host='localhost',
    database=os.getenv('LOCAL_DB_NAME') or 'almsdata',
    user=os.getenv('LOCAL_DB_USER') or 'postgres',
    password=password
)

cur = conn.cursor()

print("=" * 120)
print("CONTINUING REVIEW: ANALYZING REMAINING RECEIPTS WITH BANKING LINKS")
print("=" * 120)

# Get total receipts now
cur.execute("SELECT COUNT(*) FROM receipts")
total_receipts = cur.fetchone()[0]

# Receipts with created_from_banking flag (non-zero)
cur.execute("""
    SELECT COUNT(*) 
    FROM receipts 
    WHERE created_from_banking = TRUE 
      AND gross_amount != 0
""")
created_from_banking_nonzero = cur.fetchone()[0]

# Receipts linked to banking with actual amounts
cur.execute("""
    SELECT COUNT(*) 
    FROM receipts 
    WHERE banking_transaction_id IS NOT NULL 
      AND gross_amount != 0
""")
linked_with_amount = cur.fetchone()[0]

# OLD import receipts (created_from_banking but no link)
cur.execute("""
    SELECT COUNT(*) 
    FROM receipts 
    WHERE created_from_banking = TRUE 
      AND banking_transaction_id IS NULL
""")
old_import_no_link = cur.fetchone()[0]

print(f"\n📊 CURRENT STATE:")
print(f"  Total receipts:                                    {total_receipts:>6,}")
print(f"  Created from banking (non-zero amounts):          {created_from_banking_nonzero:>6,}")
print(f"  Linked to banking (non-zero amounts):             {linked_with_amount:>6,}")
print(f"  Old import (created_from_banking, no link):       {old_import_no_link:>6,}")

# Analyze for potential duplicate patterns
print("\n" + "=" * 120)
print("ANALYZING FOR DUPLICATE PATTERNS")
print("=" * 120)

# Check for receipts where BOTH receipt and banking have the same amount
# This could indicate double-entry
cur.execute("""
    SELECT 
        r.receipt_id,
        r.receipt_date,
        r.vendor_name,
        r.gross_amount as receipt_amount,
        bt.transaction_date,
        bt.description,
        (bt.debit_amount - COALESCE(bt.credit_amount, 0)) as banking_amount,
        CASE 
            WHEN ABS(r.gross_amount - (bt.debit_amount - COALESCE(bt.credit_amount, 0))) < 0.01 
            THEN 'EXACT_MATCH'
            ELSE 'DIFFERENT'
        END as amount_match
    FROM receipts r
    JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
    WHERE r.gross_amount != 0
      AND r.created_from_banking = TRUE
      AND ABS(r.gross_amount - (bt.debit_amount - COALESCE(bt.credit_amount, 0))) < 0.01
    ORDER BY r.receipt_date
    LIMIT 50
""")

exact_matches = cur.fetchall()

print(f"\n🔍 EXACT AMOUNT MATCHES (Receipt amount = Banking amount):")
print(f"   Found {len(exact_matches)} exact matches in sample")

if exact_matches:
    print(f"\n   Sample (first 20):")
    for row in exact_matches[:20]:
        receipt_id, r_date, vendor, r_amt, bt_date, bt_desc, bt_amt, match = row
        print(f"\n   Receipt #{receipt_id} | {r_date} | ${r_amt:>10.2f} | {vendor[:40]}")
        print(f"     → Banking: {bt_date} | ${bt_amt:>10.2f} | {bt_desc[:60]}")

# Count total exact matches
cur.execute("""
    SELECT COUNT(*)
    FROM receipts r
    JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
    WHERE r.gross_amount != 0
      AND r.created_from_banking = TRUE
      AND ABS(r.gross_amount - (bt.debit_amount - COALESCE(bt.credit_amount, 0))) < 0.01
""")
total_exact_matches = cur.fetchone()[0]

print(f"\n   TOTAL exact amount matches: {total_exact_matches:,} receipts")
print(f"   These are likely legitimate - receipt properly linked to banking transaction")

# Check for receipts where amounts DON'T match
cur.execute("""
    SELECT COUNT(*)
    FROM receipts r
    JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
    WHERE r.gross_amount != 0
      AND r.created_from_banking = TRUE
      AND ABS(r.gross_amount - (bt.debit_amount - COALESCE(bt.credit_amount, 0))) >= 0.01
""")
mismatched_amounts = cur.fetchone()[0]

print(f"\n⚠️  AMOUNT MISMATCHES (Receipt ≠ Banking):")
print(f"   Found {mismatched_amounts:,} receipts where amounts don't match")

if mismatched_amounts > 0:
    cur.execute("""
        SELECT 
            r.receipt_id,
            r.receipt_date,
            r.vendor_name,
            r.gross_amount as receipt_amount,
            bt.description,
            (bt.debit_amount - COALESCE(bt.credit_amount, 0)) as banking_amount,
            ABS(r.gross_amount - (bt.debit_amount - COALESCE(bt.credit_amount, 0))) as difference
        FROM receipts r
        JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
        WHERE r.gross_amount != 0
          AND r.created_from_banking = TRUE
          AND ABS(r.gross_amount - (bt.debit_amount - COALESCE(bt.credit_amount, 0))) >= 0.01
        ORDER BY ABS(r.gross_amount - (bt.debit_amount - COALESCE(bt.credit_amount, 0))) DESC
        LIMIT 20
    """)
    
    print(f"\n   Top 20 largest mismatches:")
    for row in cur.fetchall():
        receipt_id, r_date, vendor, r_amt, bt_desc, bt_amt, diff = row
        print(f"   Receipt #{receipt_id} | {r_date} | Receipt: ${r_amt:>10.2f} | Banking: ${bt_amt:>10.2f} | Diff: ${diff:>10.2f}")
        print(f"     → {vendor[:50]} vs {bt_desc[:50]}")

# Analyze old imports with no banking link
print("\n" + "=" * 120)
print("OLD IMPORT RECEIPTS (created_from_banking=TRUE but no banking_transaction_id)")
print("=" * 120)

cur.execute("""
    SELECT 
        COUNT(*),
        MIN(receipt_date) as earliest,
        MAX(receipt_date) as latest,
        SUM(gross_amount) as total_amount
    FROM receipts
    WHERE created_from_banking = TRUE 
      AND banking_transaction_id IS NULL
""")

row = cur.fetchone()
count, earliest, latest, total_amt = row

print(f"\n   Total old import receipts: {count:,}")
print(f"   Date range: {earliest} to {latest}")
print(f"   Total amount: ${total_amt:,.2f}")

# Sample old imports
cur.execute("""
    SELECT 
        receipt_id,
        receipt_date,
        vendor_name,
        gross_amount,
        category,
        description
    FROM receipts
    WHERE created_from_banking = TRUE 
      AND banking_transaction_id IS NULL
    ORDER BY receipt_date
    LIMIT 30
""")

print(f"\n   Sample old imports (first 30):")
for row in cur.fetchall():
    receipt_id, r_date, vendor, amount, category, desc = row
    amount_str = f"${amount:>10.2f}" if amount is not None else "      NULL"
    vendor_str = (vendor or 'NULL')[:40]
    print(f"   #{receipt_id} | {r_date} | {amount_str} | {vendor_str}")

# Check if these old imports have matching banking transactions now
print(f"\n   Checking for potential banking matches...")
cur.execute("""
    SELECT COUNT(*)
    FROM receipts r
    WHERE r.created_from_banking = TRUE 
      AND r.banking_transaction_id IS NULL
      AND EXISTS (
          SELECT 1 
          FROM banking_transactions bt
          WHERE bt.transaction_date = r.receipt_date
            AND ABS((bt.debit_amount - COALESCE(bt.credit_amount, 0)) - r.gross_amount) < 0.01
      )
""")
potential_matches = cur.fetchone()[0]

print(f"   Old imports with potential banking matches: {potential_matches:,}")

# Summary and recommendations
print("\n" + "=" * 120)
print("RECOMMENDATIONS")
print("=" * 120)
print()
print(f"1. ✅ EXACT MATCHES ({total_exact_matches:,} receipts):")
print(f"   - Receipt amount matches banking transaction amount")
print(f"   - These are properly linked and legitimate")
print(f"   - No action needed - keep as is")
print()
print(f"2. ⚠️  AMOUNT MISMATCHES ({mismatched_amounts:,} receipts):")
print(f"   - Receipt amount ≠ Banking transaction amount")
print(f"   - May indicate data quality issues or partial payments")
print(f"   - Recommend manual review of top mismatches")
print()
print(f"3. 📋 OLD IMPORTS ({old_import_no_link:,} receipts):")
print(f"   - Created from banking but no longer linked")
print(f"   - {potential_matches:,} may have banking matches available")
print(f"   - Consider re-linking or archiving as legacy data")
print()

conn.close()

print("=" * 120)
print("Review complete - see recommendations above")
print("=" * 120)
