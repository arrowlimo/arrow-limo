#!/usr/bin/env python3
"""
Reconcile 182 "credit_card" payments from 2012 against banking_transactions.
These are CIBC merchant deposit batches, not individual customer payments.

Strategy:
1. Find banking_transactions with matching date and credit_amount
2. Link payments to banking transactions via new field: banking_transaction_id
3. Generate reconciliation report
4. Mark as reconciled (not linked to charters)
"""

import psycopg2
import os
from datetime import datetime, timedelta
from decimal import Decimal
import argparse

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def main():
    parser = argparse.ArgumentParser(description='Reconcile merchant deposits to banking transactions')
    parser.add_argument('--write', action='store_true', help='Apply changes to database')
    parser.add_argument('--tolerance', type=float, default=0.01, help='Amount tolerance for matching (default: $0.01)')
    parser.add_argument('--date-window', type=int, default=3, help='Date window in days (default: ±3)')
    args = parser.parse_args()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 120)
    print("MERCHANT DEPOSIT RECONCILIATION")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Mode: {'WRITE' if args.write else 'DRY RUN'}")
    print(f"Tolerance: ±${args.tolerance}")
    print(f"Date Window: ±{args.date_window} days")
    print("=" * 120)
    
    # Get all 2012 credit_card "payments" (actually merchant deposits)
    cur.execute("""
        SELECT 
            payment_id,
            payment_date,
            amount,
            account_number,
            payment_key,
            notes
        FROM payments
        WHERE payment_method = 'credit_card'
        AND (charter_id IS NULL OR charter_id = 0)
        AND payment_date >= '2012-01-01'
        AND payment_date < '2013-01-01'
        ORDER BY payment_date, amount DESC
    """)
    
    merchant_deposits = cur.fetchall()
    print(f"\n### MERCHANT DEPOSITS TO RECONCILE ###")
    print(f"Total: {len(merchant_deposits)} entries")
    print(f"Amount: ${sum(p[2] for p in merchant_deposits if p[2]):,.2f}\n")
    
    # Match against banking_transactions
    matches = []
    unmatched = []
    
    for payment_id, pay_date, amount, acct_num, pay_key, notes in merchant_deposits:
        if not amount:
            unmatched.append((payment_id, pay_date, amount, "Zero amount"))
            continue
        
        # Find banking transactions within date window with matching credit amount
        date_start = pay_date - timedelta(days=args.date_window)
        date_end = pay_date + timedelta(days=args.date_window)
        
        cur.execute("""
            SELECT 
                transaction_id,
                transaction_date,
                credit_amount,
                description,
                ABS(transaction_date - %s) as days_diff
            FROM banking_transactions
            WHERE transaction_date BETWEEN %s AND %s
            AND credit_amount IS NOT NULL
            AND ABS(credit_amount - %s) <= %s
            ORDER BY ABS(transaction_date - %s), ABS(credit_amount - %s)
            LIMIT 3
        """, (pay_date, date_start, date_end, amount, args.tolerance, pay_date, amount))
        
        bank_matches = cur.fetchall()
        
        if bank_matches:
            # Take best match (closest date, then closest amount)
            best_match = bank_matches[0]
            bank_id, bank_date, bank_amount, bank_desc, days_diff = best_match
            
            matches.append({
                'payment_id': payment_id,
                'payment_date': pay_date,
                'payment_amount': amount,
                'banking_id': bank_id,
                'banking_date': bank_date,
                'banking_amount': bank_amount,
                'days_diff': days_diff,
                'amount_diff': abs(float(amount) - float(bank_amount)),
                'description': bank_desc,
                'notes': notes
            })
        else:
            unmatched.append((payment_id, pay_date, amount, "No banking match found"))
    
    # Display results
    print(f"\n### RECONCILIATION RESULTS ###")
    print(f"Matched: {len(matches)}/{len(merchant_deposits)} ({len(matches)/len(merchant_deposits)*100:.1f}%)")
    print(f"Unmatched: {len(unmatched)}")
    print(f"Matched amount: ${sum(m['payment_amount'] for m in matches):,.2f}")
    
    if matches:
        print(f"\n### MATCHED DEPOSITS (First 20) ###")
        print(f"{'Pay ID':<8} {'Pay Date':<12} {'Pay $':<10} {'Days':<6} {'Bank ID':<10} {'Bank Date':<12} {'Bank $':<10} {'Diff':<8}")
        print("-" * 120)
        
        for m in matches[:20]:
            print(f"{m['payment_id']:<8} {str(m['payment_date']):<12} ${m['payment_amount']:>8.2f} "
                  f"{int(m['days_diff']):<6} {m['banking_id']:<10} {str(m['banking_date']):<12} "
                  f"${m['banking_amount']:>8.2f} ${m['amount_diff']:>6.2f}")
    
    if unmatched:
        print(f"\n### UNMATCHED DEPOSITS ###")
        print(f"{'Pay ID':<8} {'Date':<12} {'Amount':<12} {'Reason':<50}")
        print("-" * 100)
        for pid, pdate, amt, reason in unmatched:
            amt_str = f"${amt:.2f}" if amt else "$0.00"
            print(f"{pid:<8} {str(pdate):<12} {amt_str:<12} {reason}")
    
    # Apply updates if --write
    if args.write and matches:
        print(f"\n### APPLYING UPDATES ###")
        
        # Check if banking_transaction_id column exists
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'payments' 
            AND column_name = 'banking_transaction_id'
        """)
        
        if not cur.fetchone():
            print("Adding banking_transaction_id column to payments table...")
            cur.execute("""
                ALTER TABLE payments 
                ADD COLUMN IF NOT EXISTS banking_transaction_id INTEGER REFERENCES banking_transactions(transaction_id)
            """)
        
        # Update payment records with banking links
        update_count = 0
        for m in matches:
            cur.execute("""
                UPDATE payments 
                SET banking_transaction_id = %s,
                    notes = COALESCE(notes, '') || ' | Reconciled to banking ' || to_char(NOW(), 'YYYY-MM-DD')
                WHERE payment_id = %s
            """, (m['banking_id'], m['payment_id']))
            update_count += cur.rowcount
        
        conn.commit()
        print(f"Updated {update_count} payment records with banking links")
        
        # Create summary
        print(f"\n### SUMMARY ###")
        print(f"[OK] Reconciled {len(matches)} merchant deposits to banking transactions")
        print(f"[OK] Total reconciled: ${sum(m['payment_amount'] for m in matches):,.2f}")
        print(f"[OK] Average match accuracy: {sum(m['days_diff'] for m in matches)/len(matches):.1f} days, ${sum(m['amount_diff'] for m in matches)/len(matches):.2f} amount")
        
    else:
        print(f"\n### DRY RUN COMPLETE ###")
        print(f"Run with --write to apply {len(matches)} updates to database")
        print(f"This will:")
        print(f"  1. Add banking_transaction_id column if needed")
        print(f"  2. Link {len(matches)} payments to banking_transactions")
        print(f"  3. Add reconciliation notes to payment records")
    
    print("\n" + "=" * 120)
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
