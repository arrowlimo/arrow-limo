"""
Check reserve 019238 status and reallocate payment 78348 ($479.70) from 018885 to 019238.

This payment (#dor5) should be on 019238, not 018885.
"""
import psycopg2
import os
from datetime import datetime
from table_protection import create_backup_before_delete, log_deletion_audit


def connect():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        dbname=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true', help='Apply changes')
    args = ap.parse_args()

    conn = connect()
    cur = conn.cursor()

    print('=== RESERVE 019238 CURRENT STATUS ===')
    cur.execute("""
        SELECT charter_id, reserve_number, charter_date,
               total_amount_due, paid_amount, balance, client_id
        FROM charters WHERE reserve_number = '019238'
    """)
    r = cur.fetchone()
    if r:
        print(f'Charter ID: {r[0]} | Date: {r[2]} | Client: {r[6]}')
        print(f'Total Due: ${r[3] if r[3] else 0:.2f}')
        print(f'Paid: ${r[4] if r[4] else 0:.2f}')
        print(f'Balance: ${r[5] if r[5] else 0:.2f}')
        
        cur.execute("""
            SELECT SUM(amount) FROM charter_charges 
            WHERE reserve_number = '019238'
        """)
        charges = cur.fetchone()[0] or 0
        print(f'Charges Sum: ${charges:.2f}')
        
        cur.execute("""
            SELECT payment_id, amount, payment_date 
            FROM payments 
            WHERE reserve_number = '019238' 
            ORDER BY payment_date
        """)
        pays = cur.fetchall()
        if pays:
            print(f'Payments ({len(pays)}):')
            for p in pays:
                print(f'  Payment {p[0]}: ${p[1]:.2f} on {p[2]}')
        else:
            print('No payments currently linked')
    else:
        print('Reserve 019238 not found')
        cur.close()
        conn.close()
        return

    print('\n=== PAYMENT 78348 ($479.70) DETAILS ===')
    cur.execute("""
        SELECT payment_id, reserve_number, amount, payment_date, 
               payment_method, square_payment_id, notes
        FROM payments WHERE payment_id = 78348
    """)
    p = cur.fetchone()
    if p:
        print(f'Payment ID: {p[0]}')
        print(f'Currently on Reserve: {p[1]}')
        print(f'Amount: ${p[2]:.2f}')
        print(f'Date: {p[3]}')
        print(f'Method: {p[4]}')
        print(f'Square ID: {p[5]}')
        print(f'Notes: {p[6][:100] if p[6] else "None"}')
    else:
        print('Payment 78348 not found')
        cur.close()
        conn.close()
        return

    print('\n=== PROPOSED CHANGE ===')
    print(f'Move payment 78348 ($479.70) from reserve {p[1]} to 019238')
    print('\nImpact:')
    print(f'  Reserve {p[1]}: paid amount will decrease by $479.70')
    print(f'  Reserve 019238: paid amount will increase by $479.70')

    if not args.write:
        print('\n*** DRY RUN - use --write to apply changes ***')
        cur.close()
        conn.close()
        return

    print('\n=== APPLYING CHANGES ===')
    
    # Create backup
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = f'payments_backup_78348_{ts}.sql'
    cur.execute("""
        SELECT payment_id, reserve_number, amount, payment_date
        FROM payments WHERE payment_id = 78348
    """)
    backup_row = cur.fetchone()
    with open(backup_file, 'w') as f:
        f.write(f'-- Backup of payment 78348 before reallocation to 019238\n')
        f.write(f'-- Original reserve: {backup_row[1]}\n')
        f.write(f'UPDATE payments SET reserve_number = ''{backup_row[1]}'' WHERE payment_id = 78348;\n')
    print(f'Backup created: {backup_file}')

    # Update payment reserve_number
    cur.execute("""
        UPDATE payments 
        SET reserve_number = '019238'
        WHERE payment_id = 78348
    """)
    print(f'Payment 78348 moved to reserve 019238')

    # Recalculate paid_amount and balance for both reserves
    for reserve in [p[1], '019238']:
        cur.execute("""
            WITH payment_sum AS (
                SELECT COALESCE(SUM(amount), 0) as total_paid
                FROM payments
                WHERE reserve_number = %s
            )
            UPDATE charters
            SET paid_amount = payment_sum.total_paid,
                balance = total_amount_due - payment_sum.total_paid
            FROM payment_sum
            WHERE reserve_number = %s
        """, (reserve, reserve))
        print(f'Recalculated paid_amount and balance for reserve {reserve}')

    conn.commit()
    
    # Verify results
    print('\n=== VERIFICATION ===')
    for reserve in [p[1], '019238']:
        cur.execute("""
            SELECT reserve_number, total_amount_due, paid_amount, balance
            FROM charters WHERE reserve_number = %s
        """, (reserve,))
        v = cur.fetchone()
        if v:
            print(f'{v[0]}: Total ${v[1]:.2f} | Paid ${v[2]:.2f} | Balance ${v[3]:.2f}')

    print('\n✓ Payment reallocation complete')
    
    cur.close()
    conn.close()


if __name__ == '__main__':
    main()
