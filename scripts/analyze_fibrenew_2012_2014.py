#!/usr/bin/env python3
"""
Analyze Fibrenew receipts, payments, and checks for 2012-2014
"""
import psycopg2
from decimal import Decimal

DB = dict(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')

print("\n" + "="*100)
print("FIBRENEW 2012-2014 ANALYSIS")
print("="*100)

with psycopg2.connect(**DB) as cn:
    with cn.cursor() as cur:
        for year in [2012, 2013, 2014]:
            print(f"\n{'='*100}")
            print(f"YEAR {year}")
            print(f"{'='*100}")
            
            # Fibrenew receipts
            cur.execute("""
                SELECT 
                    COUNT(*) as receipt_count,
                    SUM(gross_amount) as total_gross,
                    SUM(gst_amount) as total_gst,
                    SUM(net_amount) as total_net
                FROM receipts
                WHERE EXTRACT(YEAR FROM receipt_date) = %s
                AND (vendor_name ILIKE '%%fibrenew%%' OR description ILIKE '%%fibrenew%%')
            """, (year,))
            
            receipt_data = cur.fetchone()
            
            if receipt_data and receipt_data[0] > 0:
                r_cnt, r_gross, r_gst, r_net = receipt_data
                print(f"\n📋 FIBRENEW RECEIPTS:")
                print("-" * 100)
                print(f"  Count: {r_cnt}")
                print(f"  Gross amount: ${r_gross:,.2f}")
                print(f"  GST amount: ${r_gst:,.2f}")
                print(f"  Net amount: ${r_net:,.2f}")
                
                # List individual receipts
                cur.execute("""
                    SELECT receipt_date, vendor_name, description, gross_amount, gst_amount
                    FROM receipts
                    WHERE EXTRACT(YEAR FROM receipt_date) = %s
                    AND (vendor_name ILIKE '%%fibrenew%%' OR description ILIKE '%%fibrenew%%')
                    ORDER BY receipt_date
                """, (year,))
                
                receipts = cur.fetchall()
                print(f"\n  Individual Receipts:")
                print(f"  {'Date':<12} {'Vendor':<20} {'Description':<40} {'Gross':>12} {'GST':>10}")
                print("  " + "-" * 96)
                for dt, vendor, desc, gross, gst in receipts:
                    vendor_str = (vendor or '')[:20]
                    desc_str = (desc or '')[:40]
                    print(f"  {dt!s:<12} {vendor_str:<20} {desc_str:<40} ${gross:>10,.2f} ${gst:>8,.2f}")
            else:
                print(f"\n⚠️  No Fibrenew receipts for {year}")
            
            # Fibrenew payments in rent_debt_ledger
            cur.execute("""
                SELECT 
                    COUNT(*) as payment_count,
                    SUM(payment_amount) as total_payments
                FROM rent_debt_ledger
                WHERE EXTRACT(YEAR FROM transaction_date) = %s
                AND transaction_type = 'PAYMENT'
            """, (year,))
            
            payment_data = cur.fetchone()
            
            if payment_data and payment_data[0] > 0:
                p_cnt, p_amt = payment_data
                print(f"\n💰 FIBRENEW RENT PAYMENTS (from rent_debt_ledger):")
                print("-" * 100)
                print(f"  Count: {p_cnt}")
                print(f"  Total: ${p_amt:,.2f}")
                
                # List payments
                cur.execute("""
                    SELECT transaction_date, payment_amount, description
                    FROM rent_debt_ledger
                    WHERE EXTRACT(YEAR FROM transaction_date) = %s
                    AND transaction_type = 'PAYMENT'
                    ORDER BY transaction_date
                """, (year,))
                
                payments = cur.fetchall()
                print(f"\n  Individual Payments:")
                print(f"  {'Date':<12} {'Amount':>12} {'Description':<60}")
                print("  " + "-" * 86)
                for dt, amt, desc in payments:
                    desc_str = (desc or '')[:60]
                    print(f"  {dt!s:<12} ${amt:>10,.2f} {desc_str:<60}")
            else:
                print(f"\n⚠️  No Fibrenew rent payments for {year}")
            
            # Fibrenew charges
            cur.execute("""
                SELECT 
                    COUNT(*) as charge_count,
                    SUM(charge_amount) as total_charges
                FROM rent_debt_ledger
                WHERE EXTRACT(YEAR FROM transaction_date) = %s
                AND transaction_type = 'CHARGE'
            """, (year,))
            
            charge_data = cur.fetchone()
            
            if charge_data and charge_data[0] > 0:
                c_cnt, c_amt = charge_data
                print(f"\n📄 FIBRENEW RENT CHARGES:")
                print("-" * 100)
                print(f"  Count: {c_cnt}")
                print(f"  Total: ${c_amt:,.2f}")
                print(f"  Average: ${c_amt/c_cnt:,.2f}/month" if c_cnt > 0 else "")
            
            # Check for Fibrenew in banking transactions
            cur.execute("""
                SELECT 
                    COUNT(*) as txn_count,
                    SUM(debit_amount) as total_debits,
                    SUM(credit_amount) as total_credits
                FROM banking_transactions
                WHERE EXTRACT(YEAR FROM transaction_date) = %s
                AND description ILIKE '%%fibrenew%%'
            """, (year,))
            
            banking_data = cur.fetchone()
            
            if banking_data and banking_data[0] > 0:
                b_cnt, b_debits, b_credits = banking_data
                print(f"\n🏦 FIBRENEW IN BANKING TRANSACTIONS:")
                print("-" * 100)
                print(f"  Count: {b_cnt}")
                print(f"  Debits: ${b_debits or 0:,.2f}")
                print(f"  Credits: ${b_credits or 0:,.2f}")

print("\n" + "="*100)
print("SUMMARY")
print("="*100)

with psycopg2.connect(**DB) as cn:
    with cn.cursor() as cur:
        # Total receipts 2012-2014
        cur.execute("""
            SELECT 
                COUNT(*) as total_receipts,
                SUM(gross_amount) as total_amount
            FROM receipts
            WHERE EXTRACT(YEAR FROM receipt_date) BETWEEN 2012 AND 2014
            AND (vendor_name ILIKE '%%fibrenew%%' OR description ILIKE '%%fibrenew%%')
        """)
        
        total_receipts = cur.fetchone()
        
        # Total payments 2012-2014
        cur.execute("""
            SELECT 
                COUNT(*) as total_payments,
                SUM(payment_amount) as total_amount
            FROM rent_debt_ledger
            WHERE EXTRACT(YEAR FROM transaction_date) BETWEEN 2012 AND 2014
            AND transaction_type = 'PAYMENT'
        """)
        
        total_payments = cur.fetchone()
        
        # Total charges 2012-2014
        cur.execute("""
            SELECT 
                COUNT(*) as total_charges,
                SUM(charge_amount) as total_amount
            FROM rent_debt_ledger
            WHERE EXTRACT(YEAR FROM transaction_date) BETWEEN 2012 AND 2014
            AND transaction_type = 'CHARGE'
        """)
        
        total_charges = cur.fetchone()
        
        print(f"\n2012-2014 COMBINED:")
        print("-" * 100)
        if total_receipts and total_receipts[0] > 0:
            print(f"  Fibrenew receipts: {total_receipts[0]} (${total_receipts[1]:,.2f})")
        else:
            print(f"  Fibrenew receipts: 0")
        
        if total_payments and total_payments[0] > 0:
            print(f"  Rent payments: {total_payments[0]} (${total_payments[1]:,.2f})")
        else:
            print(f"  Rent payments: 0")
        
        if total_charges and total_charges[0] > 0:
            print(f"  Rent charges: {total_charges[0]} (${total_charges[1]:,.2f})")
        else:
            print(f"  Rent charges: 0")
        
        if total_payments and total_charges and total_payments[0] > 0 and total_charges[0] > 0:
            net = total_charges[1] - total_payments[1]
            print(f"  Net owed: ${net:,.2f}")

print("\n" + "="*100)
