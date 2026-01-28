#!/usr/bin/env python3
"""
Calculate NSF costs (fees only, not bounced cheques)
Verify one-to-one receipt-to-banking matching
Identify duplicate entries causing inflation
"""
import psycopg2
from collections import defaultdict

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = "***REMOVED***"

def main():
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    print("="*100)
    print("NSF COST ANALYSIS & ONE-TO-ONE RECEIPT VERIFICATION")
    print("="*100)
    
    # Calculate NSF fees (actual bank charges)
    print("\nNSF FEES (Actual Bank Charges - Real Costs):")
    print("-"*100)
    
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM transaction_date)::int as year,
            COUNT(*) as fee_count,
            SUM(debit_amount) as total_fees
        FROM banking_transactions
        WHERE (description ILIKE '%NSF FEE%' 
            OR description ILIKE '%NSF CHARGE%'
            OR description ILIKE '%RETURNED ITEM FEE%'
            OR description ILIKE '%DISHONOURED%')
        AND debit_amount IS NOT NULL
        GROUP BY EXTRACT(YEAR FROM transaction_date)
        ORDER BY year
    """)
    
    nsf_fees = cur.fetchall()
    
    total_nsf_fees = 0
    if nsf_fees:
        print("\nNSF Fees by Year:")
        for year, count, total in nsf_fees:
            total_nsf_fees += float(total) if total else 0
            print(f"  {year}: {count} fees, ${total:,.2f}" if total else f"  {year}: {count} fees")
        
        print(f"\nTOTAL NSF FEES INCURRED: ${total_nsf_fees:,.2f}")
    else:
        print("\nNo NSF fees found in banking")
    
    # Check for duplicate receipts
    print(f"\n{'='*100}")
    print("CHECKING FOR DUPLICATE RECEIPTS")
    print(f"{'='*100}")
    
    cur.execute("""
        SELECT 
            receipt_date,
            vendor_name,
            gross_amount,
            COUNT(*) as dup_count,
            ARRAY_AGG(receipt_id ORDER BY receipt_id) as receipt_ids,
            ARRAY_AGG(source_system ORDER BY receipt_id) as sources
        FROM receipts
        WHERE gross_amount IS NOT NULL
        AND exclude_from_reports = FALSE
        GROUP BY receipt_date, vendor_name, gross_amount
        HAVING COUNT(*) > 1
        ORDER BY gross_amount DESC, receipt_date
        LIMIT 100
    """)
    
    duplicates = cur.fetchall()
    
    if duplicates:
        print(f"\nFound {len(duplicates)} sets of duplicate receipts:")
        
        total_duplicate_amount = 0
        for date, vendor, amount, count, ids, sources in duplicates[:30]:  # Show top 30
            duplicate_amt = float(amount) * (count - 1)  # Extra copies
            total_duplicate_amount += duplicate_amt
            
            print(f"\n  {date} | {vendor or 'NO VENDOR'} | ${amount:,.2f} x {count} copies")
            print(f"    Receipt IDs: {ids}")
            print(f"    Sources: {sources}")
            print(f"    Duplicate amount: ${duplicate_amt:,.2f}")
        
        print(f"\n  TOTAL DUPLICATE INFLATION (top 30): ${total_duplicate_amount:,.2f}")
    else:
        print("\nNo duplicate receipts found")
    
    # Check one-to-one banking matching
    print(f"\n{'='*100}")
    print("ONE-TO-ONE BANKING VERIFICATION")
    print(f"{'='*100}")
    
    # Multiple receipts for same banking transaction
    cur.execute("""
        SELECT 
            bt.transaction_id,
            bt.transaction_date,
            bt.description,
            bt.debit_amount,
            bt.credit_amount,
            COUNT(r.receipt_id) as receipt_count,
            ARRAY_AGG(r.receipt_id ORDER BY r.receipt_id) as receipt_ids,
            SUM(r.gross_amount) as total_receipts
        FROM banking_transactions bt
        INNER JOIN receipts r ON r.banking_transaction_id = bt.transaction_id
        WHERE r.exclude_from_reports = FALSE
        GROUP BY bt.transaction_id, bt.transaction_date, bt.description, bt.debit_amount, bt.credit_amount
        HAVING COUNT(r.receipt_id) > 1
        ORDER BY COUNT(r.receipt_id) DESC, bt.transaction_date
        LIMIT 50
    """)
    
    multi_receipts = cur.fetchall()
    
    if multi_receipts:
        print(f"\nFound {len(multi_receipts)} banking transactions with MULTIPLE receipts:")
        
        inflation = 0
        for tx_id, date, desc, debit, credit, count, ids, total_rec in multi_receipts[:20]:
            bank_amt = float(debit) if debit else float(credit)
            rec_amt = float(total_rec) if total_rec else 0
            diff = rec_amt - bank_amt
            inflation += diff
            
            print(f"\n  TX #{tx_id} | {date} | ${bank_amt:,.2f}")
            print(f"    {desc[:80]}")
            print(f"    {count} receipts totaling ${rec_amt:,.2f} (inflation: ${diff:,.2f})")
            print(f"    Receipt IDs: {ids}")
        
        print(f"\n  TOTAL INFLATION FROM MULTIPLE RECEIPTS (top 20): ${inflation:,.2f}")
    else:
        print("\nAll banking transactions have one-to-one receipt matching")
    
    # Overall totals verification
    print(f"\n{'='*100}")
    print("OVERALL TOTALS VERIFICATION")
    print(f"{'='*100}")
    
    # Banking totals
    cur.execute("""
        SELECT 
            SUM(debit_amount) as total_debits,
            SUM(credit_amount) as total_credits
        FROM banking_transactions
        WHERE account_number IN ('0228362', '903990106011', '61615', '8032', 'SQUARE')
        AND verified = TRUE
    """)
    
    bank_debits, bank_credits = cur.fetchone()
    
    print(f"\nVERIFIED BANKING TOTALS:")
    print(f"  Total Debits (expenses): ${bank_debits:,.2f}" if bank_debits else "  Total Debits: NULL")
    print(f"  Total Credits (income): ${bank_credits:,.2f}" if bank_credits else "  Total Credits: NULL")
    
    # Receipt totals
    cur.execute("""
        SELECT 
            SUM(gross_amount) as total_receipts,
            COUNT(*) as receipt_count
        FROM receipts
        WHERE exclude_from_reports = FALSE
        AND gross_amount > 0
    """)
    
    total_receipts, receipt_count = cur.fetchone()
    
    print(f"\nRECEIPT TOTALS:")
    print(f"  Total receipts: {receipt_count:,}")
    print(f"  Total amount: ${total_receipts:,.2f}" if total_receipts else "  Total amount: NULL")
    
    # Compare
    if bank_debits and total_receipts:
        diff = float(total_receipts) - float(bank_debits)
        print(f"\nCOMPARISON:")
        print(f"  Receipts - Banking Debits = ${diff:,.2f}")
        
        if diff > 0:
            pct = (diff / float(bank_debits)) * 100
            print(f"  INFLATION: {pct:.2f}%")
        elif diff < 0:
            print(f"  MISSING: ${abs(diff):,.2f} in receipts")
    
    # Check receipts NOT linked to banking
    print(f"\n{'='*100}")
    print("RECEIPTS NOT LINKED TO BANKING")
    print(f"{'='*100}")
    
    cur.execute("""
        SELECT 
            source_system,
            COUNT(*) as count,
            SUM(gross_amount) as total
        FROM receipts
        WHERE banking_transaction_id IS NULL
        AND exclude_from_reports = FALSE
        AND gross_amount > 0
        GROUP BY source_system
        ORDER BY SUM(gross_amount) DESC
    """)
    
    unlinked = cur.fetchall()
    
    if unlinked:
        print(f"\nReceipts without banking link:")
        unlinked_total = 0
        for source, count, total in unlinked:
            unlinked_total += float(total) if total else 0
            total_str = f"${total:,.2f}" if total else "NULL"
            print(f"  {source or 'NULL'}: {count:,} receipts, {total_str}")
        
        print(f"\n  TOTAL UNLINKED: ${unlinked_total:,.2f}")
        print(f"\n  These receipts may be legitimate (cash, manual entries)")
        print(f"  OR they may be causing inflation if they're duplicates")
    else:
        print("\nAll receipts are linked to banking")
    
    # Summary
    print(f"\n{'='*100}")
    print("SUMMARY")
    print(f"{'='*100}")
    
    print(f"\n1. NSF FEES (actual cost): ${total_nsf_fees:,.2f}")
    
    print(f"\n2. VERIFIED BANKING:")
    if bank_debits:
        print(f"   Expenses (debits): ${bank_debits:,.2f}")
    
    print(f"\n3. RECEIPTS IN DATABASE:")
    if total_receipts:
        print(f"   Total: ${total_receipts:,.2f} ({receipt_count:,} receipts)")
    
    if bank_debits and total_receipts:
        diff = float(total_receipts) - float(bank_debits)
        if diff > 0:
            print(f"\n4. OVER-INFLATION: ${diff:,.2f}")
            print(f"   Causes:")
            print(f"   - Duplicate receipts")
            print(f"   - Multiple receipts for same banking transaction")
            print(f"   - Unlinked receipts that duplicate banking")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
