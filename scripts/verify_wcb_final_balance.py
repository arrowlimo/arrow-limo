#!/usr/bin/env python3
"""
Verify WCB final balance after all 4 payments are linked.
User's corrected Excel shows final balance should be $3,593.83
"""

import os
import psycopg2
from datetime import datetime

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

try:
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    print("="*70)
    print("WCB ACCOUNT FINAL BALANCE VERIFICATION")
    print("="*70)
    
    # Get all WCB invoices (positive amounts = invoiced)
    cur.execute("""
        SELECT COUNT(*), COALESCE(SUM(gross_amount), 0)
        FROM receipts
        WHERE vendor_name = 'WCB' AND gross_amount > 0
    """)
    invoice_count, invoice_total = cur.fetchone()
    print(f"\nTotal WCB Invoices: {invoice_count}")
    print(f"Total Invoice Amount: ${invoice_total:,.2f}")
    
    # Get all WCB payments from receipts (negative amounts = paid)
    cur.execute("""
        SELECT COUNT(*), COALESCE(SUM(ABS(gross_amount)), 0)
        FROM receipts
        WHERE vendor_name = 'WCB' AND gross_amount < 0
    """)
    payment_count, payment_total = cur.fetchone()
    print(f"\nTotal WCB Payments (receipts): {payment_count}")
    print(f"Total Payment Amount: ${payment_total:,.2f}")
    
    # Get WCB banking transactions
    cur.execute("""
        SELECT COUNT(*), COALESCE(SUM(credit_amount), 0)
        FROM banking_transactions bt
        WHERE description LIKE '%WCB%' AND credit_amount > 0
    """)
    bank_count, bank_total = cur.fetchone()
    print(f"\nTotal WCB Payments (banking): {bank_count}")
    print(f"Total Banking Amount: ${bank_total:,.2f}")
    
    print(f"\n{'='*70}")
    print("FINAL BALANCE CALCULATION")
    print(f"{'='*70}")
    
    total_invoices = invoice_total
    total_payments = payment_total + bank_total
    
    print(f"Opening Balance: $0.00")
    print(f"+ Invoices: ${total_invoices:,.2f}")
    print(f"- Payments: ${total_payments:,.2f}")
    
    final_balance = total_invoices - total_payments
    print(f"\nCalculated Final Balance: ${final_balance:,.2f}")
    print(f"Target Balance (from Excel): $3,593.83")
    
    if abs(final_balance - 3593.83) < 0.01:
        print("\n✅ BALANCE MATCHES! Account is properly reconciled.")
    else:
        diff = final_balance - 3593.83
        print(f"\n⚠️  DIFFERENCE: ${diff:+,.2f}")
        print("   This may indicate:")
        print("   - Additional invoices not yet recorded")
        print("   - Or payments not yet matched")
    
    print(f"\n{'='*70}")
    print("PAYMENT LINKAGE VERIFICATION")
    print(f"{'='*70}")
    
    # Check each payment
    payments = [
        (145297, "$686.65", "2012-03-19"),
        (69282, "$3,446.02", "2012-08-28"),
        (69587, "$553.17", "2012-11-27"),
        (145305, "$593.81", "2012-11-27"),
    ]
    
    for receipt_id, amount, date in payments:
        cur.execute("""
            SELECT COUNT(*)
            FROM banking_receipt_matching_ledger
            WHERE receipt_id = %s
        """, (receipt_id,))
        count = cur.fetchone()[0]
        status = "✓" if count > 0 else "✗"
        print(f"{status} Receipt {receipt_id:6} ({amount:>10} on {date}): {count} linked invoice(s)")
    
    conn.close()

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
