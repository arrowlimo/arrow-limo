#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Check if Scotia receipts are incorrectly linked to CIBC banking transactions.
Also check CIBC transaction coverage for receipts.
"""

import psycopg2

def get_db_connection():
    """Get PostgreSQL connection."""
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )

def check_account_linkage():
    """Check receipt-banking account linkage."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 70)
    print("SCOTIA vs CIBC BANKING RECEIPT LINKAGE CHECK")
    print("=" * 70)
    
    # Count Scotia receipts
    cur.execute("""
        SELECT COUNT(*) 
        FROM receipts 
        WHERE created_from_banking = TRUE 
        AND mapped_bank_account_id = 2
    """)
    scotia_receipts = cur.fetchone()[0]
    print(f"\nScotia receipts (mapped_bank_account_id=2): {scotia_receipts:,}")
    
    # Count CIBC transactions
    cur.execute("""
        SELECT COUNT(*) 
        FROM banking_transactions 
        WHERE account_number = '0228362'
    """)
    cibc_txns = cur.fetchone()[0]
    print(f"CIBC transactions (account 0228362): {cibc_txns:,}")
    
    # Count Scotia transactions
    cur.execute("""
        SELECT COUNT(*) 
        FROM banking_transactions 
        WHERE account_number = '903990106011'
    """)
    scotia_txns = cur.fetchone()[0]
    print(f"Scotia transactions (account 903990106011): {scotia_txns:,}")
    
    # Check for mislinked Scotia receipts → CIBC banking
    cur.execute("""
        SELECT COUNT(*)
        FROM receipts r
        JOIN banking_receipt_matching_ledger bm ON r.receipt_id = bm.receipt_id
        JOIN banking_transactions bt ON bm.banking_transaction_id = bt.transaction_id
        WHERE r.created_from_banking = TRUE 
        AND r.mapped_bank_account_id = 2
        AND bt.account_number = '0228362'
    """)
    wrong_account_links = cur.fetchone()[0]
    print(f"\n❌ Scotia receipts WRONGLY linked to CIBC banking: {wrong_account_links:,}")
    
    # Check correct Scotia receipts → Scotia banking
    cur.execute("""
        SELECT COUNT(*)
        FROM receipts r
        JOIN banking_receipt_matching_ledger bm ON r.receipt_id = bm.receipt_id
        JOIN banking_transactions bt ON bm.banking_transaction_id = bt.transaction_id
        WHERE r.created_from_banking = TRUE 
        AND r.mapped_bank_account_id = 2
        AND bt.account_number = '903990106011'
    """)
    correct_links = cur.fetchone()[0]
    print(f"✅ Scotia receipts correctly linked to Scotia banking: {correct_links:,}")
    
    # Check CIBC banking coverage
    print("\n" + "=" * 70)
    print("CIBC BANKING RECEIPT COVERAGE")
    print("=" * 70)
    
    cur.execute("""
        SELECT COUNT(DISTINCT bm.banking_transaction_id)
        FROM banking_receipt_matching_ledger bm
        JOIN banking_transactions bt ON bm.banking_transaction_id = bt.transaction_id
        WHERE bt.account_number = '0228362'
    """)
    cibc_with_receipts = cur.fetchone()[0]
    print(f"\nCIBC transactions WITH receipts: {cibc_with_receipts:,}")
    
    cur.execute("""
        SELECT COUNT(*)
        FROM banking_transactions
        WHERE account_number = '0228362'
        AND debit_amount > 0
        AND transaction_id NOT IN (
            SELECT banking_transaction_id 
            FROM banking_receipt_matching_ledger
        )
    """)
    cibc_debits_no_receipts = cur.fetchone()[0]
    print(f"CIBC debits WITHOUT receipts: {cibc_debits_no_receipts:,}")
    
    # Sum of CIBC debits without receipts
    cur.execute("""
        SELECT SUM(debit_amount)
        FROM banking_transactions
        WHERE account_number = '0228362'
        AND debit_amount > 0
        AND transaction_id NOT IN (
            SELECT banking_transaction_id 
            FROM banking_receipt_matching_ledger
        )
    """)
    cibc_unmatched_amount = cur.fetchone()[0] or 0
    print(f"CIBC unmatched debit amount: ${cibc_unmatched_amount:,.2f}")
    
    # Check if CIBC receipts were created with wrong account flag
    cur.execute("""
        SELECT COUNT(*)
        FROM receipts
        WHERE created_from_banking = TRUE
        AND mapped_bank_account_id = 1
    """)
    cibc_flagged_receipts = cur.fetchone()[0]
    print(f"\nReceipts flagged as CIBC (mapped_bank_account_id=1): {cibc_flagged_receipts:,}")
    
    # Sample CIBC transactions without receipts
    print("\n" + "=" * 70)
    print("SAMPLE CIBC DEBITS WITHOUT RECEIPTS (first 10)")
    print("=" * 70)
    cur.execute("""
        SELECT 
            transaction_date,
            description,
            debit_amount
        FROM banking_transactions
        WHERE account_number = '0228362'
        AND debit_amount > 0
        AND transaction_id NOT IN (
            SELECT banking_transaction_id 
            FROM banking_receipt_matching_ledger
        )
        ORDER BY transaction_date DESC
        LIMIT 10
    """)
    print("\n{:<12s} {:<45s} {:>12s}".format("Date", "Description", "Amount"))
    print("-" * 70)
    for row in cur.fetchall():
        print(f"{row[0]} {row[1][:45]:45s} ${row[2]:>10,.2f}")
    
    conn.close()
    
    print("\n" + "=" * 70)
    print("RECOMMENDATION:")
    print("=" * 70)
    if cibc_debits_no_receipts > 0:
        print(f"\nRun auto_create_receipts_from_all_banking.py for CIBC account:")
        print(f"  python scripts/auto_create_receipts_from_all_banking.py --account 0228362 --write")
        print(f"\nThis will create {cibc_debits_no_receipts:,} receipts for ${cibc_unmatched_amount:,.2f}")
    else:
        print("\nAll CIBC debits already have receipts! ✅")

if __name__ == '__main__':
    check_account_linkage()
