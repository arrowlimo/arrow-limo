#!/usr/bin/env python3
"""
Check final Fibrenew status after importing invoices from statement.
"""
import psycopg2
from decimal import Decimal

DB = dict(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')

STATEMENT_BALANCE = Decimal('14734.56')

print("\n" + "="*100)
print("FIBRENEW FINAL STATUS CHECK")
print("="*100)

with psycopg2.connect(**DB) as cn:
    with cn.cursor() as cur:
        # Check rent_debt_ledger balance
        cur.execute("""
            SELECT running_balance
            FROM rent_debt_ledger
            ORDER BY transaction_date DESC, id DESC
            LIMIT 1
        """)
        ledger_balance = cur.fetchone()
        
        if ledger_balance:
            print(f"\n📊 RENT_DEBT_LEDGER:")
            print(f"  Current balance: ${ledger_balance[0]:,.2f}")
            print(f"  Statement balance: ${STATEMENT_BALANCE:,.2f}")
            print(f"  Difference: ${abs(ledger_balance[0] - STATEMENT_BALANCE):,.2f}")
            
            if abs(ledger_balance[0] - STATEMENT_BALANCE) < Decimal('0.01'):
                print(f"  ✅ MATCHES!")
            else:
                print(f"  ❌ DOES NOT MATCH")
        
        # Check for Fibrenew invoices in receipts table
        cur.execute("""
            SELECT COUNT(*), SUM(gross_amount), SUM(net_amount)
            FROM receipts
            WHERE vendor_name = 'Fibrenew'
            OR description LIKE '%Fibrenew%'
        """)
        receipt_count, receipt_gross, receipt_net = cur.fetchone()
        
        print(f"\n📋 RECEIPTS TABLE (Fibrenew):")
        print(f"  Count: {receipt_count}")
        print(f"  Gross amount: ${receipt_gross:,.2f}" if receipt_gross else "  Gross amount: $0.00")
        print(f"  Net amount: ${receipt_net:,.2f}" if receipt_net else "  Net amount: $0.00")
        
        # Check recurring_invoices table
        cur.execute("""
            SELECT COUNT(*), SUM(total_amount)
            FROM recurring_invoices
            WHERE vendor_name = 'Fibrenew'
        """)
        inv_count, inv_total = cur.fetchone()
        
        print(f"\n📄 RECURRING_INVOICES TABLE:")
        print(f"  Count: {inv_count or 0}")
        print(f"  Total: ${inv_total:,.2f}" if inv_total else "  Total: $0.00")
        
        # Check for invoices with statement invoice numbers
        cur.execute("""
            SELECT COUNT(*)
            FROM receipts
            WHERE description LIKE '%Invoice #%'
            AND vendor_name = 'Fibrenew'
        """)
        stmt_inv_count = cur.fetchone()[0]
        
        print(f"\n🔍 INVOICES FROM STATEMENT:")
        print(f"  Imported: {stmt_inv_count}")
        print(f"  Expected: 68")
        
        if stmt_inv_count >= 68:
            print(f"  ✅ ALL IMPORTED")
        else:
            print(f"  ⚠️  Missing {68 - stmt_inv_count} invoices")
        
        # Summary
        print("\n" + "="*100)
        print("SUMMARY:")
        print("="*100)
        
        if ledger_balance and abs(ledger_balance[0] - STATEMENT_BALANCE) < Decimal('0.01'):
            print("✅ Fibrenew debt tracking is CORRECT")
            print(f"   Outstanding balance: ${STATEMENT_BALANCE:,.2f}")
            print("   Matches statement dated Nov 26, 2025")
        else:
            print("❌ Fibrenew debt tracking needs correction")
            if ledger_balance:
                print(f"   Database: ${ledger_balance[0]:,.2f}")
                print(f"   Statement: ${STATEMENT_BALANCE:,.2f}")
                print(f"   Gap: ${abs(ledger_balance[0] - STATEMENT_BALANCE):,.2f}")

print("\n" + "="*100)
