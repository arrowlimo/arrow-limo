#!/usr/bin/env python3
"""
Verify "duplicate" receipts against banking transactions.

CRITICAL DISTINCTION:
- TRUE DUPLICATES: Same date/amount/vendor with SINGLE banking transaction (or none)
- RECURRING PAYMENTS: Same amount/vendor, DIFFERENT dates, EACH with own banking entry
- NSF RETRIES: Original NSF'd payment + successful retry (both legitimate)

This script verifies each potential duplicate against banking_transactions
to determine if it's a real duplicate or a legitimate recurring payment.
"""

import psycopg2
import os
from datetime import datetime

# Database connection
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

def main():
    conn = psycopg2.connect(
        host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    print("=" * 80)
    print("DUPLICATE VERIFICATION AGAINST BANKING TRANSACTIONS")
    print("=" * 80)
    print()
    
    # Find potential duplicates (same date, vendor, amount)
    cur.execute("""
        SELECT 
            receipt_date,
            vendor_name,
            gross_amount,
            COUNT(*) as receipt_count,
            ARRAY_AGG(receipt_id ORDER BY receipt_id) as receipt_ids,
            ARRAY_AGG(banking_transaction_id ORDER BY receipt_id) as banking_ids,
            ARRAY_AGG(receipt_source ORDER BY receipt_id) as sources
        FROM receipts
        WHERE exclude_from_reports = FALSE
        GROUP BY receipt_date, vendor_name, gross_amount
        HAVING COUNT(*) > 1
        ORDER BY gross_amount DESC, receipt_date
    """)
    
    duplicates = cur.fetchall()
    
    print(f"Found {len(duplicates)} sets of potential duplicates\n")
    
    true_duplicates = []
    recurring_payments = []
    nsf_retries = []
    
    for date, vendor, amount, count, receipt_ids, banking_ids, sources in duplicates:
        # Handle NULL amounts
        if amount is None:
            amount = 0.0
        
        # Remove None values and get unique banking transaction IDs
        linked_banking_ids = [bid for bid in banking_ids if bid is not None]
        unique_banking_ids = list(set(linked_banking_ids))
        
        print(f"\n{'='*70}")
        print(f"Date: {date} | Vendor: {vendor} | Amount: ${amount if amount else 0:,.2f}")
        print(f"Receipt count: {count}")
        print(f"Receipt IDs: {receipt_ids}")
        print(f"Banking IDs: {banking_ids}")
        print(f"Unique banking links: {len(unique_banking_ids)}")
        print(f"Sources: {sources}")
        
        # Classify the duplicate
        if len(unique_banking_ids) == 0:
            # No banking links - unlinked duplicates (TRUE DUPLICATES)
            print("❌ TRUE DUPLICATE: No banking links - all receipts are unlinked")
            true_duplicates.append({
                'date': date,
                'vendor': vendor,
                'amount': amount,
                'receipt_ids': receipt_ids,
                'reason': 'No banking links',
                'inflation': amount * (count - 1)
            })
        
        elif len(unique_banking_ids) == 1:
            # Single banking transaction with multiple receipts (TRUE DUPLICATE)
            print(f"❌ TRUE DUPLICATE: {count} receipts linked to single banking TX #{unique_banking_ids[0]}")
            
            # Get banking details
            cur.execute("""
                SELECT transaction_date, description, debit_amount
                FROM banking_transactions
                WHERE transaction_id = %s
            """, (unique_banking_ids[0],))
            
            if cur.rowcount > 0:
                tx_date, tx_desc, tx_amount = cur.fetchone()
                print(f"   Banking: {tx_date} | {tx_desc} | ${tx_amount:,.2f}")
            
            true_duplicates.append({
                'date': date,
                'vendor': vendor,
                'amount': amount,
                'receipt_ids': receipt_ids,
                'banking_id': unique_banking_ids[0],
                'reason': f'{count} receipts for 1 banking transaction',
                'inflation': amount * (count - 1)
            })
        
        elif len(unique_banking_ids) == count:
            # Each receipt has its own banking transaction
            print(f"✅ LEGITIMATE: Each receipt linked to different banking transaction")
            
            # Get banking details to verify dates
            cur.execute("""
                SELECT transaction_id, transaction_date, description, debit_amount
                FROM banking_transactions
                WHERE transaction_id = ANY(%s)
                ORDER BY transaction_date
            """, (unique_banking_ids,))
            
            banking_details = cur.fetchall()
            dates = [bd[1] for bd in banking_details]
            
            if len(set(dates)) == 1:
                # Same date - check for NSF pattern
                print(f"   Same date transactions - checking for NSF pattern...")
                
                # Check if vendor is known for NSF issues
                nsf_vendors = ['EQUITY PREMIUM FINANCE', 'HEFFNER', 'KAREN RICHARD']
                is_nsf_vendor = any(nsv in vendor.upper() for nsv in nsf_vendors)
                
                if is_nsf_vendor:
                    print(f"   ⚠️  NSF-PRONE VENDOR: Likely NSF retry scenario")
                    nsf_retries.append({
                        'date': date,
                        'vendor': vendor,
                        'amount': amount,
                        'receipt_ids': receipt_ids,
                        'banking_ids': unique_banking_ids,
                        'note': 'Same date, NSF-prone vendor - verify manually'
                    })
                else:
                    print(f"   ❌ SUSPICIOUS: Same date, each with banking link - may be import error")
                    true_duplicates.append({
                        'date': date,
                        'vendor': vendor,
                        'amount': amount,
                        'receipt_ids': receipt_ids,
                        'banking_ids': unique_banking_ids,
                        'reason': 'Same date, multiple banking links (suspicious)',
                        'inflation': amount * (count - 1)
                    })
            else:
                # Different dates - RECURRING PAYMENT
                print(f"   ✅ RECURRING PAYMENT: Different transaction dates")
                print(f"      Dates: {', '.join(str(d) for d in dates)}")
                recurring_payments.append({
                    'vendor': vendor,
                    'amount': amount,
                    'receipt_count': count,
                    'dates': dates
                })
        
        else:
            # Mixed scenario - some receipts share banking, some don't
            unlinked_count = count - len(linked_banking_ids)
            print(f"⚠️  MIXED: {len(unique_banking_ids)} banking links for {count} receipts ({unlinked_count} unlinked)")
            print(f"   This suggests import errors or partial duplicates")
            
            true_duplicates.append({
                'date': date,
                'vendor': vendor,
                'amount': amount,
                'receipt_ids': receipt_ids,
                'banking_ids': unique_banking_ids,
                'reason': f'Mixed: {len(unique_banking_ids)} banking for {count} receipts',
                'inflation': amount * (count - len(unique_banking_ids) - unlinked_count)
            })
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    print(f"\n✅ LEGITIMATE RECURRING PAYMENTS: {len(recurring_payments)}")
    recurring_total = sum(rp['amount'] for rp in recurring_payments)
    print(f"   (Same amount/vendor, different dates, each with banking link)")
    print(f"   Total value: ${recurring_total:,.2f}")
    
    if recurring_payments[:5]:
        print("\n   Examples:")
        for rp in recurring_payments[:5]:
            print(f"   - {rp['vendor']}: ${rp['amount']:,.2f} x {rp['receipt_count']} times")
    
    print(f"\n⚠️  NSF RETRY SCENARIOS: {len(nsf_retries)}")
    nsf_total = sum(nr['amount'] for nr in nsf_retries)
    print(f"   (Need manual verification - may be legitimate retries)")
    print(f"   Total value: ${nsf_total:,.2f}")
    
    if nsf_retries:
        print("\n   Cases to verify:")
        for nr in nsf_retries:
            print(f"   - {nr['vendor']}: ${nr['amount']:,.2f} on {nr['date']}")
            print(f"     Receipt IDs: {nr['receipt_ids']}")
    
    print(f"\n❌ TRUE DUPLICATES: {len(true_duplicates)}")
    total_inflation = sum(td.get('inflation', 0) for td in true_duplicates)
    print(f"   Total inflation: ${total_inflation:,.2f}")
    
    if true_duplicates:
        print("\n   Top 10 by inflation:")
        sorted_dupes = sorted(true_duplicates, key=lambda x: x.get('inflation', 0), reverse=True)
        for td in sorted_dupes[:10]:
            print(f"\n   {td['date']} | {td['vendor']} | ${td['amount']:,.2f}")
            print(f"   Receipt IDs: {td['receipt_ids']}")
            print(f"   Reason: {td['reason']}")
            print(f"   Inflation: ${td.get('inflation', 0):,.2f}")
    
    print("\n" + "=" * 80)
    print("NEXT STEPS")
    print("=" * 80)
    print(f"1. Review NSF retry scenarios manually ({len(nsf_retries)} cases)")
    print(f"2. Delete true duplicates to remove ${total_inflation:,.2f} inflation")
    print(f"3. Recurring payments are legitimate - no action needed")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
