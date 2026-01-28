#!/usr/bin/env python3
"""
STEP 3: Link CIBC->Scotia split deposits with parent/child relationships.
4 known split deposits match CIBC withdrawals to Scotia deposits.
"""

import os
import psycopg2

DB_SETTINGS = {
    "host": os.getenv("DB_HOST", "localhost"),
    "database": os.getenv("DB_NAME", "almsdata"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "***REMOVED***"),
}

# 4 known CIBC->Scotia split deposits
SPLITS = [
    {'date': '2012-07-16', 'scotia_amount': 400.00, 'cibc_amount': 400.00, 'notes': 'CIBC->Scotia'},
    {'date': '2012-10-24', 'scotia_amount': 1700.00, 'cibc_amount': 1000.00, 'notes': 'CIBC->Scotia split'},
    {'date': '2012-10-26', 'scotia_amount': 1500.00, 'cibc_amount': 600.00, 'notes': 'CIBC->Scotia split'},
    {'date': '2012-11-19', 'scotia_amount': 2000.00, 'cibc_amount': 1300.00, 'notes': 'CIBC->Scotia split'},
]

def link_split_deposits(dry_run=False):
    """Link CIBC debits to Scotia deposits as inter-account transfers."""
    print("\n" + "="*80)
    print("STEP 3: LINK CIBC->SCOTIA SPLIT DEPOSITS")
    print("="*80)
    print(f"Mode: {'DRY-RUN' if dry_run else 'WRITE'}\n")
    
    conn = psycopg2.connect(**DB_SETTINGS)
    cur = conn.cursor()
    
    try:
        linked_count = 0
        
        for split in SPLITS:
            date = split['date']
            scotia_amt = split['scotia_amount']
            cibc_amt = split['cibc_amount']
            
            print(f"\n{date}: Scotia ${scotia_amt:,.2f} <-> CIBC ${cibc_amt:,.2f}")
            
            # Find Scotia deposit (credit)
            cur.execute("""
                SELECT transaction_id FROM banking_transactions
                WHERE account_number = '903990106011'
                  AND transaction_date = %s::date
                  AND credit_amount = %s
                LIMIT 1
            """, (date, scotia_amt))
            
            scotia_tx = cur.fetchone()
            if not scotia_tx:
                print(f"  [SKIP] Scotia deposit not found")
                continue
            
            scotia_tx_id = scotia_tx[0]
            
            # Find CIBC debit
            cur.execute("""
                SELECT transaction_id FROM banking_transactions
                WHERE account_number = '0228362'
                  AND transaction_date = %s::date
                  AND debit_amount = %s
                LIMIT 1
            """, (date, cibc_amt))
            
            cibc_tx = cur.fetchone()
            if not cibc_tx:
                print(f"  [SKIP] CIBC debit not found")
                continue
            
            cibc_tx_id = cibc_tx[0]
            
            print(f"  [FOUND] Scotia TX {scotia_tx_id}, CIBC TX {cibc_tx_id}")
            
            if not dry_run:
                # Create inter-account transfer receipts if not already present
                # Check if receipt already exists for Scotia TX
                cur.execute("""
                    SELECT receipt_id FROM banking_receipt_matching_ledger
                    WHERE banking_transaction_id = %s
                    LIMIT 1
                """, (scotia_tx_id,))
                
                if not cur.fetchone():
                    # Create receipt for Scotia side
                    cur.execute("""
                        INSERT INTO receipts
                        (receipt_date, vendor_name, description, gross_amount, gst_amount, net_amount,
                         category, mapped_bank_account_id, source_hash, created_from_banking)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, true)
                        RETURNING receipt_id
                    """, (
                        date,
                        'Inter-Account Transfer (CIBC->Scotia)',
                        f'Inter-account transfer from CIBC to Scotia. {split["notes"]}',
                        scotia_amt,
                        0.0,
                        scotia_amt,
                        'inter_account_transfer',
                        2,  # Scotia account ID
                        f"{date}|Inter-account CIBC->Scotia|{scotia_amt}",
                    ))
                    
                    receipt_id = cur.fetchone()[0]
                    
                    # Link both transactions to same receipt (parent/child)
                    cur.execute("""
                        INSERT INTO banking_receipt_matching_ledger
                        (banking_transaction_id, receipt_id, match_type)
                        VALUES (%s, %s, %s), (%s, %s, %s)
                        ON CONFLICT DO NOTHING
                    """, (
                        scotia_tx_id, receipt_id, 'inter_account_scotia_side',
                        cibc_tx_id, receipt_id, 'inter_account_cibc_side'
                    ))
                    
                    print(f"  [CREATED] Receipt {receipt_id}, linked both sides")
                    linked_count += 1
        
        if not dry_run:
            conn.commit()
            print(f"\n[OK] Linked {linked_count} split deposit pairs")
        else:
            print(f"\n[DRY-RUN] Would link {linked_count} split deposit pairs")
        
        return linked_count
    
    except Exception as e:
        if not dry_run:
            conn.rollback()
        print(f"[ERROR] {e}")
        raise
    finally:
        cur.close()
        conn.close()

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Link CIBC->Scotia split deposits')
    parser.add_argument('--dry-run', action='store_true', help='Preview without writing')
    parser.add_argument('--write', action='store_true', help='Write to database')
    args = parser.parse_args()
    
    if not args.write:
        args.dry_run = True
    
    count = link_split_deposits(dry_run=args.dry_run)
    
    print("\n" + "="*80)
    print("NEXT: Dedup receipts (remove QuickBooks 'Cheque #dd X' artifacts)")
    print("="*80)

if __name__ == '__main__':
    main()
