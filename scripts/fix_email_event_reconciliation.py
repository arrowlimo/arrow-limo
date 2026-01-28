#!/usr/bin/env python3
"""
Fix email_financial_events reconciliation after duplicate deletion.

Email event ID 28428 was linked to banking_transaction_id 45438,
but that was a duplicate that was deleted. Update to link to the
correct transaction ID 43061 (2017-04-20 $131.26).
"""

import os
import psycopg2
from datetime import date as _date, datetime as _datetime

DB = dict(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REMOVED***'),
)

def main():
    print("FIXING EMAIL EVENT RECONCILIATION")
    print("=" * 80)
    
    with psycopg2.connect(**DB) as conn:
        with conn.cursor() as cur:
            # Check current state
            cur.execute("""
                SELECT id, email_date, amount, banking_transaction_id, 
                       matched_account_number, notes
                FROM email_financial_events
                WHERE id = 28428
            """)
            
            event = cur.fetchone()
            if not event:
                print("[FAIL] Email event ID 28428 not found")
                return
            
            print(f"Current email event state:")
            print(f"  ID: {event[0]}")
            print(f"  Date: {event[1]}")
            print(f"  Amount: ${event[2]}")
            print(f"  Banking ID: {event[3]}")
            print(f"  Account: {event[4]}")
            print(f"  Notes: {event[5]}")
            
            # Verify the correct banking transaction exists
            cur.execute("""
                SELECT transaction_id, transaction_date, description, 
                       credit_amount, debit_amount
                FROM banking_transactions
                WHERE transaction_id = 43061
            """)
            
            banking = cur.fetchone()
            if not banking:
                print("\n[FAIL] Banking transaction ID 43061 not found")
                return
            
            print(f"\nTarget banking transaction:")
            print(f"  ID: {banking[0]}")
            print(f"  Date: {banking[1]}")
            print(f"  Description: {banking[2]}")
            print(f"  Credit: ${banking[3] or 0}")
            print(f"  Debit: ${banking[4] or 0}")
            
            # Verify the old one is deleted
            cur.execute("""
                SELECT COUNT(*) FROM banking_transactions
                WHERE transaction_id = 45438
            """)
            
            if cur.fetchone()[0] > 0:
                print("\n[WARN]  WARNING: Old transaction ID 45438 still exists!")
            else:
                print("\n[OK] Confirmed: Old transaction ID 45438 is deleted")
            
            # Update the email event
            print("\nUpdating email event...")
            cur.execute("""
                UPDATE email_financial_events
                SET banking_transaction_id = 43061,
                    notes = COALESCE(notes || ' | ', '') || 
                            'Reconciliation fixed: updated from deleted duplicate ID 45438 to correct ID 43061'
                WHERE id = 28428
            """)
            
            conn.commit()
            
            print("[OK] Email event reconciliation updated")
            
            # Verify final state
            cur.execute("""
                SELECT e.id, e.email_date, e.amount, e.banking_transaction_id,
                       b.transaction_date, b.description, b.credit_amount, b.debit_amount
                FROM email_financial_events e
                LEFT JOIN banking_transactions b ON b.transaction_id = e.banking_transaction_id
                WHERE e.id = 28428
            """)
            
            final = cur.fetchone()
            print(f"\nFinal reconciliation state:")
            print(f"  Email event ID: {final[0]}")
            print(f"  Email date: {final[1]}")
            print(f"  Email amount: ${final[2]}")
            print(f"  Banking ID: {final[3]}")
            print(f"  Banking date: {final[4]}")
            print(f"  Banking desc: {final[5]}")
            print(f"  Banking credit: ${final[6] or 0:.2f}")
            print(f"  Banking debit:  ${final[7] or 0:.2f}")
            
            banking_amount = float(final[6] or 0) if float(final[6] or 0) > 0 else float(final[7] or 0)
            # Normalize dates for comparison (email_date may be datetime, banking transaction_date is date)
            email_dt = final[1]
            bank_dt = final[4]
            email_date = email_dt.date() if isinstance(email_dt, _datetime) else email_dt
            bank_date = bank_dt.date() if isinstance(bank_dt, _datetime) else bank_dt

            if email_date == bank_date and float(final[2]) == banking_amount:
                print("\n[OK] RECONCILIATION VERIFIED: Date and amount match (matched against {} column)!".format(
                    'credit' if float(final[6] or 0) > 0 else 'debit'))
            else:
                print("\n[WARN]  Reconciliation mismatch detected")


if __name__ == '__main__':
    main()
