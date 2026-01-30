"""
Fix cancelled duplicate charter 016854 that was double-booked - actual run is 016857.
Zero out financial fields and add note pointing to actual charter.
"""
import sys
import psycopg2

def main():
    write_mode = '--write' in sys.argv
    
    cancelled_reserve = '016854'
    actual_reserve = '016857'
    
    print("\n" + "="*100)
    print("FIX CANCELLED DUPLICATE CHARTER - DOUBLE BOOKING")
    print("="*100)
    print(f"\nCancelled duplicate: {cancelled_reserve}")
    print(f"Actual run charter:  {actual_reserve}")
    
    if not write_mode:
        print("\n⚠️  DRY RUN - Use --write to apply changes\n")
    
    conn = psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )
    cur = conn.cursor()
    
    # Get current state of cancelled charter
    cur.execute("""
        SELECT charter_id, reserve_number, status, cancelled, 
               total_amount_due, paid_amount, balance, notes
        FROM charters 
        WHERE reserve_number = %s
    """, (cancelled_reserve,))
    
    cancelled_row = cur.fetchone()
    
    if not cancelled_row:
        print(f"✗ Charter {cancelled_reserve} not found")
        cur.close(); conn.close()
        return
    
    charter_id = cancelled_row[0]
    current_status = cancelled_row[2]
    current_cancelled = cancelled_row[3]
    current_total = float(cancelled_row[4]) if cancelled_row[4] else 0
    current_paid = float(cancelled_row[5]) if cancelled_row[5] else 0
    current_balance = float(cancelled_row[6]) if cancelled_row[6] else 0
    current_notes = cancelled_row[7] or ''
    
    print(f"\nCurrent state of {cancelled_reserve}:")
    print(f"  Status: {current_status}")
    print(f"  Cancelled: {current_cancelled}")
    print(f"  Total Due: ${current_total:.2f}")
    print(f"  Paid: ${current_paid:.2f}")
    print(f"  Balance: ${current_balance:.2f}")
    
    # Check if it has imported charges
    cur.execute("""
        SELECT COUNT(*), SUM(amount) 
        FROM charter_charges 
        WHERE charter_id = %s
    """, (charter_id,))
    charge_row = cur.fetchone()
    num_charges = charge_row[0]
    charges_total = float(charge_row[1]) if charge_row[1] else 0
    
    print(f"  Charges: {num_charges} rows totaling ${charges_total:.2f}")
    
    # Check actual charter
    cur.execute("""
        SELECT reserve_number, status, cancelled, total_amount_due
        FROM charters
        WHERE reserve_number = %s
    """, (actual_reserve,))
    actual_row = cur.fetchone()
    
    if actual_row:
        print(f"\nActual charter {actual_reserve}:")
        print(f"  Status: {actual_row[1]}")
        print(f"  Cancelled: {actual_row[2]}")
        print(f"  Total Due: ${float(actual_row[3]) if actual_row[3] else 0:.2f}")
    else:
        print(f"\n⚠️  Warning: Actual charter {actual_reserve} not found in database")
    
    # Prepare update
    new_note = f"CANCELLED - Double booking. Actual run is {actual_reserve}."
    if current_notes:
        new_note = f"{current_notes}\n\n{new_note}"
    
    print(f"\nPlanned updates to {cancelled_reserve}:")
    print(f"  Set status → 'Cancelled'")
    print(f"  Set cancelled → TRUE")
    print(f"  Set total_amount_due → 0.00")
    print(f"  Set paid_amount → 0.00")
    print(f"  Set balance → 0.00")
    print(f"  Append note → 'CANCELLED - Double booking. Actual run is {actual_reserve}.'")
    
    if num_charges > 0:
        print(f"  Delete {num_charges} charter_charges rows")
    
    if write_mode:
        # Delete charges
        if num_charges > 0:
            cur.execute("DELETE FROM charter_charges WHERE charter_id = %s", (charter_id,))
            print(f"\n✓ Deleted {num_charges} charge rows")
        
        # Update charter
        cur.execute("""
            UPDATE charters
            SET status = 'Cancelled',
                cancelled = TRUE,
                total_amount_due = 0.00,
                paid_amount = 0.00,
                balance = 0.00,
                notes = %s
            WHERE charter_id = %s
        """, (new_note, charter_id))
        
        conn.commit()
        print(f"✓ Updated charter {cancelled_reserve}")
        print(f"\nCOMMITTED - Charter {cancelled_reserve} zeroed and marked as duplicate")
    else:
        print(f"\nDRY RUN - No changes made. Use --write to apply.")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
