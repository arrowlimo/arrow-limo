#!/usr/bin/env python3
"""
Find and verify all 4 WCB payments in the database.
1. $686.65 (2012-12-30) - 2011 payment
2. $3,446.02 (2012-08-28) - main payment
3. $553.17 (2012-11-26) - second payment
4. $593.81 (2012-11-27) - waived late fee refunded
"""
import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

try:
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    
    print("\n" + "="*80)
    print("FINDING ALL 4 WCB PAYMENTS")
    print("="*80)
    
    # Search for all amounts
    payment_amounts = [686.65, 3446.02, 553.17, 593.81]
    
    for amount in payment_amounts:
        print(f"\nSearching for ${amount:.2f}...")
        
        # Look in banking_transactions
        cur.execute("""
            SELECT transaction_id, transaction_date, debit_amount, credit_amount, check_number, description
            FROM banking_transactions
            WHERE (ABS(debit_amount - %s) < 0.01 OR ABS(credit_amount - %s) < 0.01)
              AND transaction_date >= '2011-01-01'
              AND transaction_date <= '2012-12-31'
        """, (amount, amount))
        
        results = cur.fetchall()
        if results:
            for tx_id, tx_date, debit, credit, check, desc in results:
                print(f"  ✓ Found TX {tx_id}: {tx_date} | Check: {check} | Debit: ${float(debit) if debit else 0:.2f} | Credit: ${float(credit) if credit else 0:.2f} | {desc}")
        else:
            print(f"  ✗ Not found in banking_transactions")
            
            # Try looking in receipts as a voided/refunded entry
            cur.execute("""
                SELECT receipt_id, receipt_date, vendor_name, gross_amount, banking_transaction_id
                FROM receipts
                WHERE ABS(gross_amount - %s) < 0.01
                  AND vendor_name ILIKE '%%wcb%%'
                  AND receipt_date >= '2011-01-01'
                  AND receipt_date <= '2012-12-31'
                ORDER BY receipt_date DESC
                LIMIT 1
            """, (amount,))
            
            result = cur.fetchone()
            if result:
                rec_id, rec_date, vendor, rec_amount, banking_id = result
                print(f"  ✓ Found as Receipt {rec_id}: {rec_date} | ${float(rec_amount):.2f} | Banking ID: {banking_id}")
            else:
                print(f"  ✗ Not found anywhere")
    
    print(f"\n" + "="*80)
    print("SUMMARY OF PAYMENTS")
    print("="*80)
    
    # Get all WCB banking transactions
    cur.execute("""
        SELECT transaction_id, transaction_date, debit_amount, credit_amount, description, check_number
        FROM banking_transactions
        WHERE (description ILIKE '%%wcb%%' OR description ILIKE '%%workers%%')
          AND transaction_date >= '2011-01-01'
          AND transaction_date <= '2012-12-31'
        ORDER BY transaction_date
    """)
    
    print("\nBanking transactions:")
    total_payments = 0.0
    for tx_id, tx_date, debit, credit, desc, check in cur.fetchall():
        debit_f = float(debit) if debit else 0.0
        credit_f = float(credit) if credit else 0.0
        amount_f = debit_f if debit_f > 0 else credit_f
        total_payments += amount_f
        print(f"  TX {tx_id}: {tx_date} | ${amount_f:>8.2f} | Check: {check} | {desc}")
    
    # Get refunded/waived entries
    cur.execute("""
        SELECT receipt_id, receipt_date, vendor_name, gross_amount, description
        FROM receipts
        WHERE vendor_name ILIKE '%%wcb%%'
          AND receipt_date >= '2011-01-01'
          AND receipt_date <= '2012-12-31'
          AND (description ILIKE '%%waived%%' OR description ILIKE '%%refund%%')
        ORDER BY receipt_date
    """)
    
    refunded_total = 0.0
    print("\nRefunded/Waived entries:")
    for rec_id, rec_date, vendor, amount, desc in cur.fetchall():
        amount_f = float(amount)
        refunded_total += amount_f
        print(f"  Receipt {rec_id}: {rec_date} | ${amount_f:>8.2f} | {desc}")
    
    print(f"\nTotal banking payments: ${total_payments:.2f}")
    print(f"Total refunded: ${refunded_total:.2f}")
    print(f"Expected total: ${686.65 + 3446.02 + 553.17 + 593.81:.2f}")
    
    cur.close()
    conn.close()
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
