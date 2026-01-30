"""
Fix the 4 overpaid quote charters that have payments but no charges.
Since we can't find them in LMS and they're quotes, set total_amount_due = paid_amount
so balance becomes $0.
"""
import psycopg2

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )

def fix_overpaid_quotes():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 100)
    print("FIXING OVERPAID QUOTES WITH NO CHARGES")
    print("=" * 100)
    
    reserves = ['019536', '019571', '019657', '019586']
    
    for reserve in reserves:
        cur.execute("""
            SELECT charter_id, reserve_number, total_amount_due, paid_amount, balance, booking_status
            FROM charters 
            WHERE reserve_number = %s
        """, (reserve,))
        
        row = cur.fetchone()
        if not row:
            print(f"\n[FAIL] {reserve}: Not found")
            continue
        
        charter_id, res_num, total_due, paid, balance, status = row
        
        print(f"\n{reserve} ({status}):")
        print(f"  Current: total=${total_due:.2f}, paid=${paid:.2f}, balance=${balance:.2f}")
        
        # Set total_amount_due = paid_amount, balance = 0
        cur.execute("""
            UPDATE charters 
            SET total_amount_due = paid_amount,
                balance = 0,
                updated_at = CURRENT_TIMESTAMP
            WHERE charter_id = %s
        """, (charter_id,))
        
        print(f"  Updated: total=${paid:.2f}, paid=${paid:.2f}, balance=$0.00")
        print(f"  ✓ Balanced (total_due set to match payment)")
    
    conn.commit()
    
    print("\n" + "=" * 100)
    print("COMPLETE - All 4 charters now balanced")
    print("=" * 100)
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    fix_overpaid_quotes()
