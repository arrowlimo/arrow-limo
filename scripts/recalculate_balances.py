"""
Recalculate all charter balances based on actual payments
Balance = total_amount_due - SUM(payments)
"""

import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REDACTED***")

print("=" * 100)
print("RECALCULATING CHARTER BALANCES")
print("=" * 100)

try:
    alms_conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    alms_cursor = alms_conn.cursor()
    
    # Get all charters
    alms_cursor.execute("""
        SELECT charter_id, reserve_number, total_amount_due
        FROM charters
        WHERE reserve_number IS NOT NULL
        ORDER BY charter_id
    """)
    
    all_charters = alms_cursor.fetchall()
    print(f"\nProcessing {len(all_charters)} charters...")
    
    updated_count = 0
    
    for charter_id, reserve_num, total_due in all_charters:
        # Get total payments for this charter
        alms_cursor.execute("""
            SELECT COALESCE(SUM(amount), 0) as total_paid
            FROM payments
            WHERE reserve_number = %s
        """, (reserve_num,))
        
        total_paid = alms_cursor.fetchone()[0]
        
        # Calculate new balance
        new_balance = total_due - total_paid
        
        # Update the charter balance
        alms_cursor.execute("""
            UPDATE charters
            SET balance = %s
            WHERE charter_id = %s
        """, (new_balance, charter_id))
        
        updated_count += 1
        
        # Show overpaid reserves
        if new_balance < 0 and updated_count <= 100:  # Only show first 100
            if reserve_num in ['001009', '001010', '001011', '001015', '001017', '001019', '001021']:
                print(f"Charter {charter_id} (Reserve {reserve_num}): Due ${total_due:.2f} - Paid ${total_paid:.2f} = Balance ${new_balance:.2f}")
    
    # Commit all updates
    alms_conn.commit()
    print(f"\n✅ Updated {updated_count} charter balances")
    
    # Verify the 54 problematic reserves
    print("\nVerifying overpaid reserves after recalculation:")
    print("-" * 100)
    
    alms_cursor.execute("""
        SELECT reserve_number, total_amount_due, balance
        FROM charters
        WHERE reserve_number IN ('001009', '001010', '001011', '001015', '001017', '001019', '001021')
        ORDER BY reserve_number
    """)
    
    for reserve_num, total_due, balance in alms_cursor.fetchall():
        status = "✅" if balance >= 0 else "⚠️ "
        print(f"{status} Reserve {reserve_num}: Due ${total_due:.2f} | Balance ${balance:.2f}")
    
    # Count remaining overpaid
    alms_cursor.execute("""
        SELECT COUNT(*) as cnt, COALESCE(SUM(ABS(balance)), 0) as total_overpay
        FROM charters
        WHERE balance < 0
    """)
    
    remaining_count, total_overpay = alms_cursor.fetchone()
    
    print(f"\n{'='*100}")
    print(f"FINAL STATUS")
    print(f"{'='*100}")
    print(f"Remaining overpaid reserves: {remaining_count}")
    print(f"Total overpayment amount:    ${total_overpay:.2f}")
    
    if remaining_count == 0:
        print("✅ ALL BALANCES CORRECTED!")
    else:
        print(f"⚠️  Still have {remaining_count} overpaid reserves - investigate why")
    
    alms_conn.close()
    
except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
