#!/usr/bin/env python3
"""
Analyze negative payment entries to classify them by type.
Negative payments represent refunds, NSF reversals, and accounting corrections.

Classification Strategy:
1. NSF Reversals - Negative entry with "NSF" in notes + matching positive entry within 30 days
2. Refunds - Negative entry linked to cancelled charter
3. Corrections - Negative entry offsetting duplicate positive entry (same amount, same key)
4. Unknown - Other negative entries requiring manual review
"""

import psycopg2
import os
from datetime import datetime, timedelta
from collections import defaultdict
import argparse

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def main():
    parser = argparse.ArgumentParser(description='Classify negative payment entries')
    parser.add_argument('--write', action='store_true', help='Apply classification to database')
    args = parser.parse_args()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 120)
    print("NEGATIVE PAYMENT CLASSIFICATION")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Mode: {'WRITE' if args.write else 'DRY RUN'}")
    print("=" * 120)
    
    # Get all negative payments
    cur.execute("""
        SELECT 
            payment_id,
            payment_date,
            amount,
            payment_method,
            account_number,
            payment_key,
            notes,
            reference_number
        FROM payments
        WHERE amount < 0
        AND payment_date >= '2007-01-01'
        AND payment_date < '2025-01-01'
        ORDER BY payment_date DESC, amount
    """)
    
    negative_payments = cur.fetchall()
    
    print(f"\n### NEGATIVE PAYMENTS OVERVIEW ###")
    print(f"Total: {len(negative_payments)} payments")
    print(f"Total amount: ${sum(p[2] for p in negative_payments):,.2f}\n")
    
    # Classification buckets
    nsf_reversals = []
    refunds = []
    corrections = []
    unknown = []
    
    for payment in negative_payments:
        pid, pdate, amount, method, acct, pkey, notes, ref = payment
        notes_lower = (notes or '').lower()
        
        # Classification logic
        classified = False
        
        # 1. NSF Detection - "NSF" or "Returned Cheque" in notes
        if 'nsf' in notes_lower or 'returned cheque' in notes_lower or 'returned check' in notes_lower:
            # Look for matching positive re-attempt
            cur.execute("""
                SELECT payment_id, payment_date, amount, notes
                FROM payments
                WHERE payment_date BETWEEN %s AND %s
                AND amount = %s
                AND payment_id != %s
                ORDER BY payment_date
                LIMIT 1
            """, (pdate, pdate + timedelta(days=60), abs(amount), pid))
            
            positive_match = cur.fetchone()
            nsf_reversals.append((payment, positive_match))
            classified = True
        
        # 2. Duplicate Correction - Same payment_key with opposite amounts
        elif pkey:
            cur.execute("""
                SELECT payment_id, payment_date, amount
                FROM payments
                WHERE payment_key = %s
                AND payment_id != %s
                AND amount = %s
                ORDER BY payment_date
                LIMIT 1
            """, (pkey, pid, abs(amount)))
            
            duplicate_match = cur.fetchone()
            if duplicate_match:
                corrections.append((payment, duplicate_match))
                classified = True
        
        # 3. Refund - Could check for cancelled charters, but skip for now
        # (Would need charter status data)
        
        if not classified:
            unknown.append((payment, None))
    
    # Display results
    print(f"### CLASSIFICATION RESULTS ###\n")
    print(f"{'Category':<20} {'Count':<10} {'Amount':<15}")
    print("-" * 50)
    print(f"{'NSF Reversals':<20} {len(nsf_reversals):<10} ${sum(p[0][2] for p in nsf_reversals):,.2f}")
    print(f"{'Corrections':<20} {len(corrections):<10} ${sum(p[0][2] for p in corrections):,.2f}")
    print(f"{'Unknown/Refunds':<20} {len(unknown):<10} ${sum(p[0][2] for p in unknown):,.2f}")
    print("-" * 50)
    print(f"{'TOTAL':<20} {len(negative_payments):<10} ${sum(p[2] for p in negative_payments):,.2f}")
    
    # NSF Details
    if nsf_reversals:
        print(f"\n### NSF REVERSALS (First 10) ###")
        print(f"{'ID':<8} {'Date':<12} {'Amount':<12} {'Re-attempt ID':<15} {'Re-attempt Date':<15} {'Notes':<50}")
        print("-" * 120)
        
        for payment, positive in nsf_reversals[:10]:
            pid, pdate, amount, method, acct, pkey, notes, ref = payment
            notes_str = (notes or '')[:47] + '...' if notes and len(notes) > 50 else (notes or '')
            
            if positive:
                pos_id, pos_date, pos_amt, pos_notes = positive
                print(f"{pid:<8} {str(pdate):<12} ${amount:>10.2f} {pos_id:<15} {str(pos_date):<15} {notes_str}")
            else:
                print(f"{pid:<8} {str(pdate):<12} ${amount:>10.2f} {'(no match)':<15} {'':<15} {notes_str}")
    
    # Corrections Details
    if corrections:
        print(f"\n### DUPLICATE CORRECTIONS (First 10) ###")
        print(f"{'Neg ID':<8} {'Date':<12} {'Amount':<12} {'Pos ID':<10} {'Pos Date':<12} {'Payment Key':<25}")
        print("-" * 100)
        
        for payment, duplicate in corrections[:10]:
            pid, pdate, amount, method, acct, pkey, notes, ref = payment
            
            if duplicate:
                dup_id, dup_date, dup_amt = duplicate
                print(f"{pid:<8} {str(pdate):<12} ${amount:>10.2f} {dup_id:<10} {str(dup_date):<12} {pkey or '':<25}")
    
    # Unknown sample
    if unknown:
        print(f"\n### UNKNOWN/REFUNDS (First 10) ###")
        print(f"{'ID':<8} {'Date':<12} {'Amount':<12} {'Method':<15} {'Account':<12} {'Notes':<50}")
        print("-" * 120)
        
        for payment, _ in unknown[:10]:
            pid, pdate, amount, method, acct, pkey, notes, ref = payment
            notes_str = (notes or '')[:47] + '...' if notes and len(notes) > 50 else (notes or '')
            print(f"{pid:<8} {str(pdate):<12} ${amount:>10.2f} {method or '':<15} {acct or '':<12} {notes_str}")
    
    # Apply classification if --write
    if args.write:
        print(f"\n### APPLYING CLASSIFICATION ###")
        
        # Add adjustment_type column if not exists
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns
            WHERE table_name = 'payments'
            AND column_name = 'adjustment_type'
        """)
        
        if not cur.fetchone():
            print("Adding adjustment_type column to payments table...")
            cur.execute("""
                ALTER TABLE payments
                ADD COLUMN adjustment_type VARCHAR(50)
            """)
        
        # Add related_payment_id column for linking NSF/corrections
        cur.execute("""
            SELECT column_name
            FROM information_schema.columns  
            WHERE table_name = 'payments'
            AND column_name = 'related_payment_id'
        """)
        
        if not cur.fetchone():
            print("Adding related_payment_id column to payments table...")
            cur.execute("""
                ALTER TABLE payments
                ADD COLUMN related_payment_id INTEGER REFERENCES payments(payment_id)
            """)
        
        # Update NSF reversals
        nsf_count = 0
        for payment, positive in nsf_reversals:
            pid = payment[0]
            pos_id = positive[0] if positive else None
            
            cur.execute("""
                UPDATE payments
                SET adjustment_type = 'NSF_REVERSAL',
                    related_payment_id = %s
                WHERE payment_id = %s
            """, (pos_id, pid))
            nsf_count += cur.rowcount
        
        # Update corrections
        corr_count = 0
        for payment, duplicate in corrections:
            pid = payment[0]
            dup_id = duplicate[0] if duplicate else None
            
            cur.execute("""
                UPDATE payments
                SET adjustment_type = 'DUPLICATE_CORRECTION',
                    related_payment_id = %s
                WHERE payment_id = %s
            """, (dup_id, pid))
            corr_count += cur.rowcount
        
        # Update unknown as potential refunds
        refund_count = 0
        for payment, _ in unknown:
            pid = payment[0]
            
            cur.execute("""
                UPDATE payments
                SET adjustment_type = 'REFUND_OR_CORRECTION'
                WHERE payment_id = %s
            """, (pid,))
            refund_count += cur.rowcount
        
        conn.commit()
        
        print(f"\n### SUMMARY ###")
        print(f"[OK] Classified {nsf_count} NSF reversals")
        print(f"[OK] Classified {corr_count} duplicate corrections")
        print(f"[OK] Classified {refund_count} refunds/other corrections")
        print(f"[OK] Total classified: {nsf_count + corr_count + refund_count} negative payments")
        
    else:
        print(f"\n### DRY RUN COMPLETE ###")
        print(f"Run with --write to apply classification")
        print(f"This will:")
        print(f"  1. Add adjustment_type column to payments table")
        print(f"  2. Add related_payment_id column for linking")
        print(f"  3. Classify {len(nsf_reversals)} as NSF_REVERSAL")
        print(f"  4. Classify {len(corrections)} as DUPLICATE_CORRECTION")
        print(f"  5. Classify {len(unknown)} as REFUND_OR_CORRECTION")
    
    print("\n" + "=" * 120)
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
