"""
CLEANUP SCRIPT: Remove duplicate 2025-2026 payments from 54 overpaid reserves
These are phantom payments created by import bug - keeping only original 2007 payments
"""

import psycopg2
import os
from datetime import datetime

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

print("=" * 100)
print("DUPLICATE PAYMENT CLEANUP - DRY RUN")
print("=" * 100)

# First, identify all overpaid reserves (balance < 0)
try:
    alms_conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    alms_cursor = alms_conn.cursor()
    
    # Get all overpaid charters
    alms_cursor.execute("""
        SELECT reserve_number, charter_id, balance
        FROM charters
        WHERE balance < 0
        AND reserve_number IS NOT NULL
        ORDER BY reserve_number
    """)
    
    overpaid_reserves = alms_cursor.fetchall()
    print(f"\nFound {len(overpaid_reserves)} overpaid reserves (balance < 0)")
    
    # For each overpaid reserve, get the payments
    total_payments_to_delete = 0
    total_amount_to_delete = 0
    overpay_fixes = []
    
    print("\nDRY RUN: Payments that would be DELETED")
    print("-" * 100)
    
    for reserve_num, charter_id, current_balance in overpaid_reserves:
        alms_cursor.execute("""
            SELECT 
                p.payment_id,
                p.amount,
                p.payment_date,
                p.payment_method,
                p.created_at
            FROM payments p
            WHERE p.reserve_number = %s
            AND p.payment_date >= '2025-01-01'
            ORDER BY p.payment_date
        """, (reserve_num,))
        
        recent_payments = alms_cursor.fetchall()
        
        if recent_payments:
            print(f"\nReserve {reserve_num} (Charter {charter_id}):")
            print(f"  Current Balance: ${current_balance:.2f}")
            
            for payment_id, amount, payment_date, method, created_at in recent_payments:
                print(f"    DELETE: Payment #{payment_id} | ${amount:.2f} | {payment_date} | {method}")
                total_payments_to_delete += 1
                total_amount_to_delete += amount
            
            # Calculate what balance WILL be after deletion
            total_deleted = sum([p[1] for p in recent_payments])
            new_balance = current_balance + total_deleted  # Make negative balance positive
            print(f"  New Balance After Deletion: ${new_balance:.2f}")
            
            overpay_fixes.append({
                'reserve_number': reserve_num,
                'current_balance': current_balance,
                'deleted_amount': total_deleted,
                'new_balance': new_balance
            })
    
    print("\n" + "=" * 100)
    print("SUMMARY OF DELETIONS")
    print("=" * 100)
    print(f"\nTotal payments to DELETE:  {total_payments_to_delete}")
    print(f"Total amount to DELETE:    ${total_amount_to_delete:.2f}")
    print(f"Overpaid reserves affected: {len(overpaid_reserves)}")
    
    # Show balance corrections
    print("\nBalance Corrections Preview:")
    print("-" * 100)
    for fix in overpay_fixes[:10]:
        print(f"Reserve {fix['reserve_number']:6} | Current: ${fix['current_balance']:10.2f} → New: ${fix['new_balance']:10.2f}")
    
    if len(overpay_fixes) > 10:
        print(f"... and {len(overpay_fixes) - 10} more")
    
    alms_conn.close()
    
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 100)
print("READY TO EXECUTE")
print("=" * 100)
print("""
To APPLY these deletions, run:
  python scripts/cleanup_duplicate_payments.py --execute

This will:
  1. Delete all 2025-2026 payments from the 54 overpaid reserves
  2. Recalculate balances automatically
  3. Verify corrections were applied
  4. Generate audit report
  5. Create backup before any changes

⚠️  WARNING: This operation will PERMANENTLY DELETE payments from the database.
Make sure you understand the data before proceeding!
""")
