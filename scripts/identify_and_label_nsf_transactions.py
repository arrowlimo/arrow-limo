#!/usr/bin/env python3
"""
Identify and properly label NSF (Non-Sufficient Funds) transactions.

NSF Pattern:
1. Original check/payment (debit)
2. NSF Reversal (credit - money comes back)
3. NSF Fee (debit - bank charges fee)
4. Optional: Re-payment (new debit)

Updates:
- Set is_nsf_charge flag
- Update descriptions to include "NSF RETURN" or "NSF FEE"
- Update corresponding receipts
"""

import psycopg2
import os
from datetime import datetime

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

def identify_nsf_patterns(cur):
    """
    Identify NSF patterns:
    - Credit transaction that reverses a debit (NSF RETURN)
    - Small debit (usually $10-$45) with -XXX.XX in description (NSF FEE)
    """
    
    print("=== IDENTIFYING NSF PATTERNS ===\n")
    
    # Pattern 1: Credits that look like NSF reversals
    # Usually same day as original debit, description mentions the reversed amount
    cur.execute("""
        SELECT transaction_id, transaction_date, description, 
               credit_amount, debit_amount, is_nsf_charge
        FROM banking_transactions
        WHERE credit_amount > 0
          AND (
              description ILIKE '%nsf%'
              OR description ILIKE '%insufficient%'
              OR description ILIKE '%returned%'
              OR description ILIKE '%bill payment%'
              OR description ~ '-[0-9]+\.[0-9]{2}'  -- Has negative amount in description
          )
          AND is_nsf_charge IS NOT TRUE
        ORDER BY transaction_date, transaction_id
    """)
    
    nsf_returns = cur.fetchall()
    print(f"Found {len(nsf_returns)} potential NSF RETURN transactions:\n")
    for row in nsf_returns:
        print(f"  {row[0]}: {row[1]} | {row[2]}")
        print(f"    Credit: ${row[3]:.2f}")
    
    # Pattern 2: NSF fees (small debits with negative amount in description)
    # ONLY transactions that have a negative amount mentioned (e.g., "-150.00")
    # This indicates the original transaction was reversed
    cur.execute("""
        SELECT transaction_id, transaction_date, description, 
               debit_amount, credit_amount, is_nsf_charge
        FROM banking_transactions
        WHERE debit_amount > 0
          AND debit_amount < 50  -- NSF fees are typically $10-$45
          AND (
              description ILIKE '%nsf%'
              OR description ~ '-[0-9]+\.[0-9]{2}'  -- Has negative amount in description
          )
          AND is_nsf_charge IS NOT TRUE
        ORDER BY transaction_date, transaction_id
    """)
    
    nsf_fees = cur.fetchall()
    print(f"\nFound {len(nsf_fees)} potential NSF FEE transactions:\n")
    for row in nsf_fees:
        print(f"  {row[0]}: {row[1]} | {row[2]}")
        print(f"    Debit: ${row[3]:.2f}")
    
    return nsf_returns, nsf_fees


def update_nsf_transactions(cur, conn, dry_run=True):
    """Update NSF transactions with proper flags and descriptions."""
    
    nsf_returns, nsf_fees = identify_nsf_patterns(cur)
    
    if not nsf_returns and not nsf_fees:
        print("\nNo NSF transactions found to update.")
        return
    
    print(f"\n{'=' * 80}")
    print(f"{'DRY RUN - NO CHANGES WILL BE MADE' if dry_run else 'APPLYING UPDATES'}")
    print(f"{'=' * 80}\n")
    
    updates_made = 0
    
    # Update NSF RETURN transactions
    for row in nsf_returns:
        txn_id, txn_date, description, credit_amt, debit_amt, is_nsf = row
        
        # Add "NSF RETURN" to description if not already present
        new_desc = description
        if 'NSF RETURN' not in description.upper():
            if 'BILL PAYMENT' in description.upper():
                new_desc = description.replace('Bill Payment', 'NSF RETURN - Bill Payment')
                new_desc = new_desc.replace('BILL PAYMENT', 'NSF RETURN - BILL PAYMENT')
            else:
                new_desc = f"NSF RETURN - {description}"
        
        print(f"Transaction {txn_id} ({txn_date}):")
        print(f"  OLD: {description}")
        print(f"  NEW: {new_desc}")
        print(f"  Flag: is_nsf_charge = TRUE")
        print()
        
        if not dry_run:
            cur.execute("""
                UPDATE banking_transactions
                SET description = %s,
                    is_nsf_charge = TRUE,
                    updated_at = NOW()
                WHERE transaction_id = %s
            """, (new_desc, txn_id))
            
            # Update corresponding receipt if exists
            cur.execute("""
                UPDATE receipts
                SET vendor_name = %s,
                    description = %s
                WHERE banking_transaction_id = %s
            """, (new_desc[:100], new_desc, txn_id))
            
            updates_made += 1
    
    # Update NSF FEE transactions
    for row in nsf_fees:
        txn_id, txn_date, description, debit_amt, credit_amt, is_nsf = row
        
        # Add "NSF FEE" to description if not already present
        new_desc = description
        if 'NSF FEE' not in description.upper() and 'NSF CHARGE' not in description.upper():
            new_desc = f"NSF FEE - {description}"
        
        print(f"Transaction {txn_id} ({txn_date}):")
        print(f"  OLD: {description}")
        print(f"  NEW: {new_desc}")
        print(f"  Flag: is_nsf_charge = TRUE")
        print()
        
        if not dry_run:
            cur.execute("""
                UPDATE banking_transactions
                SET description = %s,
                    is_nsf_charge = TRUE,
                    updated_at = NOW()
                WHERE transaction_id = %s
            """, (new_desc, txn_id))
            
            # Update corresponding receipt if exists
            cur.execute("""
                UPDATE receipts
                SET vendor_name = %s,
                    description = %s,
                    category = 'Banking Fees'
                WHERE banking_transaction_id = %s
            """, (new_desc[:100], new_desc, txn_id))
            
            updates_made += 1
    
    if not dry_run:
        conn.commit()
        print(f"\n✅ Updated {updates_made} NSF transactions")
    else:
        print(f"\n⚠️  DRY RUN: Would update {len(nsf_returns) + len(nsf_fees)} transactions")
        print("\nRun with --write flag to apply changes.")


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
        update_nsf_transactions(cur, conn, dry_run=dry_run)
        cur.close()
    except Exception as e:
        conn.rollback()
        print(f"❌ Error: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
