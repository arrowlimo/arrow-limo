#!/usr/bin/env python3
"""
Comprehensive analysis of 2012-2014 data:
- Banking transactions (CIBC and Scotia)
- Receipts matched to banking
- Payments (charter-related)
- Checks issued
"""
import psycopg2
from decimal import Decimal

DB = dict(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')

print("\n" + "="*100)
print("2012-2014 FINANCIAL DATA ANALYSIS")
print("="*100)

with psycopg2.connect(**DB) as cn:
    with cn.cursor() as cur:
        for year in [2012, 2013, 2014]:
            print(f"\n{'='*100}")
            print(f"YEAR {year}")
            print(f"{'='*100}")
            
            # Banking transactions by account
            cur.execute("""
                SELECT 
                    account_number,
                    COUNT(*) as txn_count,
                    SUM(debit_amount) as total_debits,
                    SUM(credit_amount) as total_credits,
                    MIN(transaction_date) as first_date,
                    MAX(transaction_date) as last_date
                FROM banking_transactions
                WHERE EXTRACT(YEAR FROM transaction_date) = %s
                GROUP BY account_number
                ORDER BY account_number
            """, (year,))
            
            banking = cur.fetchall()
            
            if banking:
                print(f"\n📊 BANKING TRANSACTIONS:")
                print("-" * 100)
                print(f"{'Account':<15} {'Count':>8} {'Debits':>15} {'Credits':>15} {'First Date':<12} {'Last Date':<12}")
                print("-" * 100)
                
                total_txns = 0
                total_debits = Decimal('0')
                total_credits = Decimal('0')
                
                for acct, cnt, debits, credits, first, last in banking:
                    total_txns += cnt
                    total_debits += debits or 0
                    total_credits += credits or 0
                    print(f"{acct:<15} {cnt:>8} ${debits or 0:>13,.2f} ${credits or 0:>13,.2f} {first!s:<12} {last!s:<12}")
                
                print("-" * 100)
                print(f"{'TOTAL':<15} {total_txns:>8} ${total_debits:>13,.2f} ${total_credits:>13,.2f}")
            else:
                print(f"\n⚠️  No banking transactions for {year}")
            
            # Receipts
            cur.execute("""
                SELECT 
                    COUNT(*) as receipt_count,
                    SUM(gross_amount) as total_gross,
                    SUM(gst_amount) as total_gst,
                    SUM(net_amount) as total_net,
                    COUNT(CASE WHEN created_from_banking THEN 1 END) as from_banking,
                    COUNT(CASE WHEN mapped_bank_account_id IS NOT NULL THEN 1 END) as bank_linked
                FROM receipts
                WHERE EXTRACT(YEAR FROM receipt_date) = %s
            """, (year,))
            
            receipt_data = cur.fetchone()
            
            if receipt_data and receipt_data[0] > 0:
                r_cnt, r_gross, r_gst, r_net, r_from_bank, r_linked = receipt_data
                print(f"\n📋 RECEIPTS:")
                print("-" * 100)
                print(f"  Total receipts: {r_cnt:>6}")
                print(f"  Gross amount: ${r_gross:>13,.2f}")
                print(f"  GST amount: ${r_gst:>13,.2f}")
                print(f"  Net amount: ${r_net:>13,.2f}")
                print(f"  Created from banking: {r_from_bank:>6} ({r_from_bank*100/r_cnt:.1f}%)")
                print(f"  Linked to bank account: {r_linked:>6} ({r_linked*100/r_cnt:.1f}%)")
            else:
                print(f"\n⚠️  No receipts for {year}")
            
            # Receipt-Banking linkage via junction table
            cur.execute("""
                SELECT 
                    COUNT(DISTINCT bm.receipt_id) as linked_receipts,
                    COUNT(DISTINCT bm.banking_transaction_id) as linked_banking,
                    SUM(r.gross_amount) as linked_amount
                FROM banking_receipt_matching_ledger bm
                JOIN receipts r ON r.receipt_id = bm.receipt_id
                WHERE EXTRACT(YEAR FROM r.receipt_date) = %s
            """, (year,))
            
            linkage_data = cur.fetchone()
            
            if linkage_data and linkage_data[0] > 0:
                l_receipts, l_banking, l_amount = linkage_data
                print(f"\n🔗 RECEIPT-BANKING LINKAGE:")
                print("-" * 100)
                print(f"  Receipts linked: {l_receipts:>6}")
                print(f"  Banking txns linked: {l_banking:>6}")
                print(f"  Total amount linked: ${l_amount:>13,.2f}")
            
            # Charter payments
            cur.execute("""
                SELECT 
                    COUNT(*) as payment_count,
                    SUM(amount) as total_amount,
                    COUNT(DISTINCT reserve_number) as unique_charters,
                    COUNT(CASE WHEN payment_method = 'check' THEN 1 END) as check_payments,
                    COUNT(CASE WHEN payment_method = 'cash' THEN 1 END) as cash_payments,
                    COUNT(CASE WHEN payment_method = 'credit_card' THEN 1 END) as cc_payments
                FROM payments
                WHERE EXTRACT(YEAR FROM payment_date) = %s
            """, (year,))
            
            payment_data = cur.fetchone()
            
            if payment_data and payment_data[0] > 0:
                p_cnt, p_amt, p_charters, p_check, p_cash, p_cc = payment_data
                
                # Get payment amounts by method
                cur.execute('SELECT COALESCE(SUM(amount),0) FROM payments WHERE EXTRACT(YEAR FROM payment_date)=%s AND payment_method=%s', (year, 'check'))
                check_amt = cur.fetchone()[0]
                cur.execute('SELECT COALESCE(SUM(amount),0) FROM payments WHERE EXTRACT(YEAR FROM payment_date)=%s AND payment_method=%s', (year, 'cash'))
                cash_amt = cur.fetchone()[0]
                cur.execute('SELECT COALESCE(SUM(amount),0) FROM payments WHERE EXTRACT(YEAR FROM payment_date)=%s AND payment_method=%s', (year, 'credit_card'))
                cc_amt = cur.fetchone()[0]
                
                print(f"\n💰 CHARTER PAYMENTS:")
                print("-" * 100)
                print(f"  Total payments: {p_cnt:>6}")
                print(f"  Total amount: ${p_amt:>13,.2f}")
                print(f"  Unique charters: {p_charters:>6}")
                print(f"  By check: {p_check:>6} (${check_amt:,.2f})")
                print(f"  By cash: {p_cash:>6} (${cash_amt:,.2f})")
                print(f"  By credit card: {p_cc:>6} (${cc_amt:,.2f})")
            else:
                print(f"\n⚠️  No charter payments for {year}")
            
            # Check for cheque data in banking descriptions
            cur.execute("""
                SELECT COUNT(*), SUM(debit_amount)
                FROM banking_transactions
                WHERE EXTRACT(YEAR FROM transaction_date) = %s
                AND (description ILIKE '%%cheque%%' OR description ILIKE '%%chq%%')
            """, (year,))
            
            cheque_data = cur.fetchone()
            
            if cheque_data and cheque_data[0] > 0:
                chq_cnt, chq_amt = cheque_data
                print(f"\n✅ CHECKS (from banking descriptions):")
                print("-" * 100)
                print(f"  Transactions: {chq_cnt:>6}")
                print(f"  Total amount: ${chq_amt or 0:>13,.2f}")

print("\n" + "="*100)
print("SUMMARY")
print("="*100)

with psycopg2.connect(**DB) as cn:
    with cn.cursor() as cur:
        # Overall totals 2012-2014
        cur.execute("""
            SELECT 
                COUNT(*) as total_banking,
                SUM(debit_amount) as total_debits,
                SUM(credit_amount) as total_credits
            FROM banking_transactions
            WHERE EXTRACT(YEAR FROM transaction_date) BETWEEN 2012 AND 2014
        """)
        
        total_banking = cur.fetchone()
        
        cur.execute("""
            SELECT 
                COUNT(*) as total_receipts,
                SUM(gross_amount) as total_amount
            FROM receipts
            WHERE EXTRACT(YEAR FROM receipt_date) BETWEEN 2012 AND 2014
        """)
        
        total_receipts = cur.fetchone()
        
        cur.execute("""
            SELECT 
                COUNT(*) as total_payments,
                SUM(amount) as total_amount
            FROM payments
            WHERE EXTRACT(YEAR FROM payment_date) BETWEEN 2012 AND 2014
        """)
        
        total_payments = cur.fetchone()
        
        print(f"\n2012-2014 COMBINED:")
        print("-" * 100)
        if total_banking and total_banking[0] > 0:
            print(f"  Banking transactions: {total_banking[0]:>6} (${total_banking[1] or 0:,.2f} debits, ${total_banking[2] or 0:,.2f} credits)")
        if total_receipts and total_receipts[0] > 0:
            print(f"  Receipts: {total_receipts[0]:>6} (${total_receipts[1] or 0:,.2f})")
        if total_payments and total_payments[0] > 0:
            print(f"  Charter payments: {total_payments[0]:>6} (${total_payments[1] or 0:,.2f})")

print("\n" + "="*100)
