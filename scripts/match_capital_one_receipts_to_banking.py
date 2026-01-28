#!/usr/bin/env python
"""
Match Capital One credit card PAYMENT receipts to banking transactions.
Only payments TO the credit card appear in banking - not the individual purchases.
"""

import psycopg2
import os
from datetime import timedelta

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def find_capital_one_payments(cur):
    """Find Capital One payment receipts (payments TO the card)"""
    cur.execute("""
        SELECT receipt_id, receipt_date, vendor_name, gross_amount, description
        FROM receipts
        WHERE vendor_name LIKE '%Capital One%Payment%'
        ORDER BY receipt_date
    """)
    return cur.fetchall()

def find_banking_transactions(cur):
    """Find banking transactions that might be Capital One payments"""
    # Look for patterns like "MCC PAYMENT", "CAPITAL ONE", "AMEX", etc.
    cur.execute("""
        SELECT transaction_id, transaction_date, description, debit_amount, credit_amount
        FROM banking_transactions
        WHERE (
            description ILIKE '%capital one%'
            OR description ILIKE '%mcc payment%'
            OR description ILIKE '%amex%'
        )
        AND transaction_date >= '2012-01-01'
        AND transaction_date <= '2013-12-31'
        ORDER BY transaction_date
    """)
    return cur.fetchall()

def match_receipts_to_banking(receipt_payments, banking_txns):
    """
    Match receipt payments to banking transactions.
    Criteria: Same date (±2 days) and same amount
    """
    matches = []
    unmatched_receipts = []
    unmatched_banking = list(banking_txns)
    
    for receipt in receipt_payments:
        receipt_id, receipt_date, vendor, amount, desc = receipt
        
        # Look for matching banking transaction
        found_match = False
        for i, bank_txn in enumerate(unmatched_banking):
            bank_id, bank_date, bank_desc, debit, credit = bank_txn
            
            # Banking amount (payment is debit - money out)
            bank_amount = debit if debit else 0
            
            # Date within ±2 days
            date_diff = abs((receipt_date - bank_date).days)
            
            # Amount matches
            amount_match = abs(float(amount) - float(bank_amount)) < 0.01
            
            if date_diff <= 2 and amount_match:
                matches.append({
                    'receipt_id': receipt_id,
                    'receipt_date': receipt_date,
                    'receipt_amount': amount,
                    'banking_id': bank_id,
                    'banking_date': bank_date,
                    'banking_desc': bank_desc,
                    'banking_amount': bank_amount,
                    'date_diff': date_diff
                })
                unmatched_banking.pop(i)
                found_match = True
                break
        
        if not found_match:
            unmatched_receipts.append(receipt)
    
    return matches, unmatched_receipts, unmatched_banking

def create_receipt_banking_links(matches, cur, conn, dry_run=True):
    """
    Link receipts to banking transactions.
    Uses banking_receipt_matching_ledger table.
    """
    created = 0
    
    for match in matches:
        # Check if link already exists
        cur.execute("""
            SELECT id FROM banking_receipt_matching_ledger
            WHERE receipt_id = %s AND banking_transaction_id = %s
        """, (match['receipt_id'], match['banking_id']))
        
        if cur.fetchone():
            continue  # Already linked
        
        if not dry_run:
            cur.execute("""
                INSERT INTO banking_receipt_matching_ledger (
                    receipt_id, banking_transaction_id
                )
                VALUES (%s, %s)
            """, (
                match['receipt_id'], 
                match['banking_id']
            ))
            created += 1
    
    if not dry_run:
        conn.commit()
    
    return created

def main():
    import sys
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    dry_run = '--write' not in sys.argv
    
    print("=" * 80)
    print("CAPITAL ONE PAYMENT RECEIPT → BANKING TRANSACTION MATCHING")
    print("=" * 80)
    
    # Find Capital One payment receipts
    print("\n=== STEP 1: FINDING CAPITAL ONE PAYMENT RECEIPTS ===")
    receipt_payments = find_capital_one_payments(cur)
    print(f"Found {len(receipt_payments)} Capital One payment receipts")
    
    if receipt_payments:
        print("\nPayment receipts:")
        for receipt in receipt_payments:
            receipt_id, date, vendor, amount, desc = receipt
            print(f"  Receipt {receipt_id} | {date} | ${amount:,.2f} | {vendor}")
    
    # Find banking transactions
    print("\n=== STEP 2: FINDING BANKING TRANSACTIONS ===")
    banking_txns = find_banking_transactions(cur)
    print(f"Found {len(banking_txns)} potential banking transactions")
    
    if banking_txns:
        print("\nBanking transactions:")
        for txn in banking_txns[:10]:
            bank_id, date, desc, debit, credit = txn
            amount = debit if debit else credit
            print(f"  Bank {bank_id} | {date} | ${amount:,.2f} | {desc[:60]}")
    
    # Match
    print("\n=== STEP 3: MATCHING RECEIPTS TO BANKING ===")
    matches, unmatched_receipts, unmatched_banking = match_receipts_to_banking(
        receipt_payments, banking_txns
    )
    
    print(f"Matched: {len(matches)}")
    print(f"Unmatched receipts: {len(unmatched_receipts)}")
    print(f"Unmatched banking: {len(unmatched_banking)}")
    
    if matches:
        print("\n=== MATCHES FOUND ===")
        for match in matches:
            print(f"\n  Receipt {match['receipt_id']} → Bank {match['banking_id']}")
            print(f"    Receipt: {match['receipt_date']} | ${match['receipt_amount']:,.2f}")
            print(f"    Banking: {match['banking_date']} | ${match['banking_amount']:,.2f} | {match['banking_desc'][:60]}")
            print(f"    Date diff: {match['date_diff']} days")
    
    # Create links
    print("\n=== STEP 4: CREATING LINKS ===")
    created = create_receipt_banking_links(matches, cur, conn, dry_run=dry_run)
    
    if dry_run:
        print(f"Would create {len(matches)} receipt-banking links")
        print("\n[WARN] DRY RUN - No changes made")
        print("Run with --write to apply changes")
    else:
        print(f"[OK] Created {created} new receipt-banking links")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
