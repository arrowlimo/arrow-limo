#!/usr/bin/env python3
"""
NSF Transaction Reconciliation and Verification Handler

This script:
1. Identifies NSF transaction patterns (original, return, fee, retry)
2. Updates descriptions to clearly mark NSF RETURN and NSF FEE
3. Sets is_nsf_charge flag
4. Links related transactions together
5. Updates receipts to match
6. Sets reconciliation_status appropriately
7. Provides verification workflow for CRA compliance

Usage:
  python scripts/nsf_reconciliation_handler.py          # Dry run
  python scripts/nsf_reconciliation_handler.py --write  # Apply changes
"""

import psycopg2
import os
from datetime import datetime, timedelta

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")


def find_nsf_patterns(cur):
    """
    Find NSF patterns by looking for:
    1. Credit transactions (NSF returns) that reverse debits
    2. Small debits with negative amounts in description (NSF fees)
    3. Retry payments (new debits after NSF)
    """
    
    # Find potential NSF returns (credits with negative amount in description)
    cur.execute("""
        SELECT 
            transaction_id,
            transaction_date,
            description,
            credit_amount,
            is_nsf_charge,
            reconciliation_status
        FROM banking_transactions
        WHERE credit_amount > 0
          AND (
              description ~ '-[0-9]+\\.[0-9]{2}'  -- Has negative amount like "-150.00"
              OR description ILIKE '%nsf%'
              OR description ILIKE '%returned%'
              OR description ILIKE '%insufficient%'
          )
        ORDER BY transaction_date, transaction_id
    """)
    
    nsf_returns = cur.fetchall()
    
    # Find potential NSF fees (small debits with negative amount in description)
    cur.execute("""
        SELECT 
            transaction_id,
            transaction_date,
            description,
            debit_amount,
            is_nsf_charge,
            reconciliation_status
        FROM banking_transactions
        WHERE debit_amount > 0
          AND debit_amount < 50  -- NSF fees typically $10-$45
          AND description ~ '-[0-9]+\\.[0-9]{2}'  -- Has negative amount in description
        ORDER BY transaction_date, transaction_id
    """)
    
    nsf_fees = cur.fetchall()
    
    return nsf_returns, nsf_fees


def process_nsf_pattern(cur, conn, dry_run=True):
    """
    Process NSF patterns:
    1. Update banking transaction descriptions
    2. Set is_nsf_charge flag
    3. Update reconciliation_status
    4. Update linked receipts
    5. Create audit trail
    """
    
    nsf_returns, nsf_fees = find_nsf_patterns(cur)
    
    print(f"\n{'=' * 100}")
    print(f"NSF TRANSACTION RECONCILIATION HANDLER")
    print(f"{'=' * 100}\n")
    
    if dry_run:
        print("🔍 DRY RUN MODE - No changes will be made\n")
    else:
        print("✍️  WRITE MODE - Applying changes to database\n")
    
    print(f"Found {len(nsf_returns)} NSF RETURN transactions")
    print(f"Found {len(nsf_fees)} NSF FEE transactions\n")
    
    updates = []
    
    # Process NSF Returns
    print(f"{'=' * 100}")
    print("NSF RETURNS (Credits - Money came back)")
    print(f"{'=' * 100}\n")
    
    for txn in nsf_returns:
        txn_id, txn_date, description, credit_amt, is_nsf, recn_status = txn
        
        # Extract the reversed amount from description
        import re
        reversed_amount_match = re.search(r'-([0-9]+\.[0-9]{2})', description)
        reversed_amount = float(reversed_amount_match.group(1)) if reversed_amount_match else credit_amt
        
        # Update description
        new_desc = description
        if 'NSF RETURN' not in description.upper():
            if 'BILL PAYMENT' in description.upper() or 'CHEQUE' in description.upper():
                new_desc = f"NSF RETURN - {description}"
            else:
                new_desc = f"NSF RETURN - {description}"
        
        print(f"Transaction {txn_id} ({txn_date}):")
        print(f"  OLD: {description}")
        print(f"  NEW: {new_desc}")
        print(f"  Credit: ${credit_amt:.2f} (reversed ${reversed_amount:.2f})")
        print(f"  Flags: is_nsf_charge={not is_nsf} → TRUE, reconciliation_status={recn_status} → matched")
        
        # Find original debit transaction (same date or 1-2 days before)
        cur.execute("""
            SELECT transaction_id, description, debit_amount
            FROM banking_transactions
            WHERE transaction_date >= %s::date - INTERVAL '2 days'
              AND transaction_date <= %s::date
              AND debit_amount = %s
              AND transaction_id < %s
            ORDER BY transaction_date DESC
            LIMIT 1
        """, (txn_date, txn_date, reversed_amount, txn_id))
        
        original_txn = cur.fetchone()
        if original_txn:
            print(f"  ↳ Matches original debit: Transaction {original_txn[0]} ({original_txn[1]}) ${original_txn[2]:.2f}")
        
        print()
        
        updates.append({
            'type': 'return',
            'txn_id': txn_id,
            'new_desc': new_desc,
            'original_txn_id': original_txn[0] if original_txn else None,
            'reversed_amount': reversed_amount
        })
    
    # Process NSF Fees
    print(f"\n{'=' * 100}")
    print("NSF FEES (Small debits - Bank charges)")
    print(f"{'=' * 100}\n")
    
    for txn in nsf_fees:
        txn_id, txn_date, description, debit_amt, is_nsf, recn_status = txn
        
        # Update description
        new_desc = description
        if 'NSF FEE' not in description.upper() and 'NSF CHARGE' not in description.upper():
            new_desc = f"NSF FEE - {description}"
        
        print(f"Transaction {txn_id} ({txn_date}):")
        print(f"  OLD: {description}")
        print(f"  NEW: {new_desc}")
        print(f"  Debit: ${debit_amt:.2f} (bank fee)")
        print(f"  Flags: is_nsf_charge={not is_nsf} → TRUE, reconciliation_status={recn_status} → matched")
        print()
        
        updates.append({
            'type': 'fee',
            'txn_id': txn_id,
            'new_desc': new_desc,
            'fee_amount': debit_amt
        })
    
    # Apply updates if not dry run
    if not dry_run and updates:
        print(f"\n{'=' * 100}")
        print("APPLYING UPDATES")
        print(f"{'=' * 100}\n")
        
        for update in updates:
            txn_id = update['txn_id']
            new_desc = update['new_desc']
            
            # Update banking transaction
            cur.execute("""
                UPDATE banking_transactions
                SET description = %s,
                    is_nsf_charge = TRUE,
                    reconciliation_status = 'matched',
                    reconciliation_notes = COALESCE(reconciliation_notes, '') || 
                        ' NSF pattern identified and processed on ' || NOW()::date,
                    reconciled_at = NOW(),
                    reconciled_by = 'nsf_reconciliation_handler',
                    updated_at = NOW()
                WHERE transaction_id = %s
            """, (new_desc, txn_id))
            
            # Update linked receipt if exists
            cur.execute("""
                UPDATE receipts
                SET vendor_name = %s,
                    description = %s,
                    category = CASE 
                        WHEN %s = 'fee' THEN 'Banking Fees'
                        ELSE category
                    END
                WHERE banking_transaction_id = %s
            """, (new_desc[:100], new_desc, update['type'], txn_id))
            
            # Log to audit trail
            cur.execute("""
                INSERT INTO financial_audit_trail 
                (event_type, entity_type, entity_id, description, created_by)
                VALUES 
                ('nsf_reconciliation', 'banking_transaction', %s, %s, 'nsf_reconciliation_handler')
            """, (txn_id, f"NSF {update['type']} - Updated description and reconciliation status"))
            
            print(f"✅ Updated transaction {txn_id}")
        
        conn.commit()
        print(f"\n✅ Successfully updated {len(updates)} transactions")
        
    elif dry_run:
        print(f"\n⚠️  DRY RUN: Would update {len(updates)} transactions")
        print("   Run with --write flag to apply changes")
    
    return updates


def main():
    import sys
    dry_run = '--write' not in sys.argv
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    
    try:
        cur = conn.cursor()
        updates = process_nsf_pattern(cur, conn, dry_run=dry_run)
        
        if updates:
            print(f"\n{'=' * 100}")
            print("VERIFICATION WORKFLOW")
            print(f"{'=' * 100}\n")
            print("After NSF reconciliation, you should:")
            print("1. Review the updates in the desktop app")
            print("2. Verify each NSF pattern is correctly identified")
            print("3. Mark transactions as verified=TRUE for CRA compliance")
            print("4. Lock transactions (locked=TRUE) once verified and approved")
            print()
            print("SQL to mark as verified:")
            print("  UPDATE banking_transactions SET verified = TRUE, locked = TRUE")
            print("  WHERE transaction_id IN (...list of NSF transaction IDs...)")
        
        cur.close()
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
